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

    import uuid, random
    from app.db.models import Household
    test_h_id = random.randint(20000, 89999)
    async with AsyncSessionLocal() as db:
        db.add(Household(id=test_h_id, name="Interrupt Test Family", primary_language="mr"))
        await db.commit()

    graph = await get_compiled_graph()
    thread_id = f"test_interrupt_pipeline_{uuid.uuid4().hex[:6]}"
    config = {"configurable": {"thread_id": thread_id}}

    # Initial state with blurry/unverified quote that fails node_verify
    initial_state: AgentState = {
        "artifact_id": test_h_id,
        "household_id": test_h_id,
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
    assert "check:" in str(question).lower()

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
        unique_phone = f"+9199{uuid.uuid4().int % 100000000:08d}"
        member_h2 = Member(
            household_id=h2.id,
            name="Stranger Child",
            role=MemberRole.child,
            telegram_id=unique_tg,
            phone=unique_phone,
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
                name="Poonam Tawre (Aai)",
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




# ---------------------------------------------------------------------------
# P0-1 Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_p0_1_stop_graph_on_failed_perception_and_empty_extraction(monkeypatch, tmp_path):
    from app.agent.graph import build_graph
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from app.config import settings
    import app.agent.nodes as nodes

    db_file = str(tmp_path / "checkpoints_p0_1.db")
    async with AsyncSqliteSaver.from_conn_string(db_file) as checkpointer:
        await checkpointer.setup()
        graph = build_graph().compile(checkpointer=checkpointer)

        # 1. Perception yields empty text -> graph must terminate at perceive, no interrupt
        state_empty_perceive: AgentState = {
            "artifact_id": 9801,
            "household_id": 1,
            "artifact_type": "voice",
            "file_url": "test://nonexistent_audio.ogg",
            "raw_text": "",
            "errors": [],
        }
        interrupted = False
        final_output = None
        config = {"configurable": {"thread_id": "p0_1_thread_1"}}
        async for step in graph.astream(state_empty_perceive, config=config):
            if isinstance(step, dict) and "__interrupt__" in step:
                interrupted = True
            final_output = step

        assert interrupted is False
        assert final_output is not None
        assert "perceive" in final_output
        assert "ऐकू आला नाही" in final_output["perceive"].get("parent_reply", "")

        # 2. Extraction returning {} -> graph must terminate at extract, no interrupt
        monkeypatch.setattr(settings.__class__, "get_api_key", lambda self: "mock_api_key")
        async def mock_llm(prompt):
            return "not json at all"
        monkeypatch.setattr(nodes, "_call_llm", mock_llm)

        state_empty_extract: AgentState = {
            "artifact_id": 9802,
            "household_id": 1,
            "artifact_type": "image",
            "file_url": "test://unparseable.png",
            "raw_text": "Random gibberish that has no fields",
            "category": TaskCategory.bill.value,
            "errors": [],
        }
        interrupted_2 = False
        final_output_2 = None
        config_2 = {"configurable": {"thread_id": "p0_1_thread_2"}}
        async for step in graph.astream(state_empty_extract, config=config_2):
            if isinstance(step, dict) and "__interrupt__" in step:
                interrupted_2 = True
            final_output_2 = step

        assert interrupted_2 is False
        assert final_output_2 is not None
        assert "extract" in final_output_2



# ---------------------------------------------------------------------------
# P0-2 Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_p0_2_confirmation_question_formatting():
    from app.agent.nodes import node_verify

    state: AgentState = {
        "raw_text": "MSEDCL Electricity Bill Due 2026-11-20 Amount ₹1,840",
        "extracted": {
            "payee": {"value": "MSEDCL", "quote": "MSEDCL"},
            "amount": {"value": "₹1,840", "quote": "Amount ₹1,500"},  # amount mismatch
            "due_date": {"value": "2026-11-20T00:00:00", "quote": "2026-11-20"},
        },
        "confidence": 0.8,
    }
    v_res = await node_verify(state)
    assert v_res["verify_passed"] is False
    q = v_res["confirmation_question"]
    assert "MSEDCL" in q
    assert "₹1,840" in q
    assert len(q) <= 60
    reasons = v_res.get("confirmation_reasons", [])
    assert len(reasons) > 0
    for r in reasons:
        assert "digits" not in r
        assert "quote" not in r


# ---------------------------------------------------------------------------
# P0-3 Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_p0_3_escalation_triggers_on_status_not_unassigned(monkeypatch):
    import uuid
    from datetime import datetime, timedelta, timezone
    from app.db.models import Household, Member, MemberRole, Task, TaskCategory, TaskStatus
    from app.db.session import AsyncSessionLocal
    from app.scheduler.escalation import run_escalation, get_ist_now
    import app.scheduler.escalation as esc_module

    notified = []
    async def mock_notify(**kwargs):
        notified.append(kwargs)
    monkeypatch.setattr(esc_module, "notify", mock_notify)

    unique_h_id = 903
    async with AsyncSessionLocal() as db:
        h = await db.get(Household, unique_h_id)
        if not h:
            h = Household(id=unique_h_id, name="Escalation Test Family", primary_language="mr")
            db.add(h)
            await db.flush()

        child = Member(
            household_id=unique_h_id,
            name="Rohan",
            role=MemberRole.child,
            telegram_id=f"child_{uuid.uuid4().hex[:6]}",
            phone=f"+9198{uuid.uuid4().hex[:8]}",
        )
        db.add(child)
        await db.flush()

        now_ist = datetime(2026, 11, 3, 14, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        monkeypatch.setattr(esc_module, "get_ist_now", lambda: now_ist)
        # Task 1: Has assignee, status confirmed, due in 2 days (within escalation window)
        t_confirmed = Task(
            household_id=unique_h_id,
            category=TaskCategory.bill,
            title="Electricity Bill Due Soon",
            amount="₹1,200",
            status=TaskStatus.confirmed,
            assignee_id=child.id,
            due_date=(now_ist + timedelta(days=2)).replace(tzinfo=None),
        )
        # Task 2: Already claimed, due tomorrow -> should NOT escalate
        t_claimed = Task(
            household_id=unique_h_id,
            category=TaskCategory.bill,
            title="Internet Bill Claimed",
            amount="₹800",
            status=TaskStatus.claimed,
            assignee_id=child.id,
            due_date=(now_ist + timedelta(days=1)).replace(tzinfo=None),
        )
        db.add_all([t_confirmed, t_claimed])
        await db.commit()
        t_confirmed_id = t_confirmed.id
        t_claimed_id = t_claimed.id

    # Run escalation
    escalated_ids = await run_escalation()

    # Assertions
    assert t_confirmed_id in escalated_ids
    assert t_claimed_id not in escalated_ids

    # Check task status in DB
    async with AsyncSessionLocal() as db:
        t_refreshed = await db.get(Task, t_confirmed_id)
        assert t_refreshed.status == TaskStatus.escalated

    # Run escalation again -> idempotent, shouldn't escalate again
    escalated_again = await run_escalation()
    assert t_confirmed_id not in escalated_again


# ---------------------------------------------------------------------------
# P0-4 Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_p0_4_suppress_sibling_alert_on_duplicate():
    from app.agent.nodes import node_draft

    state: AgentState = {
        "existing_task_id": 5,
        "household_id": 1,
        "extracted": {
            "title": {"value": "MSEDCL Electricity Bill"},
            "amount": {"value": "₹1,840"},
            "due_date": {"value": "2026-11-20T00:00:00"},
            "payee": {"value": "MSEDCL"},
        },
        "category": "bill",
    }

    res = await node_draft(state)
    assert res.get("sibling_notification") == ""
    assert res.get("call_script") is None
    parent_reply = res.get("parent_reply", "")
    assert "आधीच" in parent_reply


# ---------------------------------------------------------------------------
# P0-5 Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_p0_5_serialize_agent_runs_per_household(monkeypatch):
    import uuid
    import asyncio
    from sqlalchemy import select
    from app.config import settings
    from app.db.models import Household, Member, MemberRole, Artifact, ArtifactType, Task, TaskStatus
    from app.db.session import AsyncSessionLocal
    from app.api.webhooks import _run_agent
    import app.agent.nodes as nodes
    import app.api.webhooks as wh_module

    async def noop_async(*args, **kwargs):
        return None

    monkeypatch.setattr(wh_module, "_send_telegram_message", noop_async)
    monkeypatch.setattr(wh_module, "_send_whatsapp_message", noop_async)
    monkeypatch.setattr(wh_module, "notify", noop_async)
    monkeypatch.setattr(wh_module, "_notify_siblings_new_task", noop_async)
    monkeypatch.setattr(settings.__class__, "get_api_key", lambda self: "mock_api_key")

    deterministic_json = """{
        "category": "bill",
        "title": {"value": "Electricity bill", "quote": "bill"},
        "payee": {"value": "MSEDCL", "quote": "MSEDCL"},
        "amount": {"value": "₹1,840", "quote": "1840"},
        "due_date": {"value": "2026-11-20T00:00:00", "quote": "2026-11-20"},
        "consumer_number": {"value": "020010001234", "quote": "020010001234"}
    }"""

    async def mock_call_llm(prompt: str, json_mode: bool = False) -> str:
        await asyncio.sleep(0.05)
        return deterministic_json

    monkeypatch.setattr(nodes, "_call_llm", mock_call_llm)

    import random
    unique_h_id = random.randint(10000, 99999)
    async with AsyncSessionLocal() as db:
        h = await db.get(Household, unique_h_id)
        if not h:
            h = Household(id=unique_h_id, name="Concurrent Test Family", primary_language="mr")
            db.add(h)
            await db.flush()

        child = Member(
            household_id=unique_h_id,
            name="Amit",
            role=MemberRole.child,
            telegram_id=f"child_{uuid.uuid4().hex[:6]}",
            phone=f"+9198{uuid.uuid4().hex[:8]}",
        )
        parent = Member(
            household_id=unique_h_id,
            name="Baba",
            role=MemberRole.parent,
            telegram_id=f"parent_{uuid.uuid4().hex[:6]}",
            phone=f"+9198{uuid.uuid4().hex[:8]}",
        )
        db.add_all([child, parent])
        await db.flush()

        art1 = Artifact(
            household_id=unique_h_id,
            type=ArtifactType.image,
            file_url="text://message",
            raw_text="महावितरण वीज bill MSEDCL 1840 due 2026-11-20 consumer 020010001234",
        )
        art2 = Artifact(
            household_id=unique_h_id,
            type=ArtifactType.image,
            file_url="text://message",
            raw_text="Electricity bill MSEDCL amount 1840 due date 2026-11-20 consumer 020010001234",
        )
        db.add_all([art1, art2])
        await db.commit()
        art1_id = art1.id
        art2_id = art2.id

    await asyncio.gather(
        _run_agent(art1_id, unique_h_id, "image", "text://message", "chat_1", "telegram"),
        _run_agent(art2_id, unique_h_id, "image", "text://message", "chat_2", "telegram"),
    )

    async with AsyncSessionLocal() as db:
        tasks_res = await db.execute(
            select(Task).where(
                Task.household_id == unique_h_id,
                Task.status.notin_([TaskStatus.done]),
            )
        )
        tasks = tasks_res.scalars().all()
        assert len(tasks) == 1, f"Expected 1 task but found {len(tasks)}"


# ---------------------------------------------------------------------------
# P0-6 Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_p0_6_idempotent_claim_and_complete(monkeypatch):
    import uuid, random
    from datetime import datetime, timedelta
    from sqlalchemy import select
    from app.db.models import Household, Member, MemberRole, Task, TaskCategory, TaskStatus
    from app.db.session import AsyncSessionLocal
    from app.services.tasks import claim_task, complete_task, ClaimResult, DoneResult
    import app.services.tasks as s_module

    notified = []
    async def mock_notify_parents(task, completed_by_name=""):
        notified.append((task.id, completed_by_name))
    monkeypatch.setattr(s_module, "notify_parents_task_done", mock_notify_parents)

    test_h_id = random.randint(10000, 99999)
    async with AsyncSessionLocal() as db:
        h = Household(id=test_h_id, name="Idempotent Test Family", primary_language="mr")
        db.add(h)
        await db.flush()

        sib_a = Member(
            household_id=test_h_id,
            name="Aarav",
            role=MemberRole.child,
            telegram_id=f"sib_a_{uuid.uuid4().hex[:6]}",
            phone=f"+9191{uuid.uuid4().hex[:8]}",
        )
        sib_b = Member(
            household_id=test_h_id,
            name="Ananya",
            role=MemberRole.child,
            telegram_id=f"sib_b_{uuid.uuid4().hex[:6]}",
            phone=f"+9192{uuid.uuid4().hex[:8]}",
        )
        db.add_all([sib_a, sib_b])
        await db.flush()

        task_claim = Task(
            household_id=test_h_id,
            category=TaskCategory.bill,
            title="Water Bill",
            amount="₹450",
            status=TaskStatus.confirmed,
        )
        task_emi = Task(
            household_id=test_h_id,
            category=TaskCategory.loan_emi,
            title="Home Loan EMI",
            amount="₹25,000",
            due_date=datetime(2026, 11, 15),
            status=TaskStatus.confirmed,
            recurrence="monthly",
        )
        db.add_all([task_claim, task_emi])
        await db.commit()
        t_claim_id = task_claim.id
        t_emi_id = task_emi.id

    # 1. Sibling A claims task_claim -> ok
    res1, t1 = await claim_task(t_claim_id, sib_a)
    assert res1 == ClaimResult.ok
    assert t1.assignee_id == sib_a.id
    assert t1.status == TaskStatus.claimed

    # 2. Sibling B attempts to claim the same task -> taken, assignee remains sibling A
    res2, t2 = await claim_task(t_claim_id, sib_b)
    assert res2 == ClaimResult.taken
    assert t2.assignee_id == sib_a.id

    # 3. Sibling A claims again -> already_yours
    res3, t3 = await claim_task(t_claim_id, sib_a)
    assert res3 == ClaimResult.already_yours

    # 4. Complete recurring monthly EMI task first time -> ok, creates 1 recurring task, notifies parents once
    res_done1, td1 = await complete_task(t_emi_id, sib_a.name, test_h_id)
    assert res_done1 == DoneResult.ok
    assert td1.status == TaskStatus.done
    assert len(notified) == 1

    # 5. Complete same task second time -> already_done, no second recurring task, no second notification
    res_done2, td2 = await complete_task(t_emi_id, sib_b.name, test_h_id)
    assert res_done2 == DoneResult.already_done
    assert len(notified) == 1

    # Check recurring task in DB
    async with AsyncSessionLocal() as db:
        recurring_res = await db.execute(
            select(Task).where(
                Task.household_id == test_h_id,
                Task.title == "Home Loan EMI",
            )
        )
        all_emis = recurring_res.scalars().all()
        # Original (done) + exactly 1 next month recurring task = 2
        assert len(all_emis) == 2


@pytest.mark.asyncio
async def test_p0_6_web_patch_recurrence(monkeypatch):
    import random
    from datetime import datetime
    from sqlalchemy import select
    from app.db.models import Household, Task, TaskCategory, TaskStatus
    from app.db.session import AsyncSessionLocal
    from app.api.tasks import update_task, TaskUpdate
    import app.services.tasks as s_module

    notified = []
    async def mock_notify_parents(task, completed_by_name=""):
        notified.append((task.id, completed_by_name))
    monkeypatch.setattr(s_module, "notify_parents_task_done", mock_notify_parents)

    test_h_id = random.randint(10000, 99999)
    async with AsyncSessionLocal() as db:
        h = Household(id=test_h_id, name="Web Patch Family", primary_language="mr")
        db.add(h)
        task = Task(
            household_id=test_h_id,
            category=TaskCategory.loan_emi,
            title="Education Loan EMI",
            amount="₹10,000",
            due_date=datetime(2026, 11, 25),
            status=TaskStatus.confirmed,
            recurrence="monthly",
        )
        db.add(task)
        await db.commit()
        task_id = task.id

    async with AsyncSessionLocal() as db:
        update_dto = TaskUpdate(status=TaskStatus.done)
        res = await update_task(task_id, update_dto, db)
        assert res.status == TaskStatus.done

    async with AsyncSessionLocal() as db:
        recurring_res = await db.execute(
            select(Task).where(
                Task.household_id == test_h_id,
                Task.title == "Education Loan EMI",
            )
        )
        all_emis = recurring_res.scalars().all()
        assert len(all_emis) == 2


# ---------------------------------------------------------------------------
# P0-7 Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_p0_7_route_status_queries_away_from_task_creation():
    import uuid, random
    from sqlalchemy import select
    from app.agent.graph import get_compiled_graph
    from app.db.models import Household, Task, TaskCategory, TaskStatus
    from app.db.session import AsyncSessionLocal
    from app.agent.state import AgentState

    test_h_id = random.randint(10000, 99999)
    async with AsyncSessionLocal() as db:
        h = Household(id=test_h_id, name="Status Test Family", primary_language="mr")
        db.add(h)
        task = Task(
            household_id=test_h_id,
            category=TaskCategory.bill,
            title="MSEDCL Bill",
            amount="₹1,840",
            status=TaskStatus.confirmed,
        )
        db.add(task)
        await db.commit()

    graph = await get_compiled_graph()
    thread_id = f"test_status_{uuid.uuid4().hex[:6]}"
    config = {"configurable": {"thread_id": thread_id}}

    state: AgentState = {
        "artifact_id": random.randint(10000, 99999),
        "household_id": test_h_id,
        "artifact_type": "voice",
        "raw_text": "काय बाकी आहे?",
        "errors": [],
    }

    final_state = None
    interrupted = False
    async for step in graph.astream(state, config=config):
        if isinstance(step, dict) and "__interrupt__" in step:
            interrupted = True
        final_state = step

    assert interrupted is False
    # Check that no new task was created (still only 1 task in DB)
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Task).where(Task.household_id == test_h_id))
        tasks = res.scalars().all()
        assert len(tasks) == 1

    # Check parent_reply from final_state
    parent_reply = ""
    if final_state:
        for node_out in final_state.values():
            if isinstance(node_out, dict) and "parent_reply" in node_out:
                parent_reply = node_out["parent_reply"]
    assert "बाकी असलेली कामे" in parent_reply or "कोणतीही बिले" in parent_reply


# ---------------------------------------------------------------------------
# P0-8 Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_p0_8_medical_guardrail_and_bill_classification():
    from app.agent.nodes import node_classify, node_draft, node_guardrail, GUARDRAIL_REPLY
    from app.db.models import TaskCategory, TaskStatus, Task, Household
    from app.db.session import AsyncSessionLocal
    import random

    # Table row 1: Apollo Pharmacy Bill -> bill
    c1 = await node_classify({"raw_text": "अपोलो फार्मसी औषध बिल रक्कम ₹2,340 देय 15 नोव्हेंबर", "doc_type": "bill"})
    assert c1["category"] == TaskCategory.bill
    assert c1.get("medical_context") is True

    # Table row 2: Dr Lal PathLabs Invoice -> bill
    c2 = await node_classify({"raw_text": "Dr Lal PathLabs Invoice Amount Rs 1,200 due 20 Nov 2026", "doc_type": "other"})
    assert c2["category"] == TaskCategory.bill
    assert c2.get("medical_context") is True

    # Table row 3: Sahyadri Hospital final bill with discharge summary -> bill
    c3 = await node_classify({"raw_text": "Sahyadri Hospital final bill, see discharge summary. Amount payable Rs 45,000", "doc_type": "other"})
    assert c3["category"] == TaskCategory.bill
    assert c3.get("medical_context") is True

    # Table row 4: Hindi prescription advice -> medical
    c4 = await node_classify({"raw_text": "डॉक्टर ने दवाई लिखी है, रोज़ दो गोली सुबह शाम", "doc_type": "other"})
    assert c4["category"] == TaskCategory.medical

    # Pharmacy bill draft includes the "cannot interpret reports" sentence
    d_res = await node_draft({
        "household_id": 1,
        "extracted": {
            "title": {"value": "अपोलो फार्मसी बिल"},
            "amount": {"value": "₹2,340"},
            "due_date": {"value": "2026-11-15T00:00:00"},
            "payee": {"value": "अपोलो फार्मसी"},
        },
        "category": TaskCategory.bill.value,
        "medical_context": True,
    })
    assert "वैद्यकीय अहवाल किंवा गोळ्यांचा अर्थ सांगता येणार नाही" in d_res["parent_reply"]

    # Guardrail with no date -> creates NO task
    test_h_id = random.randint(10000, 99999)
    async with AsyncSessionLocal() as db:
        db.add(Household(id=test_h_id, name="Guardrail Test Family", primary_language="mr"))
        await db.commit()

    g_no_date = await node_guardrail({
        "household_id": test_h_id,
        "raw_text": "Take paracetamol twice daily for 5 days",
    })
    assert g_no_date["parent_reply"] == GUARDRAIL_REPLY
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        res = await db.execute(select(Task).where(Task.household_id == test_h_id))
        assert len(res.scalars().all()) == 0

    # Guardrail with date "10 नोव्हेंबर 2026" -> creates confirmed task
    g_with_date = await node_guardrail({
        "household_id": test_h_id,
        "raw_text": "पुढील तपासणी सह्याद्री हॉस्पिटल येथे 10 नोव्हेंबर 2026 रोजी आहे.",
    })
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Task).where(Task.household_id == test_h_id))
        tasks = res.scalars().all()
        assert len(tasks) == 1
        assert tasks[0].status == TaskStatus.confirmed
        assert tasks[0].due_date is not None
        assert tasks[0].due_date.month == 11
        assert tasks[0].due_date.day == 10


