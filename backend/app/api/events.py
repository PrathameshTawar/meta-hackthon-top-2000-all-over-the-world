from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime

from app.db.session import get_db
from app.db.models import Event

router = APIRouter()


class EventOut(BaseModel):
    id: int
    household_id: Optional[int]
    task_id: Optional[int]
    actor: str
    action: str
    reason: Optional[str]
    payload: Optional[dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/{household_id}", response_model=list[EventOut])
async def list_events(household_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Event)
        .where((Event.household_id == household_id) | (Event.household_id.is_(None)))
        .order_by(Event.created_at.desc())
        .limit(100)
    )
    return result.scalars().all()


@router.get("/task/{task_id}", response_model=list[EventOut])
async def list_task_events(task_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Event)
        .where(Event.task_id == task_id)
        .order_by(Event.created_at.desc())
    )
    return result.scalars().all()
