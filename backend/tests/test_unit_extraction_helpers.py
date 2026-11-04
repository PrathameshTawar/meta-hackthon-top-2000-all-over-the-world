"""Unit tests for the pure text helpers in app.agent.nodes (no DB, no LLM)."""
import pytest

from app.agent.nodes import (
    _confirmation_question,
    _find_date,
    _heuristic_extract,
    _humanize_failure,
    _is_scam_message,
    _match_vitals_pattern,
    norm,
    normalize_payee,
    to_amount,
)


# --- norm ------------------------------------------------------------------

def test_norm_collapses_whitespace_and_strips_zero_width_chars():
    assert norm("  a​ b \n\t c﻿ ") == "a b c"


def test_norm_applies_nfc_normalisation():
    decomposed = "é"  # e + combining acute
    assert norm(decomposed) == "é"


# --- to_amount -------------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("₹1,840", 1840.0),
        ("₹१,८४०", 1840.0),  # Devanagari digits
        ("Rs. 1,234.50", 1234.5),
        ("INR 99", 99.0),
        (500, 500.0),
        ("१५०० रुपये", 1500.0),
    ],
)
def test_to_amount_parses_numbers(raw, expected):
    assert to_amount(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "no digits here"])
def test_to_amount_returns_none_without_digits(raw):
    assert to_amount(raw) is None


# --- normalize_payee -------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("MSEDCL office", "Mahavitaran (MSEDCL)"),
        ("msedcl", "Mahavitaran (MSEDCL)"),
        ("महावितरण कार्यालय", "Mahavitaran (MSEDCL)"),
        ("Tata Power Mumbai", "Tata Power"),
        ("MGL", "Mahanagar Gas Limited"),
    ],
)
def test_normalize_payee_maps_known_payees(raw, expected):
    assert normalize_payee(raw) == expected


def test_normalize_payee_uses_word_boundaries_for_latin_names():
    # "mgl" inside another word must not match Mahanagar Gas
    assert normalize_payee("Smgl Traders") == "Smgl Traders"


def test_normalize_payee_keeps_unknown_payees_trimmed():
    assert normalize_payee("  Corner Shop  ") == "Corner Shop"
    assert normalize_payee("") == ""


# --- _is_scam_message ------------------------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "Please share your OTP",
        "Update KYC today",
        "Your account is blocked, click here",
        "account suspended",
        "ओटीपी सांगा",
        "तुमचे खाते बंद होईल",
    ],
)
def test_is_scam_message_flags_fraud_signals(text):
    assert _is_scam_message(text) is True


@pytest.mark.parametrize("text", ["", "महावितरण वीज बिल ₹1,840", "botpress invoice", "kycx"])
def test_is_scam_message_ignores_normal_text(text):
    assert _is_scam_message(text) is False


# --- _find_date ------------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected",
    [
        ("due 2026-11-10", ("2026-11-10T00:00:00", "2026-11-10")),
        ("due 2026/1/5", ("2026-01-05T00:00:00", "2026/1/5")),
        ("३ नोव्हेंबर २०२६ पर्यंत", ("2026-11-03T00:00:00", "३ नोव्हेंबर २०२६")),
        ("10 नोव्हेंबर 2027", ("2027-11-10T00:00:00", "10 नोव्हेंबर 2027")),
        ("pay by 15th November 2026", ("2026-11-15T00:00:00", "15th November 2026")),
        ("pay by 1 Dec 2026", ("2026-12-01T00:00:00", "1 Dec 2026")),
    ],
)
def test_find_date_parses_supported_formats(text, expected):
    assert _find_date(text) == expected


def test_find_date_quote_is_verbatim_substring():
    text = "देय तारीख ३ नोव्हेंबर २०२६ आहे"
    _, quote = _find_date(text)
    assert quote in text


def test_find_date_returns_none_without_a_date():
    assert _find_date("no date in this message") is None


@pytest.mark.xfail(strict=True, reason="BUG: 'मे' (May) matches the start of 'मेन्टेनन्स' (maintenance)")
def test_find_date_does_not_read_maintenance_as_may():
    assert _find_date("भरा 10 मेन्टेनन्स") is None


@pytest.mark.xfail(strict=True, reason="BUG: English month prefix matches any word, e.g. 'dec' in 'decimal'")
def test_find_date_does_not_read_decimal_as_december():
    assert _find_date("round to 2 decimal places") is None


@pytest.mark.xfail(strict=True, reason="BUG: missing year is hard-coded to 2026 instead of the current/next year")
def test_find_date_without_year_is_not_hard_coded_to_2026(monkeypatch):
    import datetime as real_dt
    import app.agent.nodes as nodes

    class FakeDate(real_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2027, 6, 1, tzinfo=tz)

    monkeypatch.setattr(nodes, "datetime", FakeDate, raising=False)
    value, _ = _find_date("10 नोव्हेंबर")
    assert value.startswith("2027-")


# --- _heuristic_extract ----------------------------------------------------