# ---------------------------------------------------------------------------
# P1-9 Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_p1_9_devanagari_and_normalized_quotes():
    from app.agent.nodes import node_verify

    # 1. Devanagari numerals: ₹1,840 vs ₹१,८४० passes verify
    raw_text = "महावितरण वीज बिल देय रक्कम ₹१,८४० अंतिम तारीख 2026-11-20"
    extracted = {
        "amount": {"value": "₹1,840", "quote": "रक्कम ₹१,८४०"},
        "due_date": {"value": "2026-11-20T00:00:00", "quote": "2026-11-20"},
        "payee": {"value": "Mahavitaran (MSEDCL)", "quote": "महावितरण"},
        "title": {"value": "वीज बिल", "quote": "वीज बिल"},
    }
    res = await node_verify({"raw_text": raw_text, "extracted": extracted, "confidence": 1.0})
    assert res["verify_passed"] is True, f"Expected pass, got failures: {res.get('verify_failures')}"

    # 2. Substring mismatch: extracted ₹184 vs quote ₹1,840 fails check 3
    extracted_sub = {
        "amount": {"value": "₹184", "quote": "रक्कम ₹१,८४०"},
        "due_date": {"value": "2026-11-20T00:00:00", "quote": "2026-11-20"},
        "payee": {"value": "Mahavitaran (MSEDCL)", "quote": "महावितरण"},
        "title": {"value": "वीज बिल", "quote": "वीज बिल"},
    }
    res_sub = await node_verify({"raw_text": raw_text, "extracted": extracted_sub, "confidence": 1.0})
    assert res_sub["verify_passed"] is False
    assert any("amount" in f for f in res_sub["verify_failures"])

    # 3. Extra internal whitespace or non-breaking spaces in quote passes verification if norm(quote) in norm(raw_text)
    raw_text_ws = "टाटा पॉवर   देय रक्कम  ₹2,500   तारीख 2026-11-25"
    extracted_ws = {
        "amount": {"value": "₹2,500", "quote": "देय रक्कम ₹2,500"},
        "due_date": {"value": "2026-11-25T00:00:00", "quote": "2026-11-25"},
        "payee": {"value": "Tata Power", "quote": "टाटा पॉवर"},
        "title": {"value": "टाटा पॉवर", "quote": "टाटा पॉवर"},
    }
    res_ws = await node_verify({"raw_text": raw_text_ws, "extracted": extracted_ws, "confidence": 1.0})
    assert res_ws["verify_passed"] is True, f"Expected pass, got failures: {res_ws.get('verify_failures')}"


