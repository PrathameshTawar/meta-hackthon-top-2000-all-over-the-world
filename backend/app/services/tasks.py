"""
Shared task management services for Saath.
Centralizes claim, complete, and recurrence logic across Telegram, WhatsApp, and Web channels.
"""
from datetime import datetime, timedelta
import enum
import logging
from typing import Optional

from app.db.models import Task, TaskStatus, Member, Event
from app.db.session import AsyncSessionLocal
from app.api.webhooks import notify_parents_task_done

logger = logging.getLogger(__name__)


class ClaimResult(enum.Enum):
    ok = "ok"
    already_yours = "already_yours"
    taken = "taken"
    done = "done"
    not_found = "not_found"


class DoneResult(enum.Enum):
    ok = "ok"
    already_done = "already_done"
    not_found = "not_found"


async def claim_task(task_id: int, member: Member) -> tuple[ClaimResult, Optional[Task]]:
    """
    Idempotent task claim service:
    - Task not found or member's household doesn't match -> (not_found, None)
    - Task is already done -> (done, task)
    - Task already claimed by another sibling -> (taken, task)
    - Task already claimed by this member -> (already_yours, task)
    - Otherwise -> claims task, sets assignee, writes audit Event, returns (ok, task)
    """
    async with AsyncSessionLocal() as db:
        task = await db.get(Task, task_id)
        if not task or task.household_id != member.household_id:
            return ClaimResult.not_found, None

        if task.status == TaskStatus.done:
            return ClaimResult.done, task

        if task.status == TaskStatus.claimed and task.assignee_id is not None:
            if task.assignee_id == member.id:
                return ClaimResult.already_yours, task
            else:
                return ClaimResult.taken, task

        # Valid claim
        task.status = TaskStatus.claimed
        task.assignee_id = member.id
        task.updated_at = datetime.utcnow()

        db.add(Event(
            household_id=task.household_id,
            task_id=task.id,
            actor=f"member:{member.name}",
            action="claimed",
            reason=f"Claimed by {member.name}",
            payload={"member_id": member.id, "assignee_name": member.name},
        ))
        await db.commit()
        await db.refresh(task)
        return ClaimResult.ok, task


async def complete_task(
    task_id: int,
    actor_name: str,
    household_id: Optional[int] = None,
) -> tuple[DoneResult, Optional[Task]]:
    """
    Idempotent task completion service:
    - Task not found or household doesn't match -> (not_found, None)
    - Task already marked done -> (already_done, task) (no second notification, no duplicate recurrence)
    - Otherwise -> marks done, generates recurring monthly task if applicable, notifies parents, writes audit Event, returns (ok, task)
    """
    async with AsyncSessionLocal() as db:
        task = await db.get(Task, task_id)
        if not task or (household_id is not None and task.household_id != household_id):
            return DoneResult.not_found, None

        if task.status == TaskStatus.done:
            return DoneResult.already_done, task

        task.status = TaskStatus.done
        task.updated_at = datetime.utcnow()

        # Handle monthly recurrence
        if task.recurrence == "monthly" and task.due_date:
            next_due = task.due_date + timedelta(days=30)
            next_task = Task(
                household_id=task.household_id,
                category=task.category,
                title=task.title,
                amount=task.amount,
                due_date=next_due,
                payee=task.payee,
                status=TaskStatus.confirmed,
                assignee_id=task.assignee_id,
                recurrence="monthly",
            )
            db.add(next_task)

        db.add(Event(
            household_id=task.household_id,
            task_id=task.id,
            actor=f"member:{actor_name}",
            action="completed",
            reason=f"Marked completed by {actor_name}",
            payload={"actor": actor_name},
        ))
        await db.commit()
        await db.refresh(task)

    # Notify parents only on first successful completion
    try:
        await notify_parents_task_done(task, completed_by_name=actor_name)
    except Exception as exc:
        logger.warning(f"Failed to notify parents for task #{task.id}: {exc}")

    return DoneResult.ok, task
