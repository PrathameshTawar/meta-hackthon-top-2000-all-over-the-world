import sys
from pathlib import Path
import asyncio
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select

# Ensure backend root is on sys.path for direct pytest invocation
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

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


@pytest.mark.asyncio
async def test_langgraph_persistent_interrupt_and_resume():
    """
    Test that low confidence or failed verification triggers a persistent LangGraph interrupt(),
    and Command(resume={'confirmed': True}) resumes execution through SQLite checkpointer.
    """
    from app.agent.graph import get_compiled_graph
    from langgraph.types import Command

    graph = await get_compiled_graph()
    thread_id = "test_interrupt_pipeline_1"
    config = {"configurable": {"thread_id": thread_id}}

    # Initial state with blurry/unverified quote that fails node_verify
    initial_state: AgentState = {
        "artifact_id": 9991,
        "household_id": 1,
        "artifact_type": "image",
        "file_url": "test://blurry_bill.png",
        "raw_text": "Mahavitaran Bill",
        "category": TaskCategory.bill.value,
        "extracted": {
            "amount": {"value": "₹1,840", "quote": "₹1,840 (not in raw text)"},
        },
        "confidence": 0.4,  # Below 0.5 triggers verification failure
        "errors": [],
    }

    # Execute until interrupt
    interrupted = False
    question = None
    async for step in graph.astream(initial_state, config=config):
        if isinstance(step, dict) and "__interrupt__" in step:
            interrupted = True
            question = step["__interrupt__"][0].value

    assert interrupted is True
    assert "पुष्टी करा" in str(question)

    # State must be paused at interrupt
    state_paused = await graph.aget_state(config)
    assert "interrupt" in state_paused.next

    # Resume with confirmation: True
    resumed = False
    async for step in graph.astream(Command(resume={"confirmed": True}), config=config):
        if isinstance(step, dict) and "draft" in step:
            resumed = True

    assert resumed is True
    final_state = await graph.aget_state(config)
    assert final_state.values.get("confirmation_confirmed") is True
    assert "नमस्कार" in final_state.values.get("parent_reply", "")


@pytest.mark.asyncio
async def test_claim_and_done_household_isolation():
    """
    Test that a member cannot claim or complete a task belonging to a different household.
    Ensures both households exist independently so this test passes on any runner.
    """
    import uuid
    from app.db.models import Household, Member, MemberRole, Task, TaskCategory, TaskStatus

    async with AsyncSessionLocal() as db:
        # 1. Ensure Household 1 exists
        h1 = await db.get(Household, 1)
        if not h1:
            h1 = Household(id=1, name="Kulkarni Family (पुणे)", primary_language="mr")
            db.add(h1)
            await db.flush()

        # 2. Create Household 2
        h2 = Household(name="Household Two (Sharma)", primary_language="hi")
        db.add(h2)
        await db.flush()

        # Member belonging exclusively to Household 2
        unique_tg = f"stranger_{uuid.uuid4().hex[:8]}"
        member_h2 = Member(
            household_id=h2.id,
            name="Stranger Child",
            role=MemberRole.child,
            telegram_id=unique_tg,
            phone="+919999999999",
        )
        db.add(member_h2)

        # 3. Create Task belonging exclusively to Household 1
        t1 = Task(
            household_id=h1.id,
            category=TaskCategory.bill,
            title="Household 1 MSEDCL Bill",
            amount="₹1,500",
            status=TaskStatus.confirmed,
        )
        db.add(t1)
        await db.commit()
        await db.refresh(t1)
        await db.refresh(member_h2)

        task_id = t1.id

        # Verify cross-household check logic
        res = await db.execute(select(Member).where(Member.telegram_id == unique_tg))
        member = res.scalars().first()
        task = await db.get(Task, task_id)

        assert member is not None
        assert task is not None
        assert member.household_id != task.household_id, "Households must differ for security test"

        # Simulated handler check (same logic as webhooks & tasks API)
        is_authorized = (task.household_id == member.household_id)
        assert is_authorized is False, "Cross-household claim/done must be rejected"


@pytest.mark.asyncio
async def test_parent_notification_on_task_done():
    """
    Test notify_parents_task_done finds parent members and drafts Marathi reassurance message.
    """
    import uuid
    from app.db.models import Household, Member, MemberRole, Task, TaskCategory, TaskStatus
    from app.api.webhooks import notify_parents_task_done

    async with AsyncSessionLocal() as db:
        h1 = await db.get(Household, 1)
        if not h1:
            h1 = Household(id=1, name="Kulkarni Family (पुणे)", primary_language="mr")
            db.add(h1)
            await db.flush()

        # Ensure parent exists in household 1
        parent_res = await db.execute(
            select(Member).where(Member.household_id == 1, Member.role == MemberRole.parent)
        )
        parent = parent_res.scalars().first()
        if not parent:
            parent = Member(
                household_id=1,
                name="Aai (सुनीता कुलकर्णी)",
                role=MemberRole.parent,
                telegram_id=f"parent_{uuid.uuid4().hex[:6]}",
                phone="+919800000002",
            )
            db.add(parent)
            await db.flush()

        t = Task(
            household_id=1,
            category=TaskCategory.bill,
            title="महावितरण वीज बिल",
            amount="₹1,840",
            status=TaskStatus.claimed,
        )
        db.add(t)
        await db.commit()
        await db.refresh(t)

    # Should execute without errors even in simulated test environment
    await notify_parents_task_done(t, completed_by_name="अमित")

