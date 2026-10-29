"""
Telegram webhook endpoint.
Telegram sends every message here via POST /webhook/telegram.
"""
import hashlib
import hmac
import os
import tempfile

import httpx
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from sqlalchemy import select

from app.config import settings
from app.db.models import Artifact, ArtifactType, Member
from app.db.session import AsyncSessionLocal
from app.agent.graph import compiled_graph

router = APIRouter()


async def _download_telegram_file(file_id: str) -> bytes:
    """Download a file from Telegram's servers."""
    async with httpx.AsyncClient() as client:
        # Step 1: get file path
        info = await client.get(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/getFile",
            params={"file_id": file_id},
        )
        info.raise_for_status()
        file_path = info.json()["result"]["file_path"]

        # Step 2: download
        download = await client.get(
            f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}"
        )
        download.raise_for_status()
        return download.content


async def _send_telegram_message(chat_id: str | int, text: str):
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        )


async def _run_agent(artifact_id: int, household_id: int, artifact_type: str, file_url: str, chat_id: str):
    """Run the LangGraph agent in the background."""
    initial_state = {
        "artifact_id": artifact_id,
        "household_id": household_id,
        "artifact_type": artifact_type,
        "file_url": file_url,
        "errors": [],
    }
    config = {"configurable": {"thread_id": str(artifact_id)}}

    try:
        final_state = None
        async for step in compiled_graph.astream(initial_state, config=config):
            final_state = step

        if final_state:
            # Flatten nested step dict
            state = {}
            for node_output in final_state.values():
                state.update(node_output)

            # Handle interrupt (low confidence — ask for confirmation)
            if state.get("awaiting_confirmation"):
                question = state.get("confirmation_question", "Please confirm the task details.")
                await _send_telegram_message(chat_id, f"❓ {question}")
                return

            # Send parent reply
            reply = state.get("parent_reply", "तुमचा संदेश मिळाला. आम्ही लवकरच कळवतो.")
            await _send_telegram_message(chat_id, reply)

    except Exception as exc:
        await _send_telegram_message(chat_id, f"⚠️ एक त्रुटी आली: {exc}")
        raise


@router.post("/telegram")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    # Validate secret token header
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if settings.telegram_webhook_secret and secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    body = await request.json()
    message = body.get("message") or body.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    telegram_user_id = str(message["from"]["id"])

    # Look up the sender in our members table
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Member).where(Member.telegram_id == telegram_user_id)
        )
        member = result.scalars().first()

    if member is None:
        await _send_telegram_message(
            chat_id,
            "तुम्ही अजून नोंदणीकृत नाही. कृपया तुमच्या कुटुंबातील कोणाला सांगा की तुम्हाला जोडावे.",
        )
        return {"ok": True}

    household_id = member.household_id

    # Determine artifact type
    if "voice" in message or "audio" in message:
        file_id = (message.get("voice") or message.get("audio"))["file_id"]
        artifact_type = ArtifactType.voice
    elif "photo" in message:
        # Telegram sends multiple sizes; use the largest
        file_id = message["photo"][-1]["file_id"]
        artifact_type = ArtifactType.image
    elif "document" in message:
        file_id = message["document"]["file_id"]
        artifact_type = ArtifactType.image  # treat as image for OCR
    else:
        # Plain text message — treat as chit-chat / low priority
        await _send_telegram_message(chat_id, "🙏 संदेश मिळाला!")
        return {"ok": True}

    # Store artifact reference
    async with AsyncSessionLocal() as db:
        artifact = Artifact(
            household_id=household_id,
            type=artifact_type,
            file_url=f"telegram://{file_id}",  # resolved at perceive time
        )
        db.add(artifact)
        await db.commit()
        await db.refresh(artifact)
        artifact_id = artifact.id

    # Run agent in background so we return 200 to Telegram immediately
    background_tasks.add_task(
        _run_agent,
        artifact_id=artifact_id,
        household_id=household_id,
        artifact_type=artifact_type.value,
        file_url=f"telegram://{file_id}",
        chat_id=chat_id,
    )

    return {"ok": True}
