"""
Telegram webhook endpoint.
Telegram sends every message and button tap here via POST /webhook/telegram.
"""
import hashlib
import hmac
import os
import tempfile
import logging
from collections import deque
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from sqlalchemy import select

from app.config import settings
from app.db.models import Artifact, ArtifactType, Member, Task, TaskStatus, Event
from app.db.session import AsyncSessionLocal
from app.agent.graph import compiled_graph

logger = logging.getLogger(__name__)
router = APIRouter()

# Keep track of last 1000 update IDs to prevent Telegram network retry duplication
_processed_updates = deque(maxlen=1000)


async def _download_telegram_file(file_id: str) -> bytes:
    """Download a file from Telegram's servers."""
    if not settings.telegram_bot_token:
        return b""
    async with httpx.AsyncClient(timeout=30) as client:
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


async def _send_telegram_message(chat_id: str | int, text: str, reply_markup: Optional[dict] = None):
    if not settings.telegram_bot_token:
        logger.info(f"[TELEGRAM SIMULATED to {chat_id}]: {text}")
        return
    async with httpx.AsyncClient(timeout=10) as client:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json=payload,
            )
        except Exception as exc:
            logger.warning(f"Failed to send Telegram message to {chat_id}: {exc}")


async def _answer_callback_query(callback_query_id: str, text: str = "Claimed!"):
    if not settings.telegram_bot_token:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id, "text": text},
            )
        except Exception as exc:
            logger.warning(f"Failed to answer callback query: {exc}")


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
            state = {}
            for node_output in final_state.values():
                if isinstance(node_output, dict):
                    state.update(node_output)

            # Handle interrupt (low confidence — ask for confirmation)
            if state.get("awaiting_confirmation"):
                question = state.get("confirmation_question", "कृपया पुष्टी करा.")
                await _send_telegram_message(chat_id, f"❓ {question}")
                return

            # Send parent reply
            reply = state.get("parent_reply", "तुमचा संदेश मिळाला. आम्ही लवकरच कळवतो.")
            await _send_telegram_message(chat_id, reply)

    except Exception as exc:
        logger.error(f"Agent execution error for artifact #{artifact_id}: {exc}")
        await _send_telegram_message(chat_id, f"⚠️ एक त्रुटी आली: {exc}")


