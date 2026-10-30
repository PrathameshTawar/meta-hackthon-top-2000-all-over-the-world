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
from app.db.models import Artifact, ArtifactType, Member, MemberRole, Task, TaskStatus, Event
from app.db.session import AsyncSessionLocal
from app.agent.graph import get_compiled_graph
from langgraph.types import Command

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
        logger.info(f"[TELEGRAM SIMULATED to {chat_id}]: {text} | Markup: {reply_markup}")
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


async def _answer_callback_query(callback_query_id: str, text: str = "Received!"):
    if not settings.telegram_bot_token:
        logger.info(f"[TELEGRAM SIMULATED callback answer]: {text}")
        return
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id, "text": text},
            )
        except Exception as exc:
            logger.warning(f"Failed to answer callback query: {exc}")


async def notify_parents_task_done(task: Task, completed_by_name: str = "कुटुंबातील सदस्य"):
    """
    Sends a warm Marathi completion message to all parents in the household.
    Closes the loop so parents know their obligation is settled.
    """
    async with AsyncSessionLocal() as db:
        parents_res = await db.execute(
            select(Member).where(
                Member.household_id == task.household_id,
                Member.role == MemberRole.parent,
            )
        )
        parents = parents_res.scalars().all()
        for parent in parents:
            if parent.telegram_id:
                amt_str = f" ({task.amount})" if task.amount else ""
                msg = (
                    f"🙏 *नमस्कार! आनंदाची बातमी*\n\n"
                    f"तुमचे हे काम पूर्ण झाले आहे:\n"
                    f"📌 *{task.title}*{amt_str}\n"
                    f"पूर्ण करणारा: *{completed_by_name}*\n\n"
                    f"काळजी करू नका, सर्व वेळेवर झाले आहे! 😊"
                )
                await _send_telegram_message(parent.telegram_id, msg)


async def _notify_siblings_new_task(household_id: int, task_id: int, sibling_notification: str, sender_chat_id: str | int = ""):
    """Alerts siblings with watch-friendly action buttons (Claim, Done, View Board)."""
    async with AsyncSessionLocal() as db:
        children_res = await db.execute(
            select(Member).where(
                Member.household_id == household_id,
                Member.role == MemberRole.child,
            )
        )
        children = children_res.scalars().all()

        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "✅ Claim / मी करतो", "callback_data": f"claim:{task_id}"},
                    {"text": "✔️ Done / पूर्ण झाले", "callback_data": f"done:{task_id}"},
                ],
                [
                    {"text": "📋 View Board", "url": settings.frontend_url},
                ],
            ]
        }

        for child in children:
            if child.telegram_id and str(child.telegram_id) != str(sender_chat_id):
                await _send_telegram_message(
                    child.telegram_id,
                    sibling_notification,
                    reply_markup=reply_markup,
                )


