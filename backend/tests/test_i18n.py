import pytest
import uuid
import hmac
import hashlib
import json
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings
from app.db.models import Household, Member, MemberRole
from app.db.session import AsyncSessionLocal, init_db
from app.core.i18n import t, detect_language, is_language_command


def test_i18n_translation_keys():
    """Verify single-script translations across en, mr, and hi."""
    # Button texts
    assert t("btn_claim", "en") == "Claim Task"
    assert t("btn_claim", "mr") == "मी करतो"
    assert t("btn_claim", "hi") == "मैं करता हूँ"

    assert t("btn_done", "en") == "Mark Done"
    assert t("btn_done", "mr") == "पूर्ण झाले"
    assert t("btn_done", "hi") == "पूर्ण हुआ"

    assert t("btn_correct", "en") == "Correct"
    assert t("btn_correct", "mr") == "बरोबर"
    assert t("btn_correct", "hi") == "सही"

    # Formatting
    msg_en = t("task_claimed_ack", "en", task_id=42, title="MSEB Bill")
    assert "Task #42" in msg_en
    assert "MSEB Bill" in msg_en


def test_i18n_language_detection():
    """Verify detection of English, Marathi, and Hindi."""
    assert detect_language("Please pay the MSEB electricity bill before Friday") == "en"
    assert detect_language("आज लाईट बिल भरले का?") == "mr"
    assert detect_language("आज बिजली का बिल भरा क्या?") == "hi"


def test_is_language_command():
    """Verify triggering of the language selection command."""
    assert is_language_command("language") is True
    assert is_language_command("भाषा") is True
    assert is_language_command("भाषा बदला") is True
    assert is_language_command("change language") is True
    assert is_language_command("लाइट बिल 1200") is False


@pytest.mark.asyncio
async def test_member_language_api():
    """Verify PATCH /members/{id}/language updates member preference."""
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        phone = f"+919{uuid.uuid4().int % 1000000000:09d}"
        async with AsyncSessionLocal() as db:
            hh = Household(name="Test I18N Household")
            db.add(hh)
            await db.commit()
            await db.refresh(hh)

            member = Member(
                household_id=hh.id,
                name="Rohan Test",
                role=MemberRole.child,
                telegram_id=f"tg_{uuid.uuid4().hex[:8]}",
                phone=phone,
                language="en",
            )
            db.add(member)
            await db.commit()
            await db.refresh(member)
            member_id = member.id

        headers = {"X-Admin-Token": settings.admin_secret or "saath_admin_secret_demo"}
        # Valid change to Hindi
        resp = await client.patch(f"/members/{member_id}/language", json={"language": "hi"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["language"] == "hi"

        # Valid change to Marathi
        resp = await client.patch(f"/members/{member_id}/language", json={"language": "mr"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["language"] == "mr"

        # Invalid language code
        resp = await client.patch(f"/members/{member_id}/language", json={"language": "fr"}, headers=headers)
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_webhook_language_switch(monkeypatch):
    """Verify sending 'language' on WhatsApp replies with language options and tap switches language."""
    await init_db()
    secret = "test_whatsapp_secret_key"
    monkeypatch.setattr(settings, "whatsapp_app_secret", secret)

    sent_messages = []

    async def mock_send_wa(to, text, buttons=None, **kwargs):
        sent_messages.append({"to": to, "text": text, "buttons": buttons})

    monkeypatch.setattr("app.api.webhooks._send_whatsapp_message", mock_send_wa)

    phone_clean = f"919{uuid.uuid4().int % 1000000000:09d}"
    phone_plus = f"+{phone_clean}"

    async with AsyncSessionLocal() as db:
        hh = Household(name="Test WA Lang Household")
        db.add(hh)
        await db.commit()
        await db.refresh(hh)

        member = Member(
            household_id=hh.id,
            name="Priya WA",
            role=MemberRole.child,
            phone=phone_plus,
            language="mr",
        )
        db.add(member)
        await db.commit()
        await db.refresh(member)
        member_id = member.id

    def make_signed_request(payload: dict) -> tuple[bytes, dict]:
        raw_b = json.dumps(payload).encode("utf-8")
        sig = "sha256=" + hmac.new(secret.encode("utf-8"), raw_b, hashlib.sha256).hexdigest()
        return raw_b, {"X-Hub-Signature-256": sig, "Content-Type": "application/json"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Send 'language' command
        payload_msg = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "id": f"wamid.{uuid.uuid4().hex[:10]}",
                            "from": phone_clean,
                            "type": "text",
                            "text": {"body": "language"}
                        }]
                    }
                }]
            }]
        }
        sent_messages.clear()
        content, headers = make_signed_request(payload_msg)
        resp = await client.post("/chat/webhook", content=content, headers=headers)
        assert resp.status_code == 200
        assert len(sent_messages) == 1
        buttons = sent_messages[0]["buttons"]
        assert len(buttons) == 3
        assert buttons[0]["id"] == "lang:mr"
        assert buttons[1]["id"] == "lang:hi"
        assert buttons[2]["id"] == "lang:en"

        # 2. Tap 'English' button (id: lang:en)
        payload_tap = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "id": f"wamid.{uuid.uuid4().hex[:10]}",
                            "from": phone_clean,
                            "type": "interactive",
                            "interactive": {
                                "type": "button_reply",
                                "button_reply": {"id": "lang:en", "title": "English"}
                            }
                        }]
                    }
                }]
            }]
        }
        sent_messages.clear()
        content, headers = make_signed_request(payload_tap)
        resp = await client.post("/chat/webhook", content=content, headers=headers)
        assert resp.status_code == 200
        assert len(sent_messages) == 1
        assert "Language set to English" in sent_messages[0]["text"]

    # Verify updated in DB
    async with AsyncSessionLocal() as db:
        updated_member = await db.get(Member, member_id)
        assert updated_member.language == "en"
