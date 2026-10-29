from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List

from app.db.session import get_db
from app.db.models import Member, MemberRole

router = APIRouter()


class MemberOut(BaseModel):
    id: int
    household_id: int
    name: str
    role: str
    telegram_id: Optional[str]
    categories_owned: Optional[List[str]]

    class Config:
        from_attributes = True


class MemberCreate(BaseModel):
    household_id: int
    name: str
    role: str
    telegram_id: Optional[str] = None
    categories_owned: Optional[List[str]] = []


@router.get("/{household_id}", response_model=list[MemberOut])
async def list_members(household_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Member).where(Member.household_id == household_id)
    )
    return result.scalars().all()


@router.post("/", response_model=MemberOut, status_code=201)
async def create_member(data: MemberCreate, db: AsyncSession = Depends(get_db)):
    member = Member(
        household_id=data.household_id,
        name=data.name,
        role=MemberRole(data.role),
        telegram_id=data.telegram_id,
        categories_owned=data.categories_owned or [],
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member
