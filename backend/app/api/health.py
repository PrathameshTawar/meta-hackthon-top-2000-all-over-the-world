import re
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, field_validator
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.db.models import (
    Household, Member, MemberRole,
    Medication, DoseLog, DoseStatus,
    Vital, VitalKind, VitalThreshold, VitalOp,
)
from app.api.admin import verify_admin_auth

router = APIRouter(dependencies=[Depends(verify_admin_auth)])

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class MedicationCreate(BaseModel):
    household_id: int
    member_id: int
    name: str
    dose_text: str
    times: List[str]
    owner_child_id: Optional[int] = None

    @field_validator("times")
    @classmethod
    def validate_times(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one scheduled time must be provided.")
        cleaned = []
        for t in v:
            t_str = str(t).strip()
            if not TIME_RE.match(t_str):
                raise ValueError(f"Invalid time format '{t}'. Expected 'HH:MM' (24-hour, e.g. '08:00').")
            cleaned.append(t_str)
        return cleaned


class MedicationUpdate(BaseModel):
    name: Optional[str] = None
    dose_text: Optional[str] = None
    times: Optional[List[str]] = None
    owner_child_id: Optional[int] = None
    active: Optional[bool] = None

    @field_validator("times")
    @classmethod
    def validate_times(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return None
        cleaned = []
        for t in v:
            t_str = str(t).strip()
            if not TIME_RE.match(t_str):
                raise ValueError(f"Invalid time format '{t}'. Expected 'HH:MM'.")
            cleaned.append(t_str)
        return cleaned


class ThresholdCreate(BaseModel):
    household_id: int
    member_id: int
    kind: VitalKind
    field: str  # "value_1" or "value_2"
    op: VitalOp  # "gt" or "lt"
    limit: float
    note: Optional[str] = None
    set_by_member_id: Optional[int] = None

    @field_validator("field")
    @classmethod
    def validate_field(cls, v: str) -> str:
        if v not in ("value_1", "value_2"):
            raise ValueError("Field must be 'value_1' or 'value_2'.")
        return v


class ThresholdUpdate(BaseModel):
    field: Optional[str] = None
    op: Optional[VitalOp] = None
    limit: Optional[float] = None
    note: Optional[str] = None
    active: Optional[bool] = None


class MedicationOut(BaseModel):
    id: int
    household_id: int
    member_id: int
    name: str
    dose_text: str
    times: List[str]
    owner_child_id: Optional[int]
    active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DoseLogOut(BaseModel):
    id: int
    medication_id: int
    scheduled_for: datetime
    status: str
    reminder_sent_at: Optional[datetime]
    responded_at: Optional[datetime]
    escalated_at: Optional[datetime]
    medication_name: Optional[str] = None
    dose_text: Optional[str] = None
    member_id: Optional[int] = None
    member_name: Optional[str] = None

    class Config:
        from_attributes = True


class VitalOut(BaseModel):
    id: int
    household_id: int
    member_id: int
    kind: str
    value_1: float
    value_2: Optional[float]
    unit: str
    measured_at: datetime
    artifact_id: Optional[int]
    quote: str
    created_at: datetime

    class Config:
        from_attributes = True


class ThresholdOut(BaseModel):
    id: int
    household_id: int
    member_id: int
    kind: str
    field: str
    op: str
    limit: float
    note: Optional[str]
    set_by_member_id: Optional[int]
    active: bool

    class Config:
        from_attributes = True


class HealthSummaryOut(BaseModel):
    today_doses: List[DoseLogOut]
    vitals: List[VitalOut]
    active_thresholds: List[ThresholdOut]
    active_medications: List[MedicationOut]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/{household_id}/summary", response_model=HealthSummaryOut)
async def get_health_summary(household_id: int, db: AsyncSession = Depends(get_db)):
    # 1. Active medications
    meds_res = await db.execute(
        select(Medication)
        .where(Medication.household_id == household_id, Medication.active == True)
        .order_by(Medication.name)
    )
    active_meds = meds_res.scalars().all()

    # 2. Today's doses
    from app.agent.nodes import get_current_ist_datetime
    now_ist = get_current_ist_datetime()
    start_of_today = datetime(now_ist.year, now_ist.month, now_ist.day)
    end_of_today = start_of_today + timedelta(days=1)

    doses_res = await db.execute(
        select(DoseLog)
        .join(Medication, DoseLog.medication_id == Medication.id)
        .options(selectinload(DoseLog.medication).selectinload(Medication.member))
        .where(
            Medication.household_id == household_id,
            DoseLog.scheduled_for >= start_of_today,
            DoseLog.scheduled_for < end_of_today,
        )
        .order_by(DoseLog.scheduled_for)
    )
    doses = doses_res.scalars().all()
    today_dose_outs = []
    for d in doses:
        out = DoseLogOut(
            id=d.id,
            medication_id=d.medication_id,
            scheduled_for=d.scheduled_for,
            status=d.status.value,
            reminder_sent_at=d.reminder_sent_at,
            responded_at=d.responded_at,
            escalated_at=d.escalated_at,
            medication_name=d.medication.name if d.medication else None,
            dose_text=d.medication.dose_text if d.medication else None,
            member_id=d.medication.member_id if d.medication else None,
            member_name=d.medication.member.name if d.medication and d.medication.member else None,
        )
        today_dose_outs.append(out)

    # 3. Last 14 days of vitals
    fourteen_days_ago = now_ist - timedelta(days=14)
    vitals_res = await db.execute(
        select(Vital)
        .where(Vital.household_id == household_id, Vital.measured_at >= fourteen_days_ago)
        .order_by(Vital.measured_at.desc())
    )
    vitals = vitals_res.scalars().all()

    # 4. Active thresholds
    thresh_res = await db.execute(
        select(VitalThreshold)
        .where(VitalThreshold.household_id == household_id, VitalThreshold.active == True)
        .order_by(VitalThreshold.kind)
    )
    thresholds = thresh_res.scalars().all()

    return HealthSummaryOut(
        today_doses=today_dose_outs,
        vitals=vitals,
        active_thresholds=thresholds,
        active_medications=active_meds,
    )


@router.post("/medications", response_model=MedicationOut, status_code=201)
async def create_medication(req: MedicationCreate, db: AsyncSession = Depends(get_db)):
    # Validate member
    member = await db.get(Member, req.member_id)
    if not member or member.household_id != req.household_id:
        raise HTTPException(status_code=404, detail="Member not found in this household")
    if member.role != MemberRole.parent:
        raise HTTPException(status_code=422, detail="Medication recipient member must be a parent")

    # Validate owner_child
    if req.owner_child_id is not None:
        child = await db.get(Member, req.owner_child_id)
        if not child or child.household_id != req.household_id:
            raise HTTPException(status_code=404, detail="Owner child not found in this household")

    med = Medication(
        household_id=req.household_id,
        member_id=req.member_id,
        name=req.name,
        dose_text=req.dose_text,
        times=req.times,
        owner_child_id=req.owner_child_id,
    )
    db.add(med)
    await db.commit()
    await db.refresh(med)
    return med


@router.patch("/medications/{med_id}", response_model=MedicationOut)
async def update_medication(med_id: int, req: MedicationUpdate, db: AsyncSession = Depends(get_db)):
    med = await db.get(Medication, med_id)
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")

    if req.owner_child_id is not None:
        child = await db.get(Member, req.owner_child_id)
        if not child or child.household_id != med.household_id:
            raise HTTPException(status_code=404, detail="Owner child not found in this household")
        med.owner_child_id = req.owner_child_id

    if req.name is not None:
        med.name = req.name
    if req.dose_text is not None:
        med.dose_text = req.dose_text
    if req.times is not None:
        med.times = req.times
    if req.active is not None:
        med.active = req.active

    await db.commit()
    await db.refresh(med)
    return med


@router.post("/thresholds", response_model=ThresholdOut, status_code=201)
async def create_threshold(req: ThresholdCreate, db: AsyncSession = Depends(get_db)):
    member = await db.get(Member, req.member_id)
    if not member or member.household_id != req.household_id:
        raise HTTPException(status_code=404, detail="Member not found in this household")
    if member.role != MemberRole.parent:
        raise HTTPException(status_code=422, detail="Threshold member must be a parent")

    if req.set_by_member_id is not None:
        setter = await db.get(Member, req.set_by_member_id)
        if not setter or setter.household_id != req.household_id:
            raise HTTPException(status_code=404, detail="Setter member not found in this household")

    thresh = VitalThreshold(
        household_id=req.household_id,
        member_id=req.member_id,
        kind=req.kind,
        field=req.field,
        op=req.op,
        limit=req.limit,
        note=req.note,
        set_by_member_id=req.set_by_member_id,
    )
    db.add(thresh)
    await db.commit()
    await db.refresh(thresh)
    return thresh


@router.patch("/thresholds/{thresh_id}", response_model=ThresholdOut)
async def update_threshold(thresh_id: int, req: ThresholdUpdate, db: AsyncSession = Depends(get_db)):
    thresh = await db.get(VitalThreshold, thresh_id)
    if not thresh:
        raise HTTPException(status_code=404, detail="Threshold not found")

    if req.field is not None:
        if req.field not in ("value_1", "value_2"):
            raise HTTPException(status_code=422, detail="Field must be 'value_1' or 'value_2'")
        thresh.field = req.field
    if req.op is not None:
        thresh.op = req.op
    if req.limit is not None:
        thresh.limit = req.limit
    if req.note is not None:
        thresh.note = req.note
    if req.active is not None:
        thresh.active = req.active

    await db.commit()
    await db.refresh(thresh)
    return thresh