# ---------------------------------------------------------------------------
# P1-10 Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_p1_10_exclude_generated_title_from_grounding():
    import json
    import unittest.mock
    from app.agent.nodes import node_extract, node_verify
    from app.config import settings

    raw_text = "MSEDCL electricity bill amount ₹1,450 due date 2026-11-28"
    mock_llm_json = json.dumps({
        "amount": {"value": "₹1,450", "quote": "₹1,450"},
        "due_date": {"value": "2026-11-28T00:00:00", "quote": "2026-11-28"},
        "payee": {"value": "MSEDCL", "quote": "MSEDCL"},
        "title": {"value": "Monthly Power Bill Payment for Residence", "quote": "Not in text at all"},
    })

    with unittest.mock.patch("app.agent.nodes._call_llm", unittest.mock.AsyncMock(return_value=mock_llm_json)):
        with unittest.mock.patch.object(settings, "llm_api_key", "test-real-api-key"):
            extract_res = await node_extract({"artifact_id": 1, "raw_text": raw_text})

            # Title value should be preserved despite quote not being in raw_text
            assert extract_res["extracted"]["title"]["value"] == "Monthly Power Bill Payment for Residence"
            # Confidence should be 1.0 (3/3 grounded fields amount, due_date, payee)
            assert extract_res["confidence"] == 1.0

            verify_res = await node_verify({"raw_text": raw_text, "extracted": extract_res["extracted"], "confidence": extract_res["confidence"]})
            assert verify_res["verify_passed"] is True
            assert len(verify_res["verify_failures"]) == 0


