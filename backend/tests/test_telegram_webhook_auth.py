import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings

# Make root bot module importable
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot.bot import build_forward_request

client = TestClient(app)


def test_telegram_webhook_rejects_when_secret_unset(monkeypatch):
    monkeypatch.setattr(settings, "telegram_webhook_secret", "")
    res = client.post(
        "/webhook/telegram",
        json={"update_id": 1001},
        headers={"X-Telegram-Bot-Api-Secret-Token": "any_secret"},
    )
    assert res.status_code == 403
    assert "Invalid or missing" in res.json().get("detail", "") or "secret" in res.json().get("detail", "").lower()


def test_telegram_webhook_rejects_wrong_secret(monkeypatch):
    monkeypatch.setattr(settings, "telegram_webhook_secret", "expected_secret_123")
    res = client.post(
        "/webhook/telegram",
        json={"update_id": 1002},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong_secret_456"},
    )
    assert res.status_code == 403


def test_telegram_webhook_accepts_correct_secret(monkeypatch):
    monkeypatch.setattr(settings, "telegram_webhook_secret", "expected_secret_123")
    res = client.post(
        "/webhook/telegram",
        json={"update_id": 1003},
        headers={"X-Telegram-Bot-Api-Secret-Token": "expected_secret_123"},
    )
    assert res.status_code == 200
    assert res.json().get("ok") is True


def test_bot_forwarding_helper_includes_secret_header():
    update = {"update_id": 9999, "message": {"text": "hello"}}
    req_url, req_json, req_headers = build_forward_request(
        update=update,
        backend_url="http://test-backend:8000",
        webhook_secret="my_secure_secret",
    )
    assert req_url == "http://test-backend:8000/webhook/telegram"
    assert req_json == update
    assert req_headers.get("X-Telegram-Bot-Api-Secret-Token") == "my_secure_secret"

