import pytest
import uuid
from app.db.session import AsyncSessionLocal
from app.db.models import Household, Member, MemberRole
from app.agent.nodes import node_scam_guardrail
import app.agent.nodes as nodes_module


def unique_phone():
    return f"+9198{uuid.uuid4().int % 100000000:08d}"


@pytest.mark.asyncio
async def test_scam_guardrail_names_actual_child_priya(monkeypatch):
    """Household with a child named Priya -> reply names Priya, not Rohan."""
    notified = []

    async def mock_notify(**kwargs):
        notified.append(kwargs)

    monkeypatch.setattr(nodes_module, "notify", mock_notify)

    async with AsyncSessionLocal() as db:
        hh = Household(name="Priya Family", primary_language="en")
        db.add(hh)
        await db.commit()
        await db.refresh(hh)

        priya = Member(
            household_id=hh.id,
            name="Priya",
            role=MemberRole.child,
            phone=unique_phone(),
        )
        db.add(priya)
        await db.commit()
        hh_id = hh.id

    state = {
        "raw_text": "Dear customer, your bank account is blocked. Share OTP immediately.",
        "household_id": hh_id,
    }
    res = await node_scam_guardrail(state)
    assert "Priya" in res["parent_reply"]
    assert "Rohan" not in res["parent_reply"]
    assert len(notified) == 1
    assert notified[0]["member"].name == "Priya"


@pytest.mark.asyncio
async def test_scam_guardrail_fallback_when_no_children(monkeypatch):
    """Household with no children -> reply uses 'please call' message, never claims sibling was alerted."""
    notified = []

    async def mock_notify(**kwargs):
        notified.append(kwargs)

    monkeypatch.setattr(nodes_module, "notify", mock_notify)

    async with AsyncSessionLocal() as db:
        hh = Household(name="Solo Parent Family", primary_language="en")
        db.add(hh)
        await db.commit()
        await db.refresh(hh)

        parent = Member(
            household_id=hh.id,
            name="Aai",
            role=MemberRole.parent,
            phone=unique_phone(),
        )
        db.add(parent)
        await db.commit()
        hh_id = hh.id

    state = {
        "raw_text": "Dear customer, KYC verification pending. Send OTP.",
        "household_id": hh_id,
    }
    res = await node_scam_guardrail(state)
    assert len(notified) == 0
    assert "Please call your son or daughter before replying" in res["parent_reply"]
    assert "Rohan" not in res["parent_reply"]


@pytest.mark.asyncio
async def test_scam_guardrail_fallback_when_all_notifies_fail(monkeypatch):
    """If notify raises for all children -> reply falls back to 'please call' message."""
    async def failing_notify(**kwargs):
        raise RuntimeError("Network failure to WhatsApp API")

    monkeypatch.setattr(nodes_module, "notify", failing_notify)

    async with AsyncSessionLocal() as db:
        hh = Household(name="Failing Network Family", primary_language="en")
        db.add(hh)
        await db.commit()
        await db.refresh(hh)

        child = Member(
            household_id=hh.id,
            name="Amit",
            role=MemberRole.child,
            phone=unique_phone(),
        )
        db.add(child)
        await db.commit()
        hh_id = hh.id

    state = {
        "raw_text": "Account suspended. Share OTP to reactivate.",
        "household_id": hh_id,
    }
    res = await node_scam_guardrail(state)
    assert "Please call your son or daughter before replying" in res["parent_reply"]
    assert "Amit" not in res["parent_reply"]
    assert "Rohan" not in res["parent_reply"]
