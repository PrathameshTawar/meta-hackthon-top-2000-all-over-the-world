import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from datetime import datetime

from app.main import app
from app.config import settings
from app.db.models import Household, Member, MemberRole
from app.db.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_h1_data_models_and_api_skeleton(monkeypatch):
    monkeypatch.setattr(settings, "admin_secret", "saath_admin_secret_demo")

    def unique_phone():
        return f"+919{uuid.uuid4().int % 1000000000:09d}"

    # 1. Setup a test household with a parent and child, plus another household
    async with AsyncSessionLocal() as db:
        h1 = Household(name="Health Family 1", primary_language="mr")
        h2 = Household(name="Health Family 2", primary_language="mr")
        db.add_all([h1, h2])
        await db.commit()
        await db.refresh(h1)
        await db.refresh(h2)

        parent1 = Member(household_id=h1.id, name="Aai", role=MemberRole.parent, phone=unique_phone())
        child1 = Member(household_id=h1.id, name="Rohan", role=MemberRole.child, phone=unique_phone())
        parent2 = Member(household_id=h2.id, name="Other Parent", role=MemberRole.parent, phone=unique_phone())
        db.add_all([parent1, child1, parent2])
        await db.commit()
        await db.refresh(parent1)
        await db.refresh(child1)
        await db.refresh(parent2)

        h1_id = h1.id
        parent1_id = parent1.id
        child1_id = child1.id
        parent2_id = parent2.id

    headers = {"X-Admin-Token": "saath_admin_secret_demo"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test 1: Create medication with invalid time -> 422
        res_invalid_time = await client.post(
            "/health/medications",
            json={
                "household_id": h1_id,
                "member_id": parent1_id,
                "name": "Blood Pressure Pill",
                "dose_text": "1 tablet",
                "times": ["25:99"],
                "owner_child_id": child1_id,
            },
            headers=headers,
        )
        assert res_invalid_time.status_code == 422, f"Expected 422 for invalid time, got {res_invalid_time.status_code}"

        # Test 2: Member from another household -> 404
        res_wrong_household = await client.post(
            "/health/medications",
            json={
                "household_id": h1_id,
                "member_id": parent2_id,  # belongs to h2!
                "name": "Blood Pressure Pill",
                "dose_text": "1 tablet",
                "times": ["08:00"],
                "owner_child_id": child1_id,
            },
            headers=headers,
        )
        assert res_wrong_household.status_code == 404, f"Expected 404 for member from another household, got {res_wrong_household.status_code}"

        # Test 3: Member is not a parent -> 422
        res_not_parent = await client.post(
            "/health/medications",
            json={
                "household_id": h1_id,
                "member_id": child1_id,  # child, not parent!
                "name": "Blood Pressure Pill",
                "dose_text": "1 tablet",
                "times": ["08:00"],
                "owner_child_id": child1_id,
            },
            headers=headers,
        )
        assert res_not_parent.status_code == 422, f"Expected 422 for non-parent member_id, got {res_not_parent.status_code}"

        # Test 4: Valid creation of medication
        res_create_med = await client.post(
            "/health/medications",
            json={
                "household_id": h1_id,
                "member_id": parent1_id,
                "name": "Amlodipine",
                "dose_text": "1 tab",
                "times": ["08:00", "20:00"],
                "owner_child_id": child1_id,
            },
            headers=headers,
        )
        assert res_create_med.status_code in (200, 201), f"Expected 200/201, got {res_create_med.status_code}: {res_create_med.text}"
        med_id = res_create_med.json()["id"]

        # Test 5: Valid creation of threshold
        res_create_thresh = await client.post(
            "/health/thresholds",
            json={
                "household_id": h1_id,
                "member_id": parent1_id,
                "kind": "bp",
                "field": "value_1",
                "op": "gt",
                "limit": 150.0,
                "note": "Doctor advised",
                "set_by_member_id": child1_id,
            },
            headers=headers,
        )
        assert res_create_thresh.status_code in (200, 201), f"Expected 200/201, got {res_create_thresh.status_code}: {res_create_thresh.text}"

        # Test 6: Summary returns created items
        res_summary = await client.get(f"/health/{h1_id}/summary", headers=headers)
        assert res_summary.status_code == 200, f"Expected 200, got {res_summary.status_code}"
        summary_data = res_summary.json()
        assert len(summary_data["active_medications"]) >= 1
        assert any(m["id"] == med_id for m in summary_data["active_medications"])
        assert len(summary_data["active_thresholds"]) >= 1


# ---------------------------------------------------------------------------
# H-2 Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_h2_medicine_reminders_and_escalation(monkeypatch):
    from app.services.health import (
        ensure_todays_doses,
        send_due_reminders,
        escalate_missed_doses,
        record_dose_taken,
        DoseTakenResult,
    )
    from app.db.models import Medication, DoseLog, DoseStatus, Member, MemberRole, Household
    from app.db.session import AsyncSessionLocal
    from sqlalchemy import select
    from datetime import datetime, timedelta

    # Setup
    async with AsyncSessionLocal() as db:
        h1 = Household(name="H2 Test Family 1", primary_language="mr")
        h2 = Household(name="H2 Test Family 2", primary_language="mr")
        db.add_all([h1, h2])
        await db.commit()
        await db.refresh(h1)
        await db.refresh(h2)

        p1 = Member(household_id=h1.id, name="Aai", role=MemberRole.parent, phone=f"+919{uuid.uuid4().int % 1000000000:09d}")
        c1 = Member(household_id=h1.id, name="Rohan", role=MemberRole.child, phone=f"+919{uuid.uuid4().int % 1000000000:09d}")
        p2 = Member(household_id=h2.id, name="Stranger", role=MemberRole.parent, phone=f"+919{uuid.uuid4().int % 1000000000:09d}")
        db.add_all([p1, c1, p2])
        await db.commit()
        await db.refresh(p1)
        await db.refresh(c1)
        await db.refresh(p2)

        med = Medication(
            household_id=h1.id,
            member_id=p1.id,
            name="Metformin",
            dose_text="500mg",
            times=["09:00", "21:00"],
            owner_child_id=c1.id,
            active=True,
        )
        db.add(med)
        await db.commit()
        await db.refresh(med)
        med_id = med.id
        p1_id = p1.id
        c1_id = c1.id
        p2_id = p2.id
        h1_id = h1.id
        h2_id = h2.id

    now = datetime(2026, 11, 2, 9, 30)

    # 1. Doses created once per time per day
    created_count_1 = await ensure_todays_doses(now=now)
    assert created_count_1 >= 2, "Expected at least 2 doses created for 09:00 and 21:00"
    created_count_2 = await ensure_todays_doses(now=now)
    assert created_count_2 == 0, "Second call must create 0 doses (idempotent)"

    # 2. Reminder sent once for scheduled_for <= now
    notifications = []
    async def mock_notify(member, text, **kwargs):
        notifications.append((member.id, text, kwargs))
        return True
    monkeypatch.setattr("app.services.health.notify", mock_notify)

    sent_count_1 = await send_due_reminders(now=now)
    assert sent_count_1 >= 1, "09:00 dose should receive a reminder at 09:30"
    assert any("Metformin" in n[1] for n in notifications)

    notifications.clear()
    sent_count_2 = await send_due_reminders(now=now)
    assert sent_count_2 == 0, "Second reminder call must not resend"
    assert len(notifications) == 0

    # Get the 09:00 dose
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(DoseLog)
            .where(DoseLog.medication_id == med_id, DoseLog.scheduled_for == datetime(2026, 11, 2, 9, 0))
        )
        dose_9am = res.scalars().first()
        assert dose_9am is not None
        assert dose_9am.reminder_sent_at is not None
        dose_9am_id = dose_9am.id

    # 3. Tap marks taken and second tap is idempotent
    async with AsyncSessionLocal() as db:
        p1_member = await db.get(Member, p1_id)
        res_taken, d_taken, reply = await record_dose_taken(dose_9am_id, p1_member)
        assert res_taken == DoseTakenResult.ok
        assert d_taken.status == DoseStatus.taken
        assert d_taken.responded_at is not None
        assert "नोंद केली" in reply

        # Second tap
        res_taken_2, _, reply_2 = await record_dose_taken(dose_9am_id, p1_member)
        assert res_taken_2 == DoseTakenResult.already_taken
        assert "आधीच नोंदवले आहे" in reply_2

    # 4. Untapped dose escalates once after 120 minutes
    # Create another dose that missed confirmation
    async with AsyncSessionLocal() as db:
        missed_dose = DoseLog(
            medication_id=med_id,
            scheduled_for=datetime(2026, 11, 2, 6, 0),
            status=DoseStatus.pending,
            reminder_sent_at=now - timedelta(minutes=130),
        )
        db.add(missed_dose)
        await db.commit()
        await db.refresh(missed_dose)
        missed_id = missed_dose.id

    notifications.clear()
    esc_count = await escalate_missed_doses(now=now)
    assert esc_count >= 1
    assert any("hasn't confirmed taking Metformin" in n[1] for n in notifications)

    # Escalated once
    esc_count_2 = await escalate_missed_doses(now=now)
    assert esc_count_2 == 0, "Dose should not escalate a second time"

    # 5. Late tap after escalation sends update to owner child
    notifications.clear()
    async with AsyncSessionLocal() as db:
        p1_member = await db.get(Member, p1_id)
        res_late, d_late, reply_late = await record_dose_taken(missed_id, p1_member)
        assert res_late == DoseTakenResult.late_ok
        assert d_late.status == DoseStatus.taken
        assert any(c1_id == n[0] and "has now taken Metformin" in n[1] for n in notifications)

    # 6. Cross-household tap rejected
    async with AsyncSessionLocal() as db:
        p2_member = await db.get(Member, p2_id)
        res_wrong, _, _ = await record_dose_taken(dose_9am_id, p2_member)
        assert res_wrong == DoseTakenResult.household_mismatch