MSEDCL_BILL = (
    "महावितरण वीज बिल\n"
    "रक्कम ₹1,840\n"
    "देय तारीख 10 नोव्हेंबर 2026\n"
    "ग्राहक क्रमांक 170012345678"
)


def test_heuristic_extract_reads_a_marathi_electricity_bill():
    out = _heuristic_extract(MSEDCL_BILL)
    assert out["amount"] == {"value": "₹1,840", "quote": "₹1,840"}
    assert out["due_date"]["value"] == "2026-11-10T00:00:00"
    assert out["payee"]["value"] == "Mahavitaran (MSEDCL)"
    assert out["consumer_number"]["value"] == "170012345678"
    assert out["title"]["value"] == "Mahavitaran (MSEDCL) Electricity Bill"


def test_heuristic_extract_every_quote_is_verbatim():
    out = _heuristic_extract(MSEDCL_BILL)
    for field, item in out.items():
        if item["quote"]:
            assert item["quote"] in MSEDCL_BILL, field


def test_heuristic_extract_formats_decimal_amounts():
    out = _heuristic_extract("Premium Rs. 1,234.50 due 2026-12-01")
    assert out["amount"]["value"] == "₹1,234.50"


def test_heuristic_extract_reads_devanagari_rupees():
    out = _heuristic_extract("लाईट बिल १५०० रुपये")
    assert out["amount"]["value"] == "₹1,500"


def test_heuristic_extract_falls_back_to_first_line_for_unknown_payee():
    out = _heuristic_extract("Sharma Society\nAmount Rs 2,400")
    assert out["payee"]["value"] == "Sharma Society"
    assert out["consumer_number"] == {"value": None, "quote": None}


@pytest.mark.parametrize(
    "text, suffix",
    [
        ("HDFC Credila loan EMI Rs 5000", "Loan EMI"),
        ("LIC insurance renewal Rs 5000", "Insurance Renewal"),
        ("Hospital appointment on 2026-11-20", "Doctor Appointment"),
        ("Pension life certificate due 2026-11-30", "Pension Life Certificate"),
    ],
)
def test_heuristic_extract_titles_by_category(text, suffix):
    assert _heuristic_extract(text)["title"]["value"].endswith(suffix)


@pytest.mark.xfail(strict=True, reason="BUG: substring 'emi' inside 'premium' makes insurance look like a loan EMI")
def test_heuristic_extract_insurance_premium_is_not_a_loan():
    title = _heuristic_extract("LIC insurance premium Rs 5000")["title"]["value"]
    assert title.endswith("Insurance Renewal")


def test_heuristic_extract_handles_text_with_nothing_to_extract():
    out = _heuristic_extract("ok")
    assert out["amount"]["value"] is None
    assert out["due_date"]["value"] is None
    assert out["payee"]["value"] is None  # first line too short


# --- _match_vitals_pattern -------------------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "BP 140/90",
        "आज बीपी १५०/९५ आहे",
        "रक्तदाब १२० वर ८०",
        "sugar 180",
        "साखर उपाशीपोटी ११०",
        "weight 72 kg",
        "वजन ७२ किलो",
        "spo2 96",
        "pulse 78",
        "नाडी ७८",
        "temp 99.4",
    ],
)
def test_match_vitals_pattern_detects_readings(text):
    assert _match_vitals_pattern(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "महावितरण बिल 140/90",  # slash numbers without a BP keyword
        "Electricity bill Rs 1840",
        "नमस्कार",
        "",
    ],
)
def test_match_vitals_pattern_ignores_non_vitals(text):
    assert _match_vitals_pattern(text) is False


# --- _confirmation_question ------------------------------------------------

def test_confirmation_question_fits_in_60_chars():
    q = _confirmation_question(_heuristic_extract(MSEDCL_BILL))
    assert len(q) <= 60
    assert q.endswith("Is this right?")


def test_confirmation_question_uses_placeholders_for_missing_fields():
    assert _confirmation_question({}) == "Please check: ? | ? | due ?. Is this right?"


@pytest.mark.xfail(strict=True, reason="BUG: truncation cuts the due date off when the payee name is long")
def test_confirmation_question_keeps_the_due_date_visible():
    q = _confirmation_question(_heuristic_extract(MSEDCL_BILL))
    assert "2026-11-10" in q


# --- _humanize_failure -----------------------------------------------------

@pytest.mark.parametrize(
    "failure, expected",
    [
        ("amount: quote not found verbatim", "couldn't find amount on the document"),
        ("due_date '2020-01-01' is in the past", "the due date 2020-01-01 has already passed"),
        ("due_date 'abc' is not a valid ISO date", "the due date abc is not a valid date"),
        ("amount digits 1840 not in quote", "the amount doesn't match the document"),
        ("payee quote mismatch", "payee mismatch"),
        ("quote verbatim", "some extracted details need verification"),
    ],
)
def test_humanize_failure(failure, expected):
    assert _humanize_failure(failure) == expected
