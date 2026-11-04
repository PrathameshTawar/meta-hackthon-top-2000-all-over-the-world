"""G-1: guardians (MemberRole.helper) receive every sibling alert and can act on tasks."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

import app.agent.nodes as nodes_module
import app.api.webhooks as webhooks_module
import app.scheduler.escalation as esc_module
import app.services.tasks as tasks_module
from app.agent.nodes import node_assign, node_scam_guardrail
from app.config import settings
from app.db.models import (
    Artifact, ArtifactType, DoseLog, DoseStatus, Household, Medication, Member, MemberRole,
    Task, TaskCategory, TaskStatus, VitalKind, VitalOp, VitalThreshold,
)
from app.db.session import AsyncSessionLocal
from app.main import app
from app.services.health import escalate_missed_doses
from app.services.recipients import get_alert_recipients
from app.services.tasks import ClaimResult, DoneResult, claim_task, complete_task


def phone():
    return f"+9197{uuid.uuid4().int % 100000000:08d}"


async def make_household(*, with_children=True):
    """Household with a parent, two children (optional) and one guardian."""
    async with AsyncSessionLocal() as db:
        hh = Household(name=f"G1 {uuid.uuid4().hex[:6]}", primary_language="mr")
        db.add(hh)
        await db.flush()
        members = {
            "aai": Member(household_id=hh.id, name="Aai", role=MemberRole.parent, phone=phone()),
            "kavita": Member(household_id=hh.id, name="Kavita", role=MemberRole.helper, phone=phone()),
        }
        if with_children:
            members["rohan"] = Member(household_id=hh.id, name="Rohan", role=MemberRole.child, phone=phone())
            members["priya"] = Member(household_id=hh.id, name="Priya", role=MemberRole.child, telegram_id=uuid.uuid4().hex[:10])
        db.add_all(members.values())
        await db.commit()
        return hh.id, {k: m.id for k, m in members.items()}


def recorder():
    calls = []

    async def fake_notify(*args, **kwargs):
        member = kwargs.get("member") or (args[0] if args else None)
        calls.append((member.id, kwargs.get("text") or (args[1] if len(args) > 1 else "")))
        return True

    return calls, fake_notify


# --- get_alert_recipients ---------------------------------------------------

async def test_recipients_are_children_and_guardians_of_the_household_only():
    hh_id, ids = await make_household()
    other_hh, other_ids = await make_household()
    async with AsyncSessionLocal() as db:
        db.add(Member(household_id=hh_id, name="NoContact", role=MemberRole.helper))
        await db.commit()

    got = {m.id for m in await get_alert_recipients(hh_id)}

    assert got == {ids["rohan"], ids["priya"], ids["kavita"]}
    assert ids["aai"] not in got
    assert not got & set(other_ids.values())


async def test_recipients_list_children_before_guardians():
    hh_id, ids = await make_household()
    roles = [m.role for m in await get_alert_recipients(hh_id)]
    assert roles == [MemberRole.child, MemberRole.child, MemberRole.helper]


# --- alerts reach the guardian ---------------------------------------------

async def test_new_task_notifies_every_child_and_the_guardian(monkeypatch):
    hh_id, ids = await make_household()
    calls, fake = recorder()
    monkeypatch.setattr(webhooks_module, "notify", fake)

    await webhooks_module._notify_siblings_new_task(hh_id, 1, "New task")

    assert sorted(c[0] for c in calls) == sorted([ids["rohan"], ids["priya"], ids["kavita"]])


async def test_escalation_reaches_the_guardian(monkeypatch):
    hh_id, ids = await make_household()
    async with AsyncSessionLocal() as db:
        db.add(Task(
            household_id=hh_id, category=TaskCategory.bill, title="Water bill",
            due_date=(datetime.now(timezone.utc) + timedelta(days=1)).replace(tzinfo=None),
            status=TaskStatus.confirmed,
        ))
        await db.commit()
    calls, fake = recorder()
    monkeypatch.setattr(esc_module, "notify", fake)
    noon = datetime(2026, 11, 4, 12, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    monkeypatch.setattr(esc_module, "get_ist_now", lambda: noon)

    await esc_module.run_escalation()

    assert ids["kavita"] in {c[0] for c in calls}


@pytest.mark.parametrize("with_owner", [True, False])
async def test_missed_dose_reaches_the_guardian(monkeypatch, with_owner):
    hh_id, ids = await make_household()
    now = datetime(2026, 11, 4, 12, 0)
    async with AsyncSessionLocal() as db:
        med = Medication(
            household_id=hh_id, member_id=ids["aai"], name="Amlodipine", dose_text="5mg",
            times=["09:00"], owner_child_id=ids["rohan"] if with_owner else None, active=True,
        )
        db.add(med)
        await db.flush()
        db.add(DoseLog(
            medication_id=med.id, scheduled_for=datetime(2026, 11, 4, 9, 0),
            status=DoseStatus.pending, reminder_sent_at=now - timedelta(minutes=180),
        ))
        await db.commit()
    calls, fake = recorder()
    monkeypatch.setattr("app.services.health.notify", fake)

    await escalate_missed_doses(now=now)

    notified = {c[0] for c in calls}
    assert ids["kavita"] in notified
    assert ids["aai"] not in notified
    if with_owner:
        assert ids["priya"] not in notified  # owner child still chosen over other children


async def test_family_limit_alert_reaches_the_guardian(monkeypatch):
    hh_id, ids = await make_household()
    async with AsyncSessionLocal() as db:
        db.add(VitalThreshold(
            household_id=hh_id, member_id=ids["aai"], kind=VitalKind.pulse, field="value_1",
            op=VitalOp.gt, limit=100.0, set_by_member_id=ids["rohan"], active=True,
        ))
        await db.commit()
    calls, fake = recorder()
    monkeypatch.setattr("app.api.health.notify", fake)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/health/{hh_id}/vitals/device",
            json={"member_id": ids["aai"], "kind": "pulse", "value": 130, "device_name": "Watch"},
            headers={"X-Admin-Token": settings.admin_secret},
        )
    assert res.status_code in (200, 201), res.text
    assert ids["kavita"] in {c[0] for c in calls}


async def test_voice_vital_alert_reaches_the_guardian(monkeypatch):
    hh_id, ids = await make_household()
    async with AsyncSessionLocal() as db:
        aai = await db.get(Member, ids["aai"])
        art = Artifact(household_id=hh_id, type=ArtifactType.voice, file_url="test://v", raw_text="बीपी १६०/९० आहे")
        db.add(art)
        db.add(VitalThreshold(
            household_id=hh_id, member_id=ids["aai"], kind=VitalKind.bp, field="value_1",
            op=VitalOp.gt, limit=140.0, set_by_member_id=ids["rohan"], active=True,
        ))
        await db.commit()
        art_id, aai_phone = art.id, aai.phone
    calls, fake = recorder()
    monkeypatch.setattr(nodes_module, "notify", fake)

    await nodes_module.node_vital({
        "household_id": hh_id, "artifact_id": art_id, "raw_text": "बीपी १६०/९० आहे", "chat_id": aai_phone,
    })

    assert ids["kavita"] in {c[0] for c in calls}


async def test_scam_warning_reaches_the_guardian(monkeypatch):
    hh_id, ids = await make_household()
    calls, fake = recorder()
    monkeypatch.setattr(nodes_module, "notify", fake)

    await node_scam_guardrail({"raw_text": "Share your OTP now", "household_id": hh_id})

    assert ids["kavita"] in {c[0] for c in calls}


# --- guardians can act -----------------------------------------------------

async def test_guardian_can_claim_and_complete_a_task(monkeypatch):
    hh_id, ids = await make_household()
    _, fake = recorder()
    monkeypatch.setattr(tasks_module, "notify_parents_task_done", fake)
    async with AsyncSessionLocal() as db:
        task = Task(household_id=hh_id, category=TaskCategory.bill, title="Gas bill", status=TaskStatus.confirmed)
        db.add(task)
        await db.commit()
        kavita = await db.get(Member, ids["kavita"])
        task_id = task.id

    claim_res, task = await claim_task(task_id, kavita)
    assert claim_res == ClaimResult.ok
    assert task.assignee_id == ids["kavita"]

    done_res, task = await complete_task(task_id, kavita.name, kavita.household_id)
    assert done_res == DoneResult.ok
    assert task.status == TaskStatus.done


async def test_guardian_from_another_household_is_rejected():
    hh_id, _ = await make_household()
    _, other_ids = await make_household()
    async with AsyncSessionLocal() as db:
        task = Task(household_id=hh_id, category=TaskCategory.bill, title="Gas bill", status=TaskStatus.confirmed)
        db.add(task)
        await db.commit()
        outsider = await db.get(Member, other_ids["kavita"])
        task_id = task.id

    claim_res, _ = await claim_task(task_id, outsider)
    done_res, _ = await complete_task(task_id, outsider.name, outsider.household_id)
    assert claim_res == ClaimResult.not_found
    assert done_res == DoneResult.not_found


# --- auto-assignment -------------------------------------------------------

async def _assign(hh_id):
    async with AsyncSessionLocal() as db:
        art = Artifact(household_id=hh_id, type=ArtifactType.image, file_url="test://p", raw_text="bill")
        db.add(art)
        await db.commit()
        art_id = art.id
    return await node_assign({
        "household_id": hh_id, "category": "bill", "artifact_id": art_id,
        "raw_text": "bill", "extracted": {}, "verify_passed": True,
    })


async def test_auto_assignment_never_picks_a_guardian():
    hh_id, ids = await make_household()
    async with AsyncSessionLocal() as db:
        kavita = await db.get(Member, ids["kavita"])
        kavita.categories_owned = ["bill"]  # even a category owner
        await db.commit()

    res = await _assign(hh_id)
    assert res["assignee_id"] in (ids["rohan"], ids["priya"])


async def test_auto_assignment_leaves_task_unassigned_when_only_a_guardian_exists():
    hh_id, _ = await make_household(with_children=False)
    res = await _assign(hh_id)
    assert res["assignee_id"] is None


# --- members API -----------------------------------------------------------

async def test_members_api_creates_edits_and_lists_guardians():
    hh_id, _ = await make_household(with_children=False)
    headers = {"X-Admin-Token": settings.admin_secret}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/members/", headers=headers, json={
            "household_id": hh_id, "name": "Sunita", "role": "helper", "phone": phone(), "language": "hi",
        })
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["role"] == "helper" and body["language"] == "hi"

        edited = await client.patch(f"/members/{body['id']}", headers=headers, json={"name": "Sunita Tai", "language": "mr"})
        assert edited.status_code == 200, edited.text
        assert edited.json()["name"] == "Sunita Tai" and edited.json()["language"] == "mr"

        listed = await client.get(f"/members/{hh_id}", headers=headers)
        assert any(m["name"] == "Sunita Tai" and m["role"] == "helper" for m in listed.json())

        bad = await client.post("/members/", headers=headers, json={"household_id": hh_id, "name": "X", "role": "boss"})
        assert bad.status_code == 422

        no_auth = await client.post("/members/", json={"household_id": hh_id, "name": "X", "role": "helper"})
        assert no_auth.status_code == 401