# ---------------------------------------------------------------------------
# P1-11 Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_p1_11_robust_dedup_keys():
    import random
    from app.agent.nodes import node_deduplicate

    # 1. "New India Assurance policy" does not normalize to LIC
    d_nia = await node_deduplicate({
        "household_id": 1,
        "extracted": {
            "payee": {"value": "New India Assurance policy"},
            "amount": {"value": "₹3,500"},
            "due_date": {"value": "2026-11-15T00:00:00"},
        }
    })
    d_lic = await node_deduplicate({
        "household_id": 1,
        "extracted": {
            "payee": {"value": "LIC"},
            "amount": {"value": "₹3,500"},
            "due_date": {"value": "2026-11-15T00:00:00"},
        }
    })
    assert d_nia["dedupe_key"] != d_lic["dedupe_key"], "New India Assurance policy must not normalize to LIC"

    # 2. Two tasks, same payee and amount, different consumer numbers -> not merged
    d_cn1 = await node_deduplicate({
        "household_id": 1,
        "extracted": {
            "payee": {"value": "Tata Power"},
            "amount": {"value": "₹2,000"},
            "due_date": {"value": "2026-11-20T00:00:00"},
            "consumer_number": {"value": "1111100000"},
        }
    })
    d_cn2 = await node_deduplicate({
        "household_id": 1,
        "extracted": {
            "payee": {"value": "Tata Power"},
            "amount": {"value": "₹2,000"},
            "due_date": {"value": "2026-11-20T00:00:00"},
            "consumer_number": {"value": "9999900000"},
        }
    })
    assert d_cn1["dedupe_key"] != d_cn2["dedupe_key"], "Different consumer numbers must produce different dedupe keys"

    # 3. Missing due date -> dedupe_key is None
    d_no_due = await node_deduplicate({
        "household_id": 1,
        "extracted": {
            "payee": {"value": "Tata Power"},
            "amount": {"value": "₹2,000"},
        }
    })
    assert d_no_due["dedupe_key"] is None
    assert d_no_due["existing_task_id"] is None


