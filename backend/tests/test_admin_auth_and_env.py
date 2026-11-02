import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings

client = TestClient(app)


def test_admin_routes_return_503_when_admin_secret_unset(monkeypatch):
    monkeypatch.setattr(settings, "admin_secret", "")
    res = client.post("/admin/reset", headers={"X-Admin-Token": "some_token"})
    assert res.status_code == 503
    assert "ADMIN_SECRET not configured" in res.json().get("detail", "")


def test_production_environment_blocks_destructive_reset_routes(monkeypatch):
    monkeypatch.setattr(settings, "admin_secret", "secret_123")
    monkeypatch.setattr(settings, "environment", "production")
    headers = {"X-Admin-Token": "secret_123"}

    res = client.post("/admin/reset", headers=headers)
    assert res.status_code == 403
    assert "disabled in production" in res.json().get("detail", "").lower()

    res_db = client.post("/admin/reset-db", headers=headers)
    assert res_db.status_code == 403

    res_seed = client.post("/admin/seed", headers=headers)
    assert res_seed.status_code == 403


def test_development_environment_allows_reset_with_valid_token(monkeypatch):
    monkeypatch.setattr(settings, "admin_secret", "dev_secret_999")
    monkeypatch.setattr(settings, "environment", "development")
    headers = {"X-Admin-Token": "dev_secret_999"}

    res = client.post("/admin/seed", headers=headers)
    assert res.status_code == 200
    assert res.json().get("status") == "ok"

