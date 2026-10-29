from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.db.session import get_db
from app.db.models import Artifact

router = APIRouter()


class ArtifactOut(BaseModel):
    id: int
    household_id: int
    type: str
    file_url: str
    raw_text: Optional[str]
    received_at: datetime

    class Config:
        from_attributes = True


@router.get("/{household_id}", response_model=list[ArtifactOut])
async def list_artifacts(household_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Artifact)
        .where(Artifact.household_id == household_id)
        .order_by(Artifact.received_at.desc())
        .limit(50)
    )
    return result.scalars().all()