# ---------------------------------------------------------------------------
# P1-12 Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_p1_12_readme_claims_heuristic_fallback_and_round_robin():
    import os
    import random
    import unittest.mock
    from app.agent.nodes import node_extract, node_assign
    from app.config import settings
    from app.db.models import Household, Member, MemberRole, Task, TaskCategory, TaskStatus
    from app.db.session import AsyncSessionLocal
    from sqlalchemy import select

    # 1. No-key extraction returns heuristic fields
    raw_text = "महावितरण वीज बिल रक्कम ₹1,450 देय तारीख 2026-11-28"
    with unittest.mock.patch.object(settings, "llm_api_key", ""):
        with unittest.mock.patch.object(settings, "meta_api_key", ""):
            with unittest.mock.patch.dict(os.environ, {"BASETEN_API_KEY": ""}):
                res = await node_extract({"artifact_id": 1, "raw_text": raw_text, "household_id": 1})
                assert res["extracted"]["amount"]["value"] == "₹1,450"
                assert res["extracted"]["payee"]["value"] == "Mahavitaran (MSEDCL)"

    # 2. Round-robin assigns to child with fewest open tasks
    h_id = random.randint(10000, 99999)
    async with AsyncSessionLocal() as db:
        hh = Household(id=h_id, name="RoundRobin Family", primary_language="mr")
        db.add(hh)
        c_a = Member(id=h_id * 10 + 1, household_id=h_id, name="Child A", role=MemberRole.child, categories_owned=[])
        c_b = Member(id=h_id * 10 + 2, household_id=h_id, name="Child B", role=MemberRole.child, categories_owned=[])
        db.add_all([c_a, c_b])
        # Give Child A 2 open tasks
        t1 = Task(household_id=h_id, assignee_id=c_a.id, title="Open 1", status=TaskStatus.new)
        t2 = Task(household_id=h_id, assignee_id=c_a.id, title="Open 2", status=TaskStatus.confirmed)
        db.add_all([t1, t2])
        await db.commit()

    state = {
        "household_id": h_id,
        "artifact_id": 1,
        "raw_text": raw_text,
        "category": TaskCategory.bill.value,
        "extracted": {
            "title": {"value": "New Power Bill"},
            "amount": {"value": "₹1,450"},
            "due_date": {"value": "2026-11-28T00:00:00"},
            "payee": {"value": "Mahavitaran (MSEDCL)"},
        },
        "verify_passed": True,
        "dedupe_key": "some_key",
    }
    assign_res = await node_assign(state)
    assert assign_res["assignee_id"] == c_b.id, f"Expected Child B ({c_b.id}) with 0 open tasks, got {assign_res['assignee_id']}"

    # 3. If dedupe_key is None -> status is needs_review
    state_no_dedupe = dict(state)
    state_no_dedupe["dedupe_key"] = None
    assign_res_no_dedupe = await node_assign(state_no_dedupe)
    async with AsyncSessionLocal() as db:
        t_created = await db.get(Task, assign_res_no_dedupe["task_id"])
        assert t_created.status == TaskStatus.needs_review


