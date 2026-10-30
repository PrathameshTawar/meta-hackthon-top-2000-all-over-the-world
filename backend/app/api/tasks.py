from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.db.session import get_db
from app.db.models import Task, TaskStatus, Evidence

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class EvidenceOut(BaseModel):
    id: int
    artifact_id: int
    quoted_span: str
    field_name: str

    class Config:
        from_attributes = True


class TaskOut(BaseModel):
    id: int
    household_id: int
    category: str
    title: str
    amount: Optional[str]
    due_date: Optional[datetime]
    payee: Optional[str]
    status: str
    assignee_id: Optional[int]
    confidence: Optional[float]
    created_at: datetime
    updated_at: datetime
    evidence_items: list[EvidenceOut] = []

    class Config:
        from_attributes = True


class TaskUpdate(BaseModel):
    status: Optional[str] = None
    assignee_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/{household_id}", response_model=list[TaskOut])
async def list_tasks(household_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Task)
        .where(Task.household_id == household_id)
        .options(selectinload(Task.evidence_items))
        .order_by(Task.created_at.desc())
    )
    return result.scalars().all()


@router.get("/detail/{task_id}", response_model=TaskOut)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id)
        .options(selectinload(Task.evidence_items))
    )
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(task_id: int, update: TaskUpdate, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    status_changed_to_done = False
    if update.status:
        new_status = TaskStatus(update.status)
        if new_status == TaskStatus.done and task.status != TaskStatus.done:
            status_changed_to_done = True
        task.status = new_status
    if update.assignee_id is not None:
        task.assignee_id = update.assignee_id
    task.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(task)

    if status_changed_to_done:
        try:
            from app.api.webhooks import notify_parents_task_done
            await notify_parents_task_done(task, completed_by_name="कुटुंबातील सदस्य (वेब बोर्ड)")
        except Exception:
            pass

    return task
