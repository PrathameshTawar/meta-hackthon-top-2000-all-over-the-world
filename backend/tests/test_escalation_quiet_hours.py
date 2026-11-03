import pytest
import uuid
from datetime import datetime, timezone, timedelta
from app.db.session import AsyncSessionLocal
from app.db.models import Household, Member, MemberRole, Task, TaskStatus, TaskCategory, Event
from app.scheduler.escalation import run_escalation
import app.scheduler.escalation as esc_module

IST = timezone(timedelta(hours=5, minutes=30))


def unique_phone():
    return f"+9198{uuid.uuid4().int % 100000000:08d}"


@pytest.mark.asyncio
async def test_escalation_quiet_hours_tracking_and_no_lost_escalations(monkeypatch):
    """
    Tier 1 Test N-1: Escalations during quiet hours are delivered once quiet hours end.
    Delivery is tracked per child so no notifications are lost or duplicated.
    """
    notified_members = []

    async def mock_notify(**kwargs):
        notified_members.append(kwargs)

    monkeypatch.setattr(esc_module, "notify", mock_notify)

    # Setup household with two siblings:
    # Rohan in India (IST, 22:00-07:00 quiet hours)
    # Priya in New York (America/New_York, 22:00-07:00 quiet hours)
    async with AsyncSessionLocal() as db:
        hh = Household(name="Quiet Hours Test Household", primary_language="mr")
        db.add(hh)
        await db.commit()
        await db.refresh(hh)

        rohan = Member(
            household_id=hh.id,
            name="Rohan",
            role=MemberRole.child,
            phone=unique_phone(),
            timezone="Asia/Kolkata",
            quiet_hours_start=22,
            quiet_hours_end=7,
        )
        priya = Member(
            household_id=hh.id,
            name="Priya",
            role=MemberRole.child,
            phone=unique_phone(),
            timezone="America/New_York",
            quiet_hours_start=22,
            quiet_hours_end=7,
        )
        db.add_all([rohan, priya])
        await db.commit()
        await db.refresh(rohan)
        await db.refresh(priya)

        # Due tomorrow
        due_dt = datetime.now(timezone.utc) + timedelta(days=1)
        task = Task(
            household_id=hh.id,
            category=TaskCategory.bill,
            title="Electricity Bill",
            amount="₹1,200",
            due_date=due_dt.replace(tzinfo=None),
            status=TaskStatus.confirmed,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        task_id = task.id
        hh_id = hh.id

    # 1. Run at 00:30 IST (midnight in India, both or India in quiet hours)
    time_0030_ist = datetime(2026, 11, 3, 0, 30, tzinfo=IST)
    monkeypatch.setattr(esc_module, "get_ist_now", lambda: time_0030_ist)

    escalated = await run_escalation(simulated_days_ahead=0)
    # Rohan is in quiet hours at 00:30 IST (22:00 to 07:00).
    # He must NOT be notified.
    rohan_notified_at_night = [n for n in notified_members if n["member"].name == "Rohan"]
    assert len(rohan_notified_at_night) == 0

    # 2. Run at 08:00 IST (morning in India: 08:00 IST = 21:30 or 22:30 previous night in NY -> Priya in quiet hours)
    time_0800_ist = datetime(2026, 11, 3, 8, 0, tzinfo=IST)
    monkeypatch.setattr(esc_module, "get_ist_now", lambda: time_0800_ist)

    await run_escalation(simulated_days_ahead=0)
    # Rohan is outside quiet hours now -> Rohan must be notified!
    rohan_notified = [n for n in notified_members if n["member"].name == "Rohan"]
    assert len(rohan_notified) == 1, "Rohan must receive exactly 1 notification after quiet hours end"

    # Task should now be marked escalated
    async with AsyncSessionLocal() as db:
        t = await db.get(Task, task_id)
        assert t.status == TaskStatus.escalated

    # 3. Third run at 09:00 IST -> Rohan must NOT be notified again!
    time_0900_ist = datetime(2026, 11, 3, 9, 0, tzinfo=IST)
    monkeypatch.setattr(esc_module, "get_ist_now", lambda: time_0900_ist)

    await run_escalation(simulated_days_ahead=0)
    rohan_notified_repeat = [n for n in notified_members if n["member"].name == "Rohan"]
    assert len(rohan_notified_repeat) == 1, "Rohan must not receive duplicate notifications"

    # 4. Fourth run when New York is in daytime (e.g. 18:00 IST = 08:30 NY time)
    time_1800_ist = datetime(2026, 11, 3, 18, 0, tzinfo=IST)
    monkeypatch.setattr(esc_module, "get_ist_now", lambda: time_1800_ist)

    await run_escalation(simulated_days_ahead=0)
    priya_notified = [n for n in notified_members if n["member"].name == "Priya"]
    assert len(priya_notified) == 1, "Priya must be notified once her local quiet hours end"