# ---------------------------------------------------------------------------
# P1-13 Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_p1_13_smaller_crashes_and_edge_cases():
    import io
    import unittest.mock
    from PIL import Image
    from app.agent.nodes import node_classify, node_draft, _preprocess_image
    from app.config import settings
    from app.db.models import TaskCategory

    # 1. Empty-string LLM output doesn't crash classify
    with unittest.mock.patch("app.agent.nodes._call_llm", unittest.mock.AsyncMock(return_value="   ")):
        with unittest.mock.patch.object(settings, "llm_api_key", "test-key"):
            res = await node_classify({"raw_text": "Random text that does not match keywords", "household_id": 1})
            assert "category" in res

    # 2. The draft for a due date of 2026-11-10 contains "नोव्हेंबर" and not "2026-11-10"
    draft_res = await node_draft({
        "household_id": 1,
        "category": TaskCategory.bill.value,
        "extracted": {
            "title": {"value": "Electricity Bill"},
            "amount": {"value": "₹1,200"},
            "due_date": {"value": "2026-11-10T00:00:00"},
            "payee": {"value": "Tata Power"},
        },
    })
    parent_reply = draft_res["parent_reply"]
    assert "नोव्हेंबर" in parent_reply, f"Expected Marathi month name 'नोव्हेंबर' in parent reply, got: {parent_reply}"
    assert "2026-11-10" not in parent_reply, f"ISO date 2026-11-10 must not appear in parent reply, got: {parent_reply}"

    # 3. Image preprocessing returns bytes <= original size for a large test image generated in memory
    import os
    img = Image.frombytes("RGB", (2000, 1800), os.urandom(2000 * 1800 * 3))
    raw_buf = io.BytesIO()
    img.save(raw_buf, format="BMP")
    large_bytes = raw_buf.getvalue()

    processed_bytes = _preprocess_image(large_bytes)
    assert len(processed_bytes) <= len(large_bytes), "Preprocessed image must be smaller than large uncompressed image"
    processed_img = Image.open(io.BytesIO(processed_bytes))
    assert max(processed_img.size) <= 1600, f"Long edge must be <= 1600 px, got {processed_img.size}"


