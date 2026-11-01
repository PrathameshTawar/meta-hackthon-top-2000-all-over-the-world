"""
Escalation scheduler — runs hourly via APScheduler.
If a task's due_date is within N days and it's still unclaimed, ping all siblings.
Uses India Standard Time (Asia/Kolkata, UTC+5:30) for accurate midnight date comparisons.
Also provides a simulation runner for the 'simulate 3 days later' demo button.
"""
from datetime import datetime, timezone, timedelta
import logging
import httpx
from sqlalchemy import select

from app.config import settings
from app.db.models import Task, TaskStatus, Member, MemberRole, Event
from app.db.session import AsyncSessionLocal
from app.api.webhooks import notify, _clean_template_param

logger = logging.getLogger(__name__)


def get_ist_now() -> datetime:
    """Return timezone-aware current time in India (IST, UTC+5:30)."""
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist)


async def _send_telegram(chat_id: str, text: str):
    if not settings.telegram_bot_token:
        logger.info(f"[SIMULATED TELEGRAM to {chat_id}]: {text}")
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            )
    except Exception as exc:
        logger.warning(f"Failed to send Telegram notification to {chat_id}: {exc}")


async def run_escalation(simulated_days_ahead: int = 0) -> list[int]:
    """
    Check for tasks approaching their deadline with no assignee.
    simulated_days_ahead: allows fast-forwarding the clock for the demo button.
    Returns list of escalated task IDs.
    """
    now = get_ist_now() + timedelta(days=simulated_days_ahead)
    threshold = now + timedelta(days=settings.escalation_days_before)
    escalated_ids = []

    # Format threshold without tzinfo for DB query compatibility
    threshold_naive = threshold.replace(tzinfo=None)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Task).where(
                Task.due_date <= threshold_naive,
                Task.status.in_([TaskStatus.new, TaskStatus.confirmed, TaskStatus.needs_review]),
            )
        )
        overdue_tasks = result.scalars().all()

        for task in overdue_tasks:
            # Get all children in the household
            members_result = await db.execute(
                select(Member).where(
                    Member.household_id == task.household_id,
                    Member.role == MemberRole.child,
                )
            )
            children = members_result.scalars().all()

            task_due_ist = task.due_date.replace(tzinfo=timezone(timedelta(hours=5, minutes=30))) if task.due_date else now
            days_left = max(0, (task_due_ist - now).days)

            # Smartwatch-friendly first line (action + deadline)
            watch_line = f"⚠️ {task.title} due in {days_left}d, unclaimed"
            message = (
                f"*{watch_line}*\n"
                f"Amount: {task.amount or 'N/A'}\n"
                f"👉 Claim immediately on your Saath board: {settings.frontend_url}"
            )

            for child in children:
                await notify(
                    member=child,
                    text=message,
                    buttons=[{"id": f"claim:{task.id}", "title": "Claim Task"}],
                    template_name="saath_task_escalation",
                    template_params=[_clean_template_param(task.title), f"{days_left}d"],
                    template_button_payload=f"claim:{task.id}",
                    template_language="en_US",
                )

            # Update status
            task.status = TaskStatus.escalated
            escalated_ids.append(task.id)

            # Add event to audit log
            db.add(Event(
                household_id=task.household_id,
                task_id=task.id,
                actor="scheduler:escalate",
                action="escalated",
                reason=f"Task unclaimed and due within {days_left} days",
                payload={"days_left": days_left, "simulated_days_ahead": simulated_days_ahead, "watch_line": watch_line},
            ))

        await db.commit()
    return escalated_ids


async def run_health_schedule():
    """Runs health medication scheduling, due reminders, and adherence escalation."""
    from app.services.health import ensure_todays_doses, send_due_reminders, escalate_missed_doses
    try:
        await ensure_todays_doses()
        await send_due_reminders()
        await escalate_missed_doses()
    except Exception as exc:
        logger.error(f"Health scheduler execution error: {exc}", exc_info=True)


# ---------------------------------------------------------------------------
# APScheduler setup
# ---------------------------------------------------------------------------

def start_scheduler():
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        scheduler = AsyncIOScheduler()
        scheduler.add_job(run_escalation, "interval", hours=1, id="escalation")
        scheduler.add_job(run_health_schedule, "interval", minutes=5, id="health_schedule")
        scheduler.start()
        logger.info("Escalation and health scheduler started (hourly tasks, 5-min health).")
        return scheduler
    except Exception as exc:
        logger.warning(f"Could not start APScheduler: {exc}")
        return None
