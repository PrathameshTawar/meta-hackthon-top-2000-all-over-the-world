"""Unit tests for i18n helpers, quiet hours and webhook text helpers (no DB, no network)."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.api import webhooks
from app.api.webhooks import _clean_template_param, _is_status_query
from app.core.i18n import (
    SUPPORTED_LANGUAGES,
    TRANSLATIONS,
    detect_language,
    is_language_command,
    t,
)
from app.scheduler.escalation import get_ist_now, is_in_quiet_hours

IST = timezone(timedelta(hours=5, minutes=30))


# --- i18n.t ----------------------------------------------------------------

def test_t_returns_requested_language():
    key = next(iter(TRANSLATIONS))
    for lang in SUPPORTED_LANGUAGES:
        expected = TRANSLATIONS[key].get(lang) or TRANSLATIONS[key].get("en")
        assert t(key, lang) == expected


@pytest.mark.parametrize("lang", [None, "fr", "", "  EN  "])
def test_t_unknown_or_messy_language_falls_back_to_english(lang):
    key = next(k for k, v in TRANSLATIONS.items() if "en" in v)
    assert t(key, lang) == TRANSLATIONS[key]["en"]


def test_t_unknown_key_returns_key():
    assert t("definitely_not_a_key", "mr") == "definitely_not_a_key"


def test_t_formats_parameters_and_survives_missing_ones():
    key, entry = next(
        (k, v) for k, v in TRANSLATIONS.items() if "{" in (v.get("en") or "")
    )
    # Missing kwargs must not raise; the raw template comes back.
    assert t(key, "en", unrelated="x") == entry["en"]


def test_every_translation_has_all_supported_languages():
    missing = [
        (key, lang)
        for key, entry in TRANSLATIONS.items()
        for lang in SUPPORTED_LANGUAGES
        if not entry.get(lang)
    ]
    assert missing == []


# --- language detection ----------------------------------------------------

@pytest.mark.parametrize(
    "text", ["भाषा", "  Language ", "change language", "bhasha badla", "भाषा बदला"]
)
def test_is_language_command_accepts_known_commands(text):
    assert is_language_command(text) is True


@pytest.mark.parametrize("text", ["language please", "hello", "", "बिल"])
def test_is_language_command_rejects_other_text(text):
    assert is_language_command(text) is False


@pytest.mark.parametrize(
    "text, lang",
    [
        ("", "mr"),
        ("What is pending?", "en"),
        ("काय बाकी आहे?", "mr"),
        ("क्या बाकी है? बताओ", "hi"),
        ("बिजली का बिल कब है", "hi"),
    ],
)
def test_detect_language(text, lang):
    assert detect_language(text) == lang


# --- quiet hours -----------------------------------------------------------

def member(tz="Asia/Kolkata", start=22, end=7):
    return SimpleNamespace(timezone=tz, quiet_hours_start=start, quiet_hours_end=end)


@pytest.mark.parametrize(
    "hour, quiet",
    [(21, False), (22, True), (23, True), (0, True), (6, True), (7, False), (12, False)],
)
def test_quiet_hours_overnight_window(hour, quiet):
    now = datetime(2026, 11, 4, hour, 0, tzinfo=IST)
    assert is_in_quiet_hours(member(), now) is quiet


@pytest.mark.parametrize("hour, quiet", [(12, False), (13, True), (14, True), (15, False)])
def test_quiet_hours_daytime_window(hour, quiet):
    now = datetime(2026, 11, 4, hour, 0, tzinfo=IST)
    assert is_in_quiet_hours(member(start=13, end=15), now) is quiet


def test_quiet_hours_equal_start_and_end_means_never_quiet():
    now = datetime(2026, 11, 4, 3, 0, tzinfo=IST)
    assert is_in_quiet_hours(member(start=5, end=5), now) is False


def test_quiet_hours_use_the_members_own_timezone():
    # 12:30 IST = 07:00 UTC = 02:00 in New York (EST in November): quiet there.
    now = datetime(2026, 11, 4, 12, 30, tzinfo=IST)
    assert is_in_quiet_hours(member(), now) is False
    assert is_in_quiet_hours(member(tz="America/New_York"), now) is True


def test_quiet_hours_naive_datetime_is_treated_as_ist():
    assert is_in_quiet_hours(member(), datetime(2026, 11, 4, 23, 0)) is True
    assert is_in_quiet_hours(member(), datetime(2026, 11, 4, 12, 0)) is False


def test_quiet_hours_defaults_when_member_fields_are_missing():
    m = SimpleNamespace(timezone=None, quiet_hours_start=None, quiet_hours_end=None)
    assert is_in_quiet_hours(m, datetime(2026, 11, 4, 23, 0, tzinfo=IST)) is True
    assert is_in_quiet_hours(m, datetime(2026, 11, 4, 10, 0, tzinfo=IST)) is False


def test_quiet_hours_invalid_timezone_falls_back_to_ist():
    now = datetime(2026, 11, 4, 23, 0, tzinfo=IST)
    assert is_in_quiet_hours(member(tz="Not/AZone"), now) is True


def test_get_ist_now_is_utc_plus_530():
    assert get_ist_now().utcoffset() == timedelta(hours=5, minutes=30)


# --- webhook helpers -------------------------------------------------------

@pytest.mark.parametrize(
    "value, expected",
    [("line1\nline2", "line1 line2"), ("a\r\n\r\nb", "a b"), (None, ""), (1840, "1840"), ("  x  ", "x")],
)
def test_clean_template_param_removes_line_breaks(value, expected):
    assert _clean_template_param(value) == expected


@pytest.fixture
def no_llm(monkeypatch):
    monkeypatch.setattr(webhooks.settings, "llm_api_key", "")


@pytest.mark.parametrize(
    "text", ["काय बाकी आहे?", "कोणती कामे बाकी", "What is pending", "status", "बाकी?", "pending?"]
)
async def test_is_status_query_recognises_questions(no_llm, text):
    assert await _is_status_query(text) is True


@pytest.mark.parametrize(
    "text",
    ["महावितरण बाकी रक्कम ₹1,840", "Rs 500 due date 10 Nov", "नमस्कार", "electricity bill"],
)
async def test_is_status_query_treats_bills_and_chat_as_not_status(no_llm, text):
    assert await _is_status_query(text) is False
