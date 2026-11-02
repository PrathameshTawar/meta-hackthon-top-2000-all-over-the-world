import os
import tempfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

# Set up isolated test DB and admin secret before importing app
_tmpdir = tempfile.mkdtemp(prefix="saath_auth_test_")
_test_db = Path(_tmpdir) / "test_auth.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_test_db.as_posix()}"
os.environ["ADMIN_SECRET"] = "test_auth_secret_xyz"

from app.main import app
from app.config import settings

settings.admin_secret = "test_auth_secret_xyz"

client = TestClient(app)
VALID_HEADERS = {"X-Admin-Token": "test_auth_secret_xyz"}


def test_unauthenticated_members_routes_fail():
    # GET /members/1
    res = client.get("/members/1")
    assert res.status_code == 401

    # POST /members/
    attacker_payload = {
        "household_id": 1,
        "name": "Attacker",
        "role": "child",
        "phone": "+919999999999",
    }
    res_post = client.post("/members/", json=attacker_payload)
    assert res_post.status_code == 401


def test_unauthenticated_households_routes_fail():
    res = client.get("/households/1")
    assert res.status_code == 401


def test_unauthenticated_events_routes_fail():
    res = client.get("/events/1")
    assert res.status_code == 401


def test_unauthenticated_artifacts_routes_fail():
    res = client.get("/artifacts/1")
    assert res.status_code == 401


def test_authenticated_members_route_succeeds():
    res = client.get("/members/1", headers=VALID_HEADERS)
    assert res.status_code in (200, 404)


EXCLUDED_PATHS = {
    "/healthz",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/docs/oauth2-redirect",
}

def is_exempt(path: str) -> bool:
    if path in EXCLUDED_PATHS:
        return True
    if path.startswith("/webhook"):
        return True
    return False


def test_all_non_webhook_routes_require_auth():
    """Assert every route except webhooks and docs rejects unauthenticated requests."""
    unprotected = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            path = route.path
            if is_exempt(path):
                continue
            methods = [m for m in route.methods if m not in ("OPTIONS", "HEAD")]
            for method in methods:
                # Test with dummy path parameters resolved (e.g. {household_id} -> 1)
                test_path = path.replace("{household_id}", "1").replace("{member_id}", "1").replace("{task_id}", "1").replace("{artifact_id}", "1")
                res = client.request(method, test_path)
                if res.status_code not in (401, 403, 503):
                    unprotected.append((method, path, res.status_code))

    assert not unprotected, f"Unprotected non-webhook routes found: {unprotected}"
