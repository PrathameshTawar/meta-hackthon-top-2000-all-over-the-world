from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.db.session import get_db
from app.db.models import Household

router = APIRouter()


class HouseholdOut(BaseModel):
    id: int
    name: str
    primary_language: str

    class Config:
        from_attributes = True


class HouseholdCreate(BaseModel):
    name: str
    primary_language: Optional[str] = "mr"


@router.post("/", response_model=HouseholdOut, status_code=201)
async def create_household(data: HouseholdCreate, db: AsyncSession = Depends(get_db)):
    household = Household(name=data.name, primary_language=data.primary_language or "mr")
    db.add(household)
    await db.commit()
    await db.refresh(household)
    return household


@router.get("/{household_id}", response_model=HouseholdOut)
async def get_household(household_id: int, db: AsyncSession = Depends(get_db)):
    household = await db.get(Household, household_id)
    if not household:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Household not found")
    return household