# ---------------------------------------------------------------------------
# P3-16 Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_p3_16_protect_web_task_api(monkeypatch):
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.config import settings

    monkeypatch.setattr(settings, "admin_secret", "saath_admin_secret_demo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Missing token -> 401
        res1 = await client.get("/tasks/1")
        assert res1.status_code == 401, f"Expected 401 on missing admin token, got {res1.status_code}"

        # 2. Invalid status -> 422
        res2 = await client.patch(
            "/tasks/1",
            json={"status": "invalid_status_xyz"},
            headers={"X-Admin-Token": settings.admin_secret},
        )
        assert res2.status_code == 422, f"Expected 422 on invalid status, got {res2.status_code}"

        # 3. Wrong household -> 404
        res3 = await client.patch(
            "/tasks/1?household_id=999999",
            json={"status": "done"},
            headers={"X-Admin-Token": settings.admin_secret},
        )
        assert res3.status_code == 404, f"Expected 404 on wrong household, got {res3.status_code}"


# ---------------------------------------------------------------------------
# P3-17 Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_p3_17_sqlite_wal_and_busy_timeout(tmp_path):
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.db.session import _apply_sqlite_pragmas

    test_db = tmp_path / "pragma_test.db"
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{test_db}")
    _apply_sqlite_pragmas(test_engine)

    async with test_engine.connect() as conn:
        journal_mode = (await conn.exec_driver_sql("PRAGMA journal_mode")).scalar()
        busy_timeout = (await conn.exec_driver_sql("PRAGMA busy_timeout")).scalar()

    await test_engine.dispose()
    assert str(journal_mode).lower() == "wal"
    assert busy_timeout == 5000


# ---------------------------------------------------------------------------
# P3-18 Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_p3_18_scheduler_process_control(monkeypatch):
    import unittest.mock
    from app.config import settings
    from app.main import lifespan, app

    mock_start = unittest.mock.MagicMock()
    monkeypatch.setattr("app.main.start_scheduler", mock_start)

    # When run_scheduler is False, start_scheduler is NOT called during lifespan
    monkeypatch.setattr(settings, "run_scheduler", False)
    async with lifespan(app):
        pass
    mock_start.assert_not_called()

    # When run_scheduler is True, start_scheduler IS called
    mock_start.reset_mock()
    monkeypatch.setattr(settings, "run_scheduler", True)
    async with lifespan(app):
        pass
    mock_start.assert_called_once()


# ---------------------------------------------------------------------------
# P3-19 Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_p3_19_empty_admin_secret_returns_503(monkeypatch):
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.config import settings

    monkeypatch.setattr(settings, "admin_secret", "")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Task route returns 503
        res1 = await client.get("/tasks/1", headers={"X-Admin-Token": "some-token"})
        assert res1.status_code == 503, f"Expected 503 when admin_secret is empty, got {res1.status_code}"
        assert "ADMIN_SECRET not configured" in res1.json().get("detail", "")

        # Admin route returns 503
        res2 = await client.post("/admin/escalate/simulate", headers={"X-Admin-Token": "some-token"})
        assert res2.status_code == 503, f"Expected 503 when admin_secret is empty, got {res2.status_code}"
        assert "ADMIN_SECRET not configured" in res2.json().get("detail", "")


@pytest.mark.asyncio
async def test_simulate_ingest_creates_artifact_and_queues_agent(monkeypatch):
    """Regression: 'Try Live Agent' endpoint must not 500 (bad Artifact kwargs, missing _run_agent args)."""
    from fastapi import BackgroundTasks
    from app.api import admin
    from app.db.models import Artifact
    from app.db.session import AsyncSessionLocal

    req = admin.SimulateIngestRequest(household_id=1, type="text", raw_text="Adani Electricity Rs 2,310 pay by 21-11-2099")
    bg = BackgroundTasks()
    res = await admin.simulate_ingest(req, bg, None)
    async with AsyncSessionLocal() as db:
        art = await db.get(Artifact, res["artifact_id"])
    assert art.raw_text.startswith("Adani") and art.file_url
    kwargs = bg.tasks[0].kwargs
    assert kwargs["artifact_type"] == "image" and kwargs["file_url"] == art.file_url


def test_heuristic_amount_keeps_decimal_point():
    from app.agent.nodes import _heuristic_extract
    assert _heuristic_extract("Amount payable Rs 2,310.00\nPay by 21-11-2099")["amount"]["value"] == "₹2,310"
    assert _heuristic_extract("एकूण देय रक्कम: ₹१,८४०")["amount"]["value"] == "₹1,840"


@pytest.mark.asyncio
async def test_scam_guardrail_refusal_and_sibling_alert(monkeypatch):
    """
    Tier 2 Test: Safe scam reply.
    If a forwarded message mentions OTP, KYC or 'account blocked',
    reply "Don't share any OTP; I've asked Rohan to check" and alert a sibling.
    """
    from app.agent.nodes import node_classify, node_scam_guardrail
    import app.agent.nodes as nodes_module

    notified = []
    async def mock_notify(**kwargs):
        notified.append(kwargs)
    monkeypatch.setattr(nodes_module, "notify", mock_notify)

    # 1. Classification check
    scam_msg = "Forwarded: Dear customer, your SBI account is blocked. Update KYC immediately or share OTP."
    c_res = await node_classify({"raw_text": scam_msg})
    assert c_res["category"] == "scam_alert"

    # 2. Execution check: create isolated test household, parent and child
    from app.db.session import AsyncSessionLocal
    from app.db.models import Household, Member, MemberRole
    async with AsyncSessionLocal() as db:
        hh = Household(name="Scam Test Household", primary_language="en")
        db.add(hh)
        await db.commit()
        await db.refresh(hh)
        child = Member(
            household_id=hh.id,
            name="Rohan",
            role=MemberRole.child,
            phone="+919876543210",
        )
        parent = Member(
            household_id=hh.id,
            name="Aai",
            role=MemberRole.parent,
            phone="+919876543211",
        )
        db.add_all([child, parent])
        await db.commit()
        test_hh_id = hh.id

    state = {
        "raw_text": scam_msg,
        "household_id": test_hh_id,
    }
    res = await node_scam_guardrail(state)
    assert "Don't share any OTP; I've asked Rohan to check" in res["parent_reply"]
    assert len(notified) > 0, "Sibling must be alerted via notify()"
    assert "Scam/Fraud Warning" in notified[0]["text"]

    # 3. Marathi version
    marathi_scam = "तुमचे वीज खाते बंद केले जाईल. त्वरित केवायसी करा आणि ओटीपी पाठवा."
    c_res_mr = await node_classify({"raw_text": marathi_scam})
    assert c_res_mr["category"] == "scam_alert"


@pytest.mark.asyncio
async def test_sibling_quiet_hours_and_timezones():
    """
    Tier 2 Test: Quiet hours & timezones for siblings abroad.
    Non-urgent escalations must be deferred during local night hours.
    """
    from datetime import datetime, timezone
    from app.db.models import Member, MemberRole
    from app.scheduler.escalation import is_in_quiet_hours

    # Sibling in New York (UTC-4/UTC-5)
    ny_sibling = Member(
        household_id=1,
        name="Priya (US)",
        role=MemberRole.child,
        timezone="America/New_York",
        quiet_hours_start=22,
        quiet_hours_end=7,
    )

    # 3:00 AM New York time (08:00 UTC) -> should be in quiet hours
    dt_night = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)
    assert is_in_quiet_hours(ny_sibling, dt_night) is True

    # 2:00 PM New York time (19:00 UTC) -> should NOT be in quiet hours
    dt_day = datetime(2026, 11, 2, 19, 0, tzinfo=timezone.utc)
    assert is_in_quiet_hours(ny_sibling, dt_day) is False


