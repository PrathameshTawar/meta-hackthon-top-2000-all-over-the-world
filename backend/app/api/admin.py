import hmac
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Depends, Header
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime, timedelta

from app.config import settings
from app.scheduler.escalation import run_escalation
from app.db.reset import reset_db
from app.db.seed import seed_data
from app.db.models import Artifact, ArtifactType
from app.db.session import AsyncSessionLocal
from app.api.webhooks import _run_agent

router = APIRouter()


async def verify_admin_auth(
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
    authorization: Optional[str] = Header(None),
):
    """Secure admin endpoints against unauthorized resets or wipes during judging."""
    if not settings.admin_secret:
        raise HTTPException(
            status_code=503,
            detail="ADMIN_SECRET not configured",
        )

    token = x_admin_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[-1].strip()

    if not token or not hmac.compare_digest(token, settings.admin_secret):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Valid X-Admin-Token or Bearer token required for admin endpoints.",
        )


class SimulateEscalationRequest(BaseModel):
    days_ahead: int = 3


class SimulateIngestRequest(BaseModel):
    household_id: int = 1
    type: str = "voice"  # "voice" | "image"
    raw_text: str
    file_url: Optional[str] = None
    chat_id: Optional[str] = "demo_chat"


class DoseNowRequest(BaseModel):
    medication_id: int


class SkipHealthRequest(BaseModel):
    minutes: int = 120


@router.post("/escalate/simulate")
async def simulate_escalation(
    req: SimulateEscalationRequest = SimulateEscalationRequest(),
    _: None = Depends(verify_admin_auth),
):
    """Simulate advancing the clock by N days to trigger escalation on camera."""
    escalated_ids = await run_escalation(simulated_days_ahead=req.days_ahead)
    return {
        "status": "ok",
        "days_advanced": req.days_ahead,
        "escalated_task_ids": escalated_ids,
        "count": len(escalated_ids),
    }


@router.post("/reset")
@router.post("/reset-db")
async def admin_reset_db(
    request: Request = None,
    _: None = Depends(verify_admin_auth),
):
    """Wipe database and re-seed with demo household (Bhosale family)."""
    if settings.environment == "production":
        raise HTTPException(
            status_code=403,
            detail="Destructive reset endpoints are disabled in production.",
        )
    await reset_db()
    await seed_data()
    return {"status": "ok", "message": "Database reset and re-seeded with demo data."}


@router.post("/seed")
async def trigger_seed(_: None = Depends(verify_admin_auth)):
    """Seed demo data if not already present."""
    if settings.environment == "production":
        raise HTTPException(
            status_code=403,
            detail="Destructive seed endpoints are disabled in production.",
        )
    await seed_data()
    return {"status": "ok", "message": "Demo data checked/seeded."}


@router.post("/ingest/simulate")
async def simulate_ingest(
    req: SimulateIngestRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(verify_admin_auth),
):
    """Simulate an incoming artifact (voice or image) hitting the agent."""
    # Anything that isn't voice is treated as already-OCR'd document text.
    art_type = ArtifactType.voice if req.type == "voice" else ArtifactType.image
    file_url = req.file_url or "simulate://text"

    async with AsyncSessionLocal() as db:
        artifact = Artifact(
            household_id=req.household_id,
            type=art_type,
            file_url=file_url,
            raw_text=req.raw_text,
        )
        db.add(artifact)
        await db.commit()
        await db.refresh(artifact)
        art_id = artifact.id

    background_tasks.add_task(
        _run_agent,
        artifact_id=art_id,
        household_id=req.household_id,
        artifact_type=art_type.value,
        file_url=file_url,
        chat_id=req.chat_id,
    )

    return {
        "status": "ok",
        "message": "Artifact created and agent execution queued in background.",
        "artifact_id": art_id,
    }


@router.post("/health/dose-now")
async def admin_health_dose_now(
    req: DoseNowRequest,
    _: None = Depends(verify_admin_auth),
):
    from app.services.health import send_due_reminders
    from app.agent.nodes import get_current_ist_datetime
    from app.db.models import DoseLog, DoseStatus, Medication
    now = get_current_ist_datetime()
    async with AsyncSessionLocal() as db:
        med = await db.get(Medication, req.medication_id)
        if not med:
            raise HTTPException(status_code=404, detail="Medication not found")
        dose = DoseLog(
            medication_id=req.medication_id,
            scheduled_for=now,
            status=DoseStatus.pending,
        )
        db.add(dose)
        await db.commit()
    sent = await send_due_reminders(now=now)
    return {"status": "ok", "reminder_sent": sent > 0}


@router.post("/health/skip")
async def admin_health_skip(
    req: SkipHealthRequest = SkipHealthRequest(),
    _: None = Depends(verify_admin_auth),
):
    from app.services.health import escalate_missed_doses
    from app.agent.nodes import get_current_ist_datetime
    now = get_current_ist_datetime() + timedelta(minutes=req.minutes)
    escalated = await escalate_missed_doses(now=now)
    return {"status": "ok", "escalated_doses_count": escalated}
