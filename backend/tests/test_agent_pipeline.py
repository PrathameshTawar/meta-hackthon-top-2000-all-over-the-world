import asyncio
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select

from app.db.session import init_db, AsyncSessionLocal
from app.db.seed import seed_data
from app.db.models import Artifact, ArtifactType, Task, Evidence, TaskCategory, TaskStatus
from app.agent.state import AgentState
from app.agent.nodes import (
    node_perceive,
    node_classify,
    node_guardrail,
    node_extract,
    node_verify,
    node_deduplicate,
    GUARDRAIL_REPLY,
    get_current_ist_datetime,
)


@pytest.mark.asyncio
async def test_mgl_gas_bill_not_medical():
    """
    Regression test for the 'mg' bug:
    Mahanagar Gas Limited (MGL) bills contain 'MGL' and 'Gas', but must NEVER
    be classified as TaskCategory.medical.
    """
    state: AgentState = {
        "artifact_id": 1,
        "household_id": 1,
        "artifact_type": "image",
        "file_url": "test://mgl_bill.png",
        "raw_text": (
            "MAHANAGAR GAS LIMITED (MGL)\n"
            "Domestic Piped Gas Bill\n"
            "Customer No: 98124019\n"
            "Due Date: 2026-11-20\n"
            "Total Amount: ₹890\n"
            "Mahanagar Gas Limited"
        ),
        "errors": [],
    }
    c_res = await node_classify(state)
    assert c_res["category"] == TaskCategory.bill.value, (
        f"Expected category 'bill', but got '{c_res['category']}'. 'MGL' must not trigger medical guardrail!"
    )


@pytest.mark.asyncio
async def test_medical_guardrail_refusal_and_dosage_regex():
    """
    Test that a clinical prescription with '500 mg' triggers TaskCategory.medical,
    and node_guardrail strictly refuses interpretation without diagnostic advice.
    """
    state: AgentState = {
        "artifact_id": 2,
        "household_id": 1,
        "artifact_type": "image",
        "file_url": "test://prescription.png",
        "raw_text": (
            "Ruby Hall Clinic Pune\n"
            "Prescription Slip - Dr. A. Joshi\n"
            "Date: 2026-11-12\n"
            "Rx: Tablet Metformin 500 mg twice daily after meals.\n"
            "Next follow up after 15 days."
        ),
        "errors": [],
    }
    c_res = await node_classify(state)
    state.update(c_res)
    assert state["category"] == TaskCategory.medical.value

    g_res = await node_guardrail(state)
    state.update(g_res)
    assert state["parent_reply"] == GUARDRAIL_REPLY
    # Verify no interpretation of tablet dosage was stored as a bill amount
    assert state.get("extracted", {}).get("amount", {}).get("value") is None


@pytest.mark.asyncio
async def test_verbatim_quote_verification():
    """
    Test that code-based verification fails if an extracted quote is not
    an exact verbatim substring of the raw source text.
    """
    state: AgentState = {
        "raw_text": "Mahavitaran Bill Due 2026-11-15 Amount ₹1,500",
        "extracted": {
            "amount": {"value": "₹1,500", "quote": "Amount ₹1,500"},
            # Altered quote that does NOT exist in raw_text
            "payee": {"value": "Mahavitaran", "quote": "Tata Power Corporation"},
        },
        "confidence": 0.8,
    }
    v_res = await node_verify(state)
    assert v_res["verify_passed"] is False
    assert any("quote not found verbatim" in f for f in v_res["verify_failures"])


@pytest.mark.asyncio
async def test_due_date_future_check_ist():
    """
    Test that past due dates are flagged by node_verify using India Standard Time.
    """
    now_ist = get_current_ist_datetime()
    past_date = (now_ist - timedelta(days=5)).strftime("%Y-%m-%d")
    future_date = (now_ist + timedelta(days=10)).strftime("%Y-%m-%d")

    # Past date
    state_past: AgentState = {
        "raw_text": f"Bill due on {past_date} for ₹500",
        "extracted": {
            "due_date": {"value": past_date, "quote": past_date},
            "amount": {"value": "₹500", "quote": "₹500"},
        },
        "confidence": 0.8,
    }
    v_past = await node_verify(state_past)
    assert v_past["verify_passed"] is False
    assert any("is in the past" in f for f in v_past["verify_failures"])

    # Future date
    state_future: AgentState = {
        "raw_text": f"Bill due on {future_date} for ₹500",
        "extracted": {
            "due_date": {"value": future_date, "quote": future_date},
            "amount": {"value": "₹500", "quote": "₹500"},
        },
        "confidence": 0.8,
    }
    v_future = await node_verify(state_future)
    assert v_future["verify_passed"] is True


@pytest.mark.asyncio
async def test_cross_lingual_deduplication():
    """
    Test that an English bill and Marathi voice note for the same payee and amount
    generate identical dedupe keys and merge into a single task.
    """
    state_eng: AgentState = {
        "household_id": 1,
        "extracted": {
            "payee": {"value": "Mahavitaran (MSEDCL)"},
            "amount": {"value": "₹1,840"},
            "due_date": {"value": "2026-11-03"},
        },
    }
    d_eng = await node_deduplicate(state_eng)

    state_mar: AgentState = {
        "household_id": 1,
        "extracted": {
            "payee": {"value": "महावितरण वीज बिल"},
            "amount": {"value": "1,840 रुपये"},
            "due_date": {"value": "2026-11-03"},
        },
    }
    d_mar = await node_deduplicate(state_mar)

    assert d_eng["dedupe_key"] == d_mar["dedupe_key"], (
        f"Dedupe keys must match across Marathi and English: {d_eng['dedupe_key']} vs {d_mar['dedupe_key']}"
    )