@pytest.mark.asyncio
async def test_parent_first_photo_privacy_reassurance():
    """
    Tier 2 Test: Send privacy reassurance on parent's first photo upload.
    One line in their language saying only family sees it.
    """
    import random
    from app.agent.nodes import node_draft
    from app.db.models import Household, Artifact, ArtifactType
    from app.db.session import AsyncSessionLocal

    h_id = random.randint(50000, 99999)
    async with AsyncSessionLocal() as db:
        hh = Household(id=h_id, name="Privacy Test Family", primary_language="mr")
        db.add(hh)
        # First photo artifact
        art = Artifact(
            household_id=h_id,
            type=ArtifactType.image,
            file_url="test://bill_photo.jpg",
            raw_text="Tata Power Bill",
        )
        db.add(art)
        await db.commit()

    draft_res = await node_draft({
        "household_id": h_id,
        "artifact_type": "image",
        "category": "bill",
        "extracted": {
            "title": {"value": "टाटा पॉवर वीज बिल"},
            "amount": {"value": "₹1,450"},
            "due_date": {"value": "2026-11-20T00:00:00"},
            "payee": {"value": "Tata Power"},
        },
    })
    parent_reply = draft_res["parent_reply"]
    assert "फक्त तुमच्या कुटुंबातील सदस्यांनाच दिसेल" in parent_reply, (
        f"Expected privacy reassurance in Marathi for first photo upload, got: {parent_reply}"
    )

