import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.agent.nodes import node_perceive
from app.db.session import AsyncSessionLocal
from app.db.models import Household, Event

client = TestClient(app)
VALID_HEADERS = {"X-Admin-Token": settings.admin_secret or "saath_test_admin_secret"}


@pytest.mark.asyncio
async def test_http_url_rejected_and_no_request_made(monkeypatch):
    """http(s) URLs must be rejected in node_perceive without making any HTTP request."""
    # Ensure no network call can succeed
    async def mock_fail_client(*args, **kwargs):
        raise AssertionError("httpx client was called on an unauthorized URL!")

    monkeypatch.setattr("httpx.AsyncClient", mock_fail_client)

    state = {
        "file_url": "http://127.0.0.1:8000/latest/meta-data/iam",
        "artifact_type": "image",
        "household_id": 99999,
        "raw_text": "",
    }
    res = await node_perceive(state)
    # The file bytes must be empty or None, no exception raised, no network hit
    assert res.get("raw_text") == ""


@pytest.mark.asyncio
async def test_arbitrary_local_file_rejected():
    """Arbitrary system paths like /etc/hostname or .env must be rejected."""
    state = {
        "file_url": os.path.abspath(".env"),
        "artifact_type": "image",
        "household_id": 99999,
        "raw_text": "",
    }
    res = await node_perceive(state)
    assert res.get("raw_text") == ""


@pytest.mark.asyncio
async def test_eval_set_file_allowed_in_dev_and_rejected_in_prod(monkeypatch):
    """Files inside tests/eval_set/ are readable in dev/eval, but blocked in production."""
    import app.agent.nodes as nodes_module

    class MockResp:
        choices = [type("Choice", (), {"message": type("Msg", (), {"content": "EXTRACTED TEXT FROM LOCAL FILE"})()})]

    class MockCompletions:
        async def create(self, *args, **kwargs):
            return MockResp()

    class MockClient:
        chat = type("Chat", (), {"completions": MockCompletions()})

    monkeypatch.setattr(nodes_module, "get_openai_client", lambda: MockClient())

    eval_dir = Path(__file__).parent / "eval_set"
    eval_dir.mkdir(parents=True, exist_ok=True)
    test_file = eval_dir / "test_dummy_bill.png"
    test_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

    try:
        # Development: allowed
        monkeypatch.setattr(settings, "environment", "development")
        state_dev = {
            "file_url": str(test_file),
            "artifact_type": "image",
            "household_id": 99999,
            "raw_text": "",
        }
        res_dev = await node_perceive(state_dev)
        assert res_dev.get("raw_text") == "EXTRACTED TEXT FROM LOCAL FILE"

        # Production: blocked
        monkeypatch.setattr(settings, "environment", "production")
        state_prod = {
            "file_url": str(test_file),
            "artifact_type": "image",
            "household_id": 99999,
            "raw_text": "",
        }
        res_prod = await node_perceive(state_prod)
        assert res_prod.get("raw_text") == ""
    finally:
        if test_file.exists():
            test_file.unlink()


def test_simulate_ingest_validates_file_url():
    """POST /admin/ingest/simulate rejects arbitrary HTTP URLs and accepts allowed schemes."""
    # Bad URL -> 422
    res_bad = client.post(
        "/admin/ingest/simulate",
        json={
            "household_id": 1,
            "type": "image",
            "raw_text": "Test",
            "file_url": "http://169.254.169.254/latest/meta-data",
        },
        headers=VALID_HEADERS,
    )
    assert res_bad.status_code == 422

    # Allowed simulate:// scheme -> 200
    res_good = client.post(
        "/admin/ingest/simulate",
        json={
            "household_id": 1,
            "type": "image",
            "raw_text": "Test",
            "file_url": "simulate://sample_bill",
        },
        headers=VALID_HEADERS,
    )
    assert res_good.status_code == 200
