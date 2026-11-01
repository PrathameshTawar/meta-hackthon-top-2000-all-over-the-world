from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Depends, Header
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime

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

    if token != settings.admin_secret:
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
    await reset_db()
    await seed_data()
    return {"status": "ok", "message": "Database reset and re-seeded with demo data."}


@router.post("/seed")
async def trigger_seed(_: None = Depends(verify_admin_auth)):
    """Seed demo data if not already present."""
    await seed_data()
    return {"status": "ok", "message": "Demo data checked/seeded."}


@router.post("/ingest/simulate")
async def simulate_ingest(
    req: SimulateIngestRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(verify_admin_auth),
):
    """Simulate an incoming artifact (voice or image) hitting the agent."""
    if req.type == "voice":
        art_type = ArtifactType.voice
    elif req.type == "image":
        art_type = ArtifactType.image
    else:
        art_type = ArtifactType.text

    async with AsyncSessionLocal() as db:
        artifact = Artifact(
            household_id=req.household_id,
            source="simulate",
            type=art_type,
            file_url=req.file_url,
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
        chat_id=req.chat_id,
    )

    return {
        "status": "ok",
        "message": "Artifact created and agent execution queued in background.",
        "artifact_id": art_id,
    }