@router.post("/telegram")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    # Validate secret token header if set
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if settings.telegram_webhook_secret and secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    body = await request.json()

    # Deduplicate updates from Telegram network retries
    update_id = body.get("update_id")
    if update_id:
        if update_id in _processed_updates:
            return {"ok": True, "duplicate": True}
        _processed_updates.append(update_id)

    # 1. Handle Inline Button Clicks (e.g. [✅ Claim Task])
    callback_query = body.get("callback_query")
    if callback_query:
        cb_id = callback_query.get("id")
        cb_data = callback_query.get("data", "")
        from_user = str(callback_query["from"]["id"])
        chat_id = callback_query["message"]["chat"]["id"] if "message" in callback_query else from_user

        if cb_data.startswith("claim:"):
            try:
                task_id = int(cb_data.split(":")[1])
                async with AsyncSessionLocal() as db:
                    # Find member
                    res = await db.execute(select(Member).where(Member.telegram_id == from_user))
                    member = res.scalars().first()
                    task = await db.get(Task, task_id)

                    if task and member:
                        task.status = TaskStatus.claimed
                        task.assignee_id = member.id
                        task.updated_at = datetime.utcnow()

                        db.add(Event(
                            household_id=task.household_id,
                            task_id=task.id,
                            actor=f"member:{member.name}",
                            action="claimed",
                            reason=f"Claimed via Telegram button by {member.name}",
                            payload={"member_id": member.id, "telegram_id": from_user},
                        ))
                        await db.commit()

                        await _answer_callback_query(cb_id, f"✅ Task claimed by {member.name}!")
                        await _send_telegram_message(
                            chat_id,
                            f"✅ *Task Claimed*: '{task.title}' has been claimed by {member.name}.\n"
                            f"The Saath family board is updated.",
                        )
                        return {"ok": True, "action": "claimed"}
            except Exception as exc:
                logger.error(f"Error handling claim callback: {exc}")
                await _answer_callback_query(cb_id, "Error claiming task")
                return {"ok": False, "error": str(exc)}

    # 2. Handle Messages
    message = body.get("message") or body.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    telegram_user_id = str(message["from"]["id"])

    # Look up sender in members table
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

    # Handle text messages (e.g., status inquiries or text forwards)
    text_content = message.get("text", "").strip()
    if text_content and not any(k in message for k in ["photo", "voice", "audio", "document"]):
        low = text_content.lower()
        # Voice or typed status question: "काय बाकी आहे?" / "what is pending?"
        if any(q in low for q in ["काय बाकी आहे", "काय बाकी", "pending", "status", "बाकी"]):
            async with AsyncSessionLocal() as db:
                tasks_res = await db.execute(
                    select(Task).where(
                        Task.household_id == household_id,
                        Task.status.in_([TaskStatus.new, TaskStatus.assigned, TaskStatus.claimed, TaskStatus.escalated, TaskStatus.needs_review]),
                    ).order_by(Task.due_date.asc())
                )
                pending_tasks = tasks_res.scalars().all()

            if not pending_tasks:
                reply = "सध्या कोणतीही बिले किंवा कामे बाकी नाहीत! सर्व कामे पूर्ण झाली आहेत. 🙏"
            else:
                lines = ["📋 *सध्या बाकी असलेली कामे*:"]
                for i, t in enumerate(pending_tasks[:5], 1):
                    amt = f" ({t.amount})" if t.amount else ""
                    due = f" - देय: {t.due_date.strftime('%d %b')}" if t.due_date else ""
                    lines.append(f"{i}. *{t.title}*{amt}{due}")
                reply = "\n".join(lines)

            await _send_telegram_message(chat_id, reply)
            return {"ok": True}

        # Otherwise treat text as forward / document note
        async with AsyncSessionLocal() as db:
            artifact = Artifact(
                household_id=household_id,
                type=ArtifactType.image,
                file_url="text://message",
                raw_text=text_content,
            )
            db.add(artifact)
            await db.commit()
            await db.refresh(artifact)
            artifact_id = artifact.id

        background_tasks.add_task(
            _run_agent,
            artifact_id=artifact_id,
            household_id=household_id,
            artifact_type="image",
            file_url="text://message",
            chat_id=chat_id,
        )
        return {"ok": True}

    # Handle media: voice, photo, document
    if "voice" in message or "audio" in message:
        file_id = (message.get("voice") or message.get("audio"))["file_id"]
        artifact_type = ArtifactType.voice
    elif "photo" in message:
        file_id = message["photo"][-1]["file_id"]
        artifact_type = ArtifactType.image
    elif "document" in message:
        doc = message["document"]
        mime = doc.get("mime_type", "")
        # Only accept image files for OCR
        if not mime.startswith("image/"):
            await _send_telegram_message(
                chat_id,
                "कृपया बिलाचा स्पष्ट फोटो (JPEG/PNG) किंवा व्हॉईस नोट पाठवा. PDF सध्या समर्थित नाही.",
            )
            return {"ok": True}
        file_id = doc["file_id"]
        artifact_type = ArtifactType.image
    else:
        await _send_telegram_message(chat_id, "🙏 संदेश मिळाला!")
        return {"ok": True}

    # Store artifact
    async with AsyncSessionLocal() as db:
        artifact = Artifact(
            household_id=household_id,
            type=artifact_type,
            file_url=f"telegram://{file_id}",
        )
        db.add(artifact)
        await db.commit()
        await db.refresh(artifact)
        artifact_id = artifact.id

    background_tasks.add_task(
        _run_agent,
        artifact_id=artifact_id,
        household_id=household_id,
        artifact_type=artifact_type.value,
        file_url=f"telegram://{file_id}",
        chat_id=chat_id,
    )
    return {"ok": True}
