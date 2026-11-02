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
    language: str = "mr"
    timezone: Optional[str] = "Asia/Kolkata"
    quiet_hours_start: Optional[int] = 22
    quiet_hours_end: Optional[int] = 7

    class Config:
        from_attributes = True


class MemberCreate(BaseModel):
    household_id: int
    name: str
    role: str
    telegram_id: Optional[str] = None
    categories_owned: Optional[List[str]] = []
    language: Optional[str] = "mr"
    timezone: Optional[str] = "Asia/Kolkata"
    quiet_hours_start: Optional[int] = 22
    quiet_hours_end: Optional[int] = 7


class MemberUpdateLanguage(BaseModel):
    language: str


@router.get("/{household_id}", response_model=list[MemberOut])
async def list_members(household_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Member).where(Member.household_id == household_id)
    )
    return result.scalars().all()


@router.patch("/{member_id}/language", response_model=MemberOut)
async def update_member_language(
    member_id: int,
    data: MemberUpdateLanguage,
    db: AsyncSession = Depends(get_db),
):
    if data.language not in ("mr", "hi", "en"):
        raise HTTPException(status_code=422, detail="Language must be one of: mr, hi, en")
    member = await db.get(Member, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    member.language = data.language
    await db.commit()
    await db.refresh(member)
    return member


@router.post("/", response_model=MemberOut, status_code=201)
async def create_member(data: MemberCreate, db: AsyncSession = Depends(get_db)):
    member = Member(
        household_id=data.household_id,
        name=data.name,
        role=MemberRole(data.role),
        telegram_id=data.telegram_id,
        categories_owned=data.categories_owned or [],
        language=data.language or "mr",
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member