async def _run_agent(artifact_id: int, household_id: int, artifact_type: str, file_url: str, chat_id: str):
    """Run the LangGraph agent in the background with persistent checkpointing."""
    initial_state = {
        "artifact_id": artifact_id,
        "household_id": household_id,
        "artifact_type": artifact_type,
        "file_url": file_url,
        "errors": [],
    }
    config = {"configurable": {"thread_id": str(artifact_id)}}

    try:
        graph = await get_compiled_graph()
        final_state = None
        interrupted_question = None

        async for step in graph.astream(initial_state, config=config):
            if isinstance(step, dict) and "__interrupt__" in step:
                interrupts = step["__interrupt__"]
                if interrupts and len(interrupts) > 0:
                    interrupted_question = str(interrupts[0].value)
            final_state = step

        # If interrupted: present confirmation question with interactive Correct and Wrong buttons
        if interrupted_question:
            reply_markup = {
                "inline_keyboard": [
                    [
                        {"text": "✅ Correct / होय", "callback_data": f"confirm_yes:{artifact_id}"},
                        {"text": "❌ Wrong / नाही", "callback_data": f"confirm_no:{artifact_id}"},
                    ]
                ]
            }
            await _send_telegram_message(
                chat_id,
                f"❓ *कृपया माहिती तपासा*:\n{interrupted_question}",
                reply_markup=reply_markup,
            )
            return

        if final_state:
            state = {}
            for node_output in final_state.values():
                if isinstance(node_output, dict):
                    state.update(node_output)

            # Send parent confirmation reply
            reply = state.get("parent_reply", "तुमचा संदेश मिळाला. आम्ही लवकरच कळवतो.")
            await _send_telegram_message(chat_id, reply)

            # Alert siblings with interactive buttons
            sibling_notif = state.get("sibling_notification")
            task_id = state.get("task_id")
            if sibling_notif and task_id:
                await _notify_siblings_new_task(household_id, task_id, sibling_notif, sender_chat_id=chat_id)

    except Exception as exc:
        logger.error(f"Agent execution error for artifact #{artifact_id}: {exc}", exc_info=True)
        # Protect elderly parents from raw Python exceptions; send friendly Marathi resend prompt
        friendly_msg = (
            "आम्हाला हा संदेश वाचताना अडचण आली. "
            "कृपया बिलाचा स्पष्ट फोटो किंवा व्हॉईस नोट पुन्हा पाठवा. 🙏"
        )
        await _send_telegram_message(chat_id, friendly_msg)


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

    # 1. Handle Inline Button Clicks (Claim, Done, and Confirmation)
    callback_query = body.get("callback_query")
    if callback_query:
        cb_id = callback_query.get("id")
        cb_data = callback_query.get("data", "")
        from_user = str(callback_query["from"]["id"])
        chat_id = callback_query["message"]["chat"]["id"] if "message" in callback_query else from_user

        # -------------------------------------------------------------------
        # Confirmation Buttons: confirm_yes:{artifact_id} / confirm_no:{artifact_id}
        # -------------------------------------------------------------------
        if cb_data.startswith(("confirm_yes:", "confirm:yes:")):
            try:
                artifact_id = int(cb_data.split(":")[-1])
                async with AsyncSessionLocal() as db:
                    m_res = await db.execute(select(Member).where(Member.telegram_id == from_user))
                    member = m_res.scalars().first()
                    artifact = await db.get(Artifact, artifact_id)

                    if not member or not artifact:
                        await _answer_callback_query(cb_id, "सापडले नाही. (Not found)")
                        return {"ok": False, "error": "Not found"}

                    if artifact.household_id != member.household_id:
                        logger.warning(
                            f"Household mismatch on confirmation: user {from_user} "
                            f"(household {member.household_id}) artifact {artifact_id} "
                            f"(household {artifact.household_id})"
                        )
                        await _answer_callback_query(cb_id, "⚠️ हे तुमच्या कुटुंबाचे नाही.")
                        return {"ok": False, "error": "Household mismatch"}

                # Resume agent graph with confirmation
                graph = await get_compiled_graph()
                config = {"configurable": {"thread_id": str(artifact_id)}}
                final_state = None
                async for step in graph.astream(Command(resume={"confirmed": True}), config=config):
                    final_state = step

                state = {}
                if final_state:
                    for node_output in final_state.values():
                        if isinstance(node_output, dict):
                            state.update(node_output)

                await _answer_callback_query(cb_id, "✅ माहितीची पुष्टी झाली!")
                await _send_telegram_message(
                    chat_id,
                    "✅ *माहितीची पुष्टी झाली*: माहिती बरोबर असल्याचे नोंदवले आहे आणि काम कुटुंब बोर्डवर जोडले आहे. 🙏"
                )

                if state.get("sibling_notification") and state.get("task_id"):
                    await _notify_siblings_new_task(
                        member.household_id,
                        state["task_id"],
                        state["sibling_notification"],
                        sender_chat_id=chat_id,
                    )
                return {"ok": True, "action": "confirmed_yes"}
            except Exception as exc:
                logger.error(f"Error resuming agent with confirmed=True: {exc}", exc_info=True)
                await _answer_callback_query(cb_id, "त्रुटी आली.")
                return {"ok": False, "error": str(exc)}

        elif cb_data.startswith(("confirm_no:", "confirm:no:")):
            try:
                artifact_id = int(cb_data.split(":")[-1])
                async with AsyncSessionLocal() as db:
                    m_res = await db.execute(select(Member).where(Member.telegram_id == from_user))
                    member = m_res.scalars().first()
                    artifact = await db.get(Artifact, artifact_id)

                    if not member or not artifact:
                        await _answer_callback_query(cb_id, "सापडले नाही. (Not found)")
                        return {"ok": False, "error": "Not found"}

                    if artifact.household_id != member.household_id:
                        await _answer_callback_query(cb_id, "⚠️ हे तुमच्या कुटुंबाचे नाही.")
                        return {"ok": False, "error": "Household mismatch"}

                # Resume agent graph with cancellation
                graph = await get_compiled_graph()
                config = {"configurable": {"thread_id": str(artifact_id)}}
                async for step in graph.astream(Command(resume={"confirmed": False}), config=config):
                    pass

                await _answer_callback_query(cb_id, "माहिती रद्द केली.")
                await _send_telegram_message(
                    chat_id,
                    "❌ ठीक आहे, आम्ही हे काम रद्द केले आहे. कृपया पुन्हा स्पष्ट फोटो किंवा व्हॉईस नोट पाठवा. 🙏"
                )
                return {"ok": True, "action": "confirmed_no"}
            except Exception as exc:
                logger.error(f"Error resuming agent with confirmed=False: {exc}", exc_info=True)
                await _answer_callback_query(cb_id, "त्रुटी आली.")
                return {"ok": False, "error": str(exc)}

        # -------------------------------------------------------------------
        # Claim Button: claim:{task_id} or claim_{task_id}
        # -------------------------------------------------------------------
        elif cb_data.startswith(("claim:", "claim_")):
            try:
                task_id = int(cb_data.replace("claim:", "").replace("claim_", ""))
                async with AsyncSessionLocal() as db:
                    res = await db.execute(select(Member).where(Member.telegram_id == from_user))
                    member = res.scalars().first()
                    task = await db.get(Task, task_id)

                    if not member:
                        await _answer_callback_query(cb_id, "नोंदणी सापडली नाही.")
                        return {"ok": False, "error": "Member not registered"}

                    if not task:
                        await _answer_callback_query(cb_id, "काम सापडले नाही.")
                        return {"ok": False, "error": "Task not found"}

                    # Enforce household isolation
                    if task.household_id != member.household_id:
                        logger.warning(
                            f"Security mismatch: member {member.name} (household {member.household_id}) "
                            f"attempted to claim task #{task_id} (household {task.household_id})"
                        )
                        await _answer_callback_query(cb_id, "⚠️ हे काम तुमच्या कुटुंबाचे नाही.")
                        return {"ok": False, "error": "Household mismatch"}

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

                    done_markup = {
                        "inline_keyboard": [
                            [
                                {"text": "✔️ Mark Done / काम पूर्ण झाले", "callback_data": f"done:{task.id}"},
                                {"text": "📋 View Board", "url": settings.frontend_url},
                            ]
                        ]
                    }

                    await _answer_callback_query(cb_id, f"✅ Task claimed by {member.name}!")
                    await _send_telegram_message(
                        chat_id,
                        f"✅ *Task Claimed*: '{task.title}' has been claimed by {member.name}.\n"
                        f"The Saath family board is updated.\n"
                        f"When completed, tap below to notify your family:",
                        reply_markup=done_markup,
                    )
                    return {"ok": True, "action": "claimed"}
            except Exception as exc:
                logger.error(f"Error handling claim callback: {exc}", exc_info=True)
                await _answer_callback_query(cb_id, "Error claiming task")
                return {"ok": False, "error": str(exc)}

        # -------------------------------------------------------------------
        # Done Button: done:{task_id} or done_{task_id}
        # -------------------------------------------------------------------
        elif cb_data.startswith(("done:", "done_")):
            try:
                task_id = int(cb_data.replace("done:", "").replace("done_", ""))
                async with AsyncSessionLocal() as db:
                    res = await db.execute(select(Member).where(Member.telegram_id == from_user))
                    member = res.scalars().first()
                    task = await db.get(Task, task_id)

                    if not member:
                        await _answer_callback_query(cb_id, "नोंदणी सापडली नाही.")
                        return {"ok": False, "error": "Member not registered"}

                    if not task:
                        await _answer_callback_query(cb_id, "काम सापडले नाही.")
                        return {"ok": False, "error": "Task not found"}

                    # Enforce household isolation
                    if task.household_id != member.household_id:
                        logger.warning(
                            f"Security mismatch: member {member.name} (household {member.household_id}) "
                            f"attempted to complete task #{task_id} (household {task.household_id})"
                        )
                        await _answer_callback_query(cb_id, "⚠️ हे काम तुमच्या कुटुंबाचे नाही.")
                        return {"ok": False, "error": "Household mismatch"}

                    task.status = TaskStatus.done
                    task.updated_at = datetime.utcnow()

                    db.add(Event(
                        household_id=task.household_id,
                        task_id=task.id,
                        actor=f"member:{member.name}",
                        action="completed",
                        reason=f"Marked completed via Telegram button by {member.name}",
                        payload={"member_id": member.id, "telegram_id": from_user},
                    ))
                    await db.commit()

                    await _answer_callback_query(cb_id, "✔️ Task marked as completed!")
                    await _send_telegram_message(
                        chat_id,
                        f"✔️ *काम पूर्ण झाले*: '{task.title}' काम पूर्ण झाल्याचे नोंदवले आहे. "
                        f"तुमच्या पालकांना लगेच कळवले आहे. 🙏",
                    )

                    # Close the loop: notify all parents in the household
                    await notify_parents_task_done(task, completed_by_name=member.name)
                    return {"ok": True, "action": "done"}
            except Exception as exc:
                logger.error(f"Error handling done callback: {exc}", exc_info=True)
                await _answer_callback_query(cb_id, "Error marking done")
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
                        Task.status.in_([TaskStatus.new, TaskStatus.confirmed, TaskStatus.claimed, TaskStatus.escalated, TaskStatus.needs_review]),
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
