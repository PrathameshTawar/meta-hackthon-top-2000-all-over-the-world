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
    token = x_admin_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[-1].strip()

    # If secret is set and does not match, reject
    if settings.admin_secret:
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
async def trigger_reset(_: None = Depends(verify_admin_auth)):
    """Reset database to initial demo state."""
    await reset_db()
    return {"status": "ok", "message": "Database wiped and re-seeded with demo data."}


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
    """
    Directly feed a voice transcript or document OCR into the LangGraph agent
    to demonstrate live perception, extraction, verification, deduplication, and assignment.
    """
    async with AsyncSessionLocal() as db:
        artifact = Artifact(
            household_id=req.household_id,
            type=ArtifactType(req.type),
            file_url=req.file_url or f"demo://{req.type}_{datetime_timestamp()}",
            raw_text=req.raw_text,
        )
        db.add(artifact)
        await db.commit()
        await db.refresh(artifact)
        artifact_id = artifact.id

    await _run_agent(
        artifact_id=artifact_id,
        household_id=req.household_id,
        artifact_type=req.type,
        file_url=artifact.file_url,
        chat_id=req.chat_id or "demo_chat",
    )

    return {
        "status": "ok",
        "artifact_id": artifact_id,
        "message": "Processed through LangGraph agent successfully.",
    }


def datetime_timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")
