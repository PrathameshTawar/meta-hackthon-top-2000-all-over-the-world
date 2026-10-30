"""
Telegram & WhatsApp Webhook endpoints.
Supports:
1. Telegram bot webhooks: POST /webhook/telegram
2. WhatsApp Cloud API webhooks: GET & POST /chat/webhook or /webhook/whatsapp
"""
import hashlib
import hmac
import json
import os
import re
import tempfile
import logging
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from starlette.responses import PlainTextResponse
from sqlalchemy import select

from app.config import settings
from app.db.models import (
    Artifact,
    ArtifactType,
    Member,
    MemberRole,
    Task,
    TaskStatus,
    Event,
    ProcessedMessage,
)
from app.db.session import AsyncSessionLocal
from app.agent.graph import get_compiled_graph
from langgraph.types import Command

logger = logging.getLogger(__name__)

telegram_router = APIRouter(prefix="/webhook", tags=["telegram"])
whatsapp_router = APIRouter(prefix="/chat", tags=["whatsapp"])
router = telegram_router  # Fallback backward compatibility

# Template language mapping:
# - saath_new_task, saath_task_escalation, and saath_please_check are sent to siblings (English en_US)
# - saath_task_done is sent to parents (Marathi mr)
TEMPLATE_LANGUAGES = {
    "saath_new_task": "en_US",
    "saath_task_escalation": "en_US",
    "saath_task_done": "mr",
    "saath_please_check": "en_US",
}


def _clean_template_param(val: any) -> str:
    """WhatsApp Cloud API rejects template parameter values containing line breaks."""
    s = str(val) if val is not None else ""
    return re.sub(r"[\r\n]+", " ", s).strip()


# Keep track of last 1000 Telegram update IDs to prevent network retry duplication
_processed_updates = deque(maxlen=1000)
# Fast in-memory L1 cache for WhatsApp message IDs (backed by ProcessedMessage table)
_processed_wa_messages = deque(maxlen=2000)


async def _download_telegram_file(file_id: str) -> bytes:
    """Download a file from Telegram's servers."""
    if not settings.telegram_bot_token:
        return b""
    async with httpx.AsyncClient(timeout=30) as client:
        info = await client.get(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/getFile",
            params={"file_id": file_id},
        )
        info.raise_for_status()
        file_path = info.json()["result"]["file_path"]

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


async def _send_whatsapp_message(
    to_phone: str,
    text: str,
    buttons: Optional[list] = None,
    template_name: Optional[str] = None,
    template_params: Optional[list] = None,
    template_button_payload: Optional[str] = None,
    template_button_payloads: Optional[list[str]] = None,
    template_language: Optional[str] = None,
    last_inbound_at: Optional[datetime] = None,
) -> bool:
    """
    Send text, interactive buttons, or approved template via Meta's WhatsApp Cloud API.
    Enforces WhatsApp's 24-hour customer service window:
    - If last_inbound_at > 24 hours, sends an approved template directly.
    - Inspects HTTP status and logs any Meta Graph API errors (e.g. error 131047).
    - Falls back to template retry on error 131047.
    - Strips line breaks from all template parameters (WhatsApp Cloud API rejects parameters containing \r or \n).
    - Maps template names to approved language codes (e.g. en_US for sibling templates, mr for parent templates).
    - Attaches quick-reply button payloads (e.g. claim:<task_id> or confirm_yes / confirm_no) when provided.
    """
    if not settings.whatsapp_token or not settings.whatsapp_phone_number_id:
        logger.info(f"[WHATSAPP SIMULATED to {to_phone}]: {text} | Buttons: {buttons} | Template: {template_name}")
        return True

    clean_phone = to_phone.replace("+", "").replace("-", "").strip()
    api_ver = settings.whatsapp_api_version or "v22.0"
    url = f"https://graph.facebook.com/{api_ver}/{settings.whatsapp_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_token}",
        "Content-Type": "application/json",
    }

    # Check 24-hour customer service window
    now_utc = datetime.utcnow()
    is_outside_24h = False
    if last_inbound_at is not None:
        last_inbound_naive = last_inbound_at.replace(tzinfo=None)
        if (now_utc - last_inbound_naive) > timedelta(hours=24):
            is_outside_24h = True

    btn_payloads = []
    if template_button_payloads:
        btn_payloads = list(template_button_payloads)
    elif template_button_payload:
        btn_payloads = [template_button_payload]

    def _build_template_payload(t_name: str, t_params: Optional[list], t_btn_payloads: list[str], t_lang: Optional[str]) -> dict:
        lang_code = t_lang or TEMPLATE_LANGUAGES.get(t_name, "mr")
        cleaned_params = [_clean_template_param(p) for p in (t_params or [text[:60]])]
        components = [
            {
                "type": "body",
                "parameters": [{"type": "text", "text": p} for p in cleaned_params],
            }
        ]
        for idx, payload in enumerate(t_btn_payloads[:3]):
            components.append({
                "type": "button",
                "sub_type": "quick_reply",
                "index": str(idx),
                "parameters": [{"type": "payload", "payload": payload}],
            })
        return {
            "messaging_product": "whatsapp",
            "to": clean_phone,
            "type": "template",
            "template": {
                "name": t_name,
                "language": {"code": lang_code},
                "components": components,
            },
        }

    # If outside 24h window and template is provided, send template directly
    if is_outside_24h and template_name:
        template_payload = _build_template_payload(template_name, template_params, btn_payloads, template_language)
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.post(url, json=template_payload, headers=headers)
                if resp.status_code >= 400:
                    logger.error(f"WhatsApp template '{template_name}' to {to_phone} failed: {resp.status_code} - {resp.text}")
                    return False
                return True
            except Exception as exc:
                logger.error(f"Failed to post WhatsApp template to {to_phone}: {exc}")
                return False

    if buttons:
        payload = {
            "messaging_product": "whatsapp",
            "to": clean_phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": text},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                        for b in buttons[:3]
                    ]
                },
            },
        }
    else:
        payload = {
            "messaging_product": "whatsapp",
            "to": clean_phone,
            "type": "text",
            "text": {"body": text},
        }

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                err_body = resp.text
                logger.error(f"WhatsApp send to {to_phone} returned status {resp.status_code}: {err_body}")
                # Fallback retry if 131047 (outside 24h window) and template is specified
                if "131047" in err_body and template_name:
                    logger.info(f"Retrying outside 24h window with template '{template_name}' for {to_phone}")
                    retry_payload = _build_template_payload(template_name, template_params, btn_payloads, template_language)
                    retry_resp = await client.post(url, json=retry_payload, headers=headers)
                    if retry_resp.status_code != 200:
                        logger.error(f"WhatsApp template fallback also failed: {retry_resp.text}")
                        return False
                    return True
                return False
            return True
        except Exception as exc:
            logger.error(f"Failed to send WhatsApp message to {to_phone}: {exc}")
            return False


async def notify(
    member: Member,
    text: str,
    buttons: Optional[list] = None,
    template_name: Optional[str] = None,
    template_params: Optional[list] = None,
    template_button_payload: Optional[str] = None,
    template_button_payloads: Optional[list[str]] = None,
    template_language: Optional[str] = None,
    reply_markup: Optional[dict] = None,
) -> bool:
    """
    Unified notification dispatch function from Step 6 of the Build Guide.
    Sends alerts to a member across Telegram and/or WhatsApp.
    Respects WhatsApp's 24-hour customer service window based on member.last_inbound_at.
    If outside 24h, sends an approved Meta template (saath_new_task, saath_task_escalation, saath_task_done, saath_please_check).
    """
    success = True
    if member.telegram_id:
        await _send_telegram_message(member.telegram_id, text, reply_markup=reply_markup)
    if member.phone:
        ok = await _send_whatsapp_message(
            to_phone=member.phone,
            text=text,
            buttons=buttons,
            template_name=template_name,
            template_params=template_params,
            template_button_payload=template_button_payload,
            template_button_payloads=template_button_payloads,
            template_language=template_language,
            last_inbound_at=member.last_inbound_at,
        )
        if not ok:
            success = False
    return success


async def notify_parents_task_done(task: Task, completed_by_name: str = "कुटुंबातील सदस्य"):
    """
    Sends a warm Marathi completion message to all parents in the household.
    Closes the loop across both Telegram and WhatsApp so parents know their obligation is settled.
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
            amt_str = f" ({task.amount})" if task.amount else ""
            msg = (
                f"🙏 *नमस्कार! आनंदाची बातमी*\n\n"
                f"तुमचे हे काम पूर्ण झाले आहे:\n"
                f"📌 *{task.title}*{amt_str}\n"
                f"पूर्ण करणारा: *{completed_by_name}*\n\n"
                f"काळजी करू नका, सर्व वेळेवर झाले आहे! 😊"
            )
            await notify(
                member=parent,
                text=msg,
                template_name="saath_task_done",
                template_params=[_clean_template_param(task.title), _clean_template_param(completed_by_name)],
                template_language="mr",
            )


async def _notify_siblings_new_task(household_id: int, task_id: int, sibling_notification: str, sender_chat_id: str | int = ""):
    """Alerts siblings on Telegram and WhatsApp with watch-friendly action buttons."""
    async with AsyncSessionLocal() as db:
        children_res = await db.execute(
            select(Member).where(
                Member.household_id == household_id,
                Member.role == MemberRole.child,
            )
        )
        children = children_res.scalars().all()

        tg_reply_markup = {
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

        wa_buttons = [
            {"id": f"claim:{task_id}", "title": "Claim Task"},
            {"id": f"done:{task_id}", "title": "Mark Done"},
        ]

        for child in children:
            if str(child.telegram_id) != str(sender_chat_id) and str(child.phone) != str(sender_chat_id):
                await notify(
                    member=child,
                    text=sibling_notification,
                    buttons=wa_buttons,
                    template_name="saath_new_task",
                    template_params=[_clean_template_param(sibling_notification[:60]), "Claim on board"],
                    template_button_payload=f"claim:{task_id}",
                    template_language="en_US",
                    reply_markup=tg_reply_markup,
                )


async def _run_agent(artifact_id: int, household_id: int, artifact_type: str, file_url: str, chat_id: str, channel: str = "telegram"):
    """Run the LangGraph agent in the background with persistent SQLite checkpointing."""
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

        # If interrupted: route confirmation question to the category-owner sibling, not the elderly parent
        if interrupted_question:
            async with AsyncSessionLocal() as db:
                children_res = await db.execute(
                    select(Member).where(
                        Member.household_id == household_id,
                        Member.role == MemberRole.child,
                    )
                )
                children = children_res.scalars().all()

                # Identify sender member
                sender_member = None
                if channel == "telegram":
                    s_res = await db.execute(select(Member).where(Member.telegram_id == str(chat_id)))
                    sender_member = s_res.scalars().first()
                else:
                    s_res = await db.execute(
                        select(Member).where(
                            (Member.phone == chat_id) | (Member.phone == f"+{chat_id}")
                        )
                    )
                    sender_member = s_res.scalars().first()

            # Determine category from state if present
            extracted_cat = None
            if final_state:
                for node_out in final_state.values():
                    if isinstance(node_out, dict) and "category" in node_out:
                        extracted_cat = node_out["category"]

            # Select sibling: match categories_owned, otherwise first child
            target_sibling = None
            if children:
                for c in children:
                    if extracted_cat and c.categories_owned and extracted_cat in c.categories_owned:
                        target_sibling = c
                        break
                if not target_sibling:
                    target_sibling = children[0]

            # If sender was an elderly parent, send a warm reassuring message so they aren't confused
            if sender_member and sender_member.role == MemberRole.parent:
                parent_reassurance = (
                    "🙏 तुमचे बिल/माहिती मिळाली आहे. कुटुंबातील मुले याची खात्री करून काम पूर्ण करत आहेत, "
                    "काळजी करू नका! 😊"
                )
                if channel == "telegram":
                    await _send_telegram_message(chat_id, parent_reassurance)
                else:
                    await _send_whatsapp_message(chat_id, parent_reassurance)

            # Route confirmation buttons to target sibling
            confirm_text = (
                f"❓ *Please verify extracted details for family board*:\n{interrupted_question}"
            )
            tg_reply_markup = {
                "inline_keyboard": [
                    [
                        {"text": "✅ Correct / बरोबर", "callback_data": f"confirm_yes:{artifact_id}"},
                        {"text": "❌ Wrong / चूक", "callback_data": f"confirm_no:{artifact_id}"},
                    ],
                    [
                        {"text": "📋 View Board", "url": settings.frontend_url},
                    ],
                ]
            }
            wa_buttons = [
                {"id": f"confirm_yes:{artifact_id}", "title": "Correct (बरोबर)"},
                {"id": f"confirm_no:{artifact_id}", "title": "Wrong (चूक)"},
            ]

            if target_sibling:
                await notify(
                    member=target_sibling,
                    text=confirm_text,
                    buttons=wa_buttons,
                    template_name="saath_please_check",
                    template_params=[_clean_template_param(interrupted_question[:60])],
                    template_button_payloads=[f"confirm_yes:{artifact_id}", f"confirm_no:{artifact_id}"],
                    template_language="en_US",
                    reply_markup=tg_reply_markup,
                )
            else:
                # Fallback to sender if no sibling registered in household
                if channel == "telegram":
                    await _send_telegram_message(chat_id, confirm_text, reply_markup=tg_reply_markup)
                else:
                    await _send_whatsapp_message(
                        chat_id,
                        confirm_text,
                        buttons=wa_buttons,
                        template_name="saath_please_check",
                        template_params=[_clean_template_param(interrupted_question[:60])],
                        template_button_payloads=[f"confirm_yes:{artifact_id}", f"confirm_no:{artifact_id}"],
                        template_language="en_US",
                    )
            return

        if final_state:
            state = {}
            for node_output in final_state.values():
                if isinstance(node_output, dict):
                    state.update(node_output)

            # Send parent confirmation reply
            reply = state.get("parent_reply", "तुमचा संदेश मिळाला. आम्ही लवकरच कळवतो.")
            if channel == "telegram":
                await _send_telegram_message(chat_id, reply)
            else:
                await _send_whatsapp_message(chat_id, reply)

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
        if channel == "telegram":
            await _send_telegram_message(chat_id, friendly_msg)
        else:
            await _send_whatsapp_message(chat_id, friendly_msg)


# ===========================================================================
# 1. Telegram Webhook Endpoint
# ===========================================================================

@telegram_router.post("/telegram")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
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

        # Confirmation: confirm_yes:{artifact_id}
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
                        await _answer_callback_query(cb_id, "⚠️ हे तुमच्या कुटुंबाचे नाही.")
                        return {"ok": False, "error": "Household mismatch"}

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

        # Confirmation: confirm_no:{artifact_id}
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

        # Claim Button: claim:{task_id}
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

                    if task.household_id != member.household_id:
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

        # Done Button: done:{task_id}
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

                    if task.household_id != member.household_id:
                        await _answer_callback_query(cb_id, "⚠️ हे काम तुमच्या कुटुंबाचे नाही.")
                        return {"ok": False, "error": "Household mismatch"}

                    task.status = TaskStatus.done
                    task.updated_at = datetime.utcnow()

                    # Handle monthly recurrence
                    if task.recurrence == "monthly" and task.due_date:
                        from datetime import timedelta
                        next_due = task.due_date + timedelta(days=30)
                        next_task = Task(
                            household_id=task.household_id,
                            category=task.category,
                            title=task.title,
                            amount=task.amount,
                            due_date=next_due,
                            payee=task.payee,
                            status=TaskStatus.confirmed,
                            assignee_id=task.assignee_id,
                            recurrence="monthly",
                        )
                        db.add(next_task)

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

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Member).where(Member.telegram_id == telegram_user_id)
        )
        member = result.scalars().first()
        if member:
            member.last_inbound_at = datetime.utcnow()
            await db.commit()

    if member is None:
        await _send_telegram_message(
            chat_id,
            "तुम्ही अजून नोंदणीकृत नाही. कृपया तुमच्या कुटुंबातील कोणाला सांगा की तुम्हाला जोडावे.",
        )
        return {"ok": True}

    household_id = member.household_id

    # Handle text messages (e.g. "काय बाकी आहे?" / status inquiries)
    text_content = message.get("text", "").strip()
    if text_content and not any(k in message for k in ["photo", "voice", "audio", "document"]):
        if await _is_status_query(text_content):
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

        # Otherwise store text artifact
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
            channel="telegram",
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
        channel="telegram",
    )
    return {"ok": True}


# ===========================================================================
# 2. WhatsApp Cloud API Webhook Endpoints
# ===========================================================================

async def _is_status_query(text: str) -> bool:
    """
    Disambiguates status questions from bills containing words like 'बाकी रक्कम'.
    Uses Meta's Muse Spark to classify the intent when available.
    """
    text_clean = text.strip()
    low = text_clean.lower()

    # If it contains explicit amount or bill indicators without a question word, it's a bill
    bill_indicators = ["₹", "rs.", "rs ", "inr", "रक्कम", "महावितरण", "msedcl", "due date", "तारीख"]
    if any(ind in low for ind in bill_indicators) and not any(q in low for q in ["काय बाकी", "कोणती कामे", "pending?"]):
        return False

    explicit_questions = [
        "काय बाकी आहे",
        "काय बाकी",
        "कोणती कामे बाकी",
        "pending tasks",
        "what is pending",
        "what's pending",
        "status",
        "dashboard",
    ]
    if any(q in low for q in explicit_questions):
        return True

    # Single-word questions
    if low in ("बाकी?", "बाकी", "pending?"):
        return True

    # Use Muse Spark to classify intent when LLM client configured
    if settings.llm_api_key and settings.llm_base_url:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
            prompt = (
                f"Classify if this WhatsApp message is asking for a status/task list or reporting a bill.\n"
                f"Message: \"{text}\"\n"
                f"Output ONLY 'status_query' or 'bill_document'."
            )
            res = await client.chat.completions.create(
                model=settings.muse_spark_model,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
            )
            ans = (res.choices[0].message.content or "").strip().lower()
            return "status_query" in ans
        except Exception:
            pass

    return False


@whatsapp_router.get("/webhook")
async def whatsapp_verify(request: Request):
    """WhatsApp Cloud API handshake verification."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    if mode == "subscribe" and token == settings.whatsapp_verify_token:
        return PlainTextResponse(content=challenge or "", status_code=200)
    logger.warning("WhatsApp verify handshake rejected: invalid token or mode")
    raise HTTPException(status_code=403, detail="Invalid verify token")


@whatsapp_router.post("/webhook")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Inbound WhatsApp webhook endpoint.
    Strictly verifies Meta's HMAC SHA256 signature on every delivery.
    Immediately returns 200 OK after deduplicating message IDs, and offloads
    processing to background tasks.
    """
    raw_body = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not settings.whatsapp_app_secret or not sig:
        logger.warning("WhatsApp webhook rejected: secret unset or X-Hub-Signature-256 missing")
        raise HTTPException(status_code=403, detail="Signature missing or secret unset")

    expected_sig = "sha256=" + hmac.new(
        settings.whatsapp_app_secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        logger.warning("WhatsApp webhook rejected: signature mismatch")
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        body = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return {"status": "ok"}

    # Loop over all entries, changes, and messages
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            for msg in messages:
                msg_id = msg.get("id")
                if msg_id:
                    # In-memory fast-check
                    if msg_id in _processed_wa_messages:
                        logger.info(f"Duplicate WhatsApp message ID skipped (memory): {msg_id}")
                        continue
                    _processed_wa_messages.append(msg_id)

                    # Persistent DB check with unique constraint
                    try:
                        async with AsyncSessionLocal() as db:
                            existing = await db.execute(
                                select(ProcessedMessage).where(ProcessedMessage.message_id == msg_id)
                            )
                            if existing.scalar_one_or_none():
                                logger.info(f"Duplicate WhatsApp message ID skipped (DB): {msg_id}")
                                continue
                            db.add(ProcessedMessage(message_id=msg_id, channel="whatsapp"))
                            await db.commit()
                    except Exception as db_exc:
                        logger.warning(f"ProcessedMessage DB check/insert error: {db_exc}")
                        continue

                # Offload message processing to background task
                background_tasks.add_task(process_single_whatsapp_message, msg)

    return {"status": "ok"}


async def process_single_whatsapp_message(msg: dict):
    """Handles an individual inbound WhatsApp message in a background task."""
    from_phone = msg.get("from", "")
    if not from_phone:
        return

    # Look up member by phone or telegram_id and record last_inbound_at
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(Member).where(
                (Member.phone == from_phone) | (Member.phone == f"+{from_phone}") | (Member.telegram_id == from_phone)
            )
        )
        member = res.scalars().first()
        if member:
            member.last_inbound_at = datetime.utcnow()
            await db.commit()

    if not member:
        await _send_whatsapp_message(
            from_phone,
            "तुम्ही अजून नोंदणीकृत नाही. कृपया तुमच्या कुटुंबातील सदस्याला सांगा की तुम्हाला जोडावे.",
        )
        return

    household_id = member.household_id

    # 1. Handle Interactive Button Reply or Template Button Tap
    btn_id = None
    if msg.get("type") == "interactive":
        btn_reply = msg.get("interactive", {}).get("button_reply", {})
        btn_id = btn_reply.get("id", "")
    elif msg.get("type") == "button":
        # Meta WhatsApp template quick-reply button tap
        btn_id = msg.get("button", {}).get("payload", "") or msg.get("button", {}).get("text", "")

    if btn_id:
        # Claim
        if btn_id.startswith(("claim:", "claim_")):
            task_id = int(btn_id.replace("claim:", "").replace("claim_", ""))
            async with AsyncSessionLocal() as db:
                task = await db.get(Task, task_id)
                if task and task.household_id == household_id:
                    task.status = TaskStatus.claimed
                    task.assignee_id = member.id
                    task.updated_at = datetime.utcnow()
                    db.add(Event(
                        household_id=task.household_id,
                        task_id=task.id,
                        actor=f"member:{member.name}",
                        action="claimed",
                        reason=f"Claimed via WhatsApp by {member.name}",
                        payload={"member_id": member.id, "phone": from_phone},
                    ))
                    await db.commit()
                    await _send_whatsapp_message(
                        from_phone,
                        f"✅ Task #{task.id} ('{task.title}') has been claimed by you on the family board.\n"
                        f"When finished, tap Mark Done.",
                        buttons=[{"id": f"done:{task.id}", "title": "Mark Done"}],
                    )
            return

        # Done
        elif btn_id.startswith(("done:", "done_")):
            task_id = int(btn_id.replace("done:", "").replace("done_", ""))
            async with AsyncSessionLocal() as db:
                task = await db.get(Task, task_id)
                if task and task.household_id == household_id:
                    task.status = TaskStatus.done
                    task.updated_at = datetime.utcnow()

                    if task.recurrence == "monthly" and task.due_date:
                        next_due = task.due_date + timedelta(days=30)
                        next_task = Task(
                            household_id=task.household_id,
                            category=task.category,
                            title=task.title,
                            amount=task.amount,
                            due_date=next_due,
                            payee=task.payee,
                            status=TaskStatus.confirmed,
                            assignee_id=task.assignee_id,
                            recurrence="monthly",
                        )
                        db.add(next_task)

                    db.add(Event(
                        household_id=task.household_id,
                        task_id=task.id,
                        actor=f"member:{member.name}",
                        action="completed",
                        reason=f"Marked completed via WhatsApp by {member.name}",
                        payload={"member_id": member.id, "phone": from_phone},
                    ))
                    await db.commit()
                    await _send_whatsapp_message(
                        from_phone,
                        f"✔️ '{task.title}' काम पूर्ण झाल्याचे नोंदवले आहे. पालकांना कळवले आहे. 🙏",
                    )
                    await notify_parents_task_done(task, completed_by_name=member.name)
            return

        # Confirmation: confirm_yes
        elif btn_id.startswith(("confirm_yes:", "confirm:yes:")):
            artifact_id = int(btn_id.split(":")[-1])
            async with AsyncSessionLocal() as db:
                artifact = await db.get(Artifact, artifact_id)
                if not artifact or artifact.household_id != household_id:
                    await _send_whatsapp_message(from_phone, "⚠️ हे काम तुमच्या कुटुंबाचे नाही.")
                    return

            graph = await get_compiled_graph()
            config = {"configurable": {"thread_id": str(artifact_id)}}
            final_state = None
            async for step in graph.astream(Command(resume={"confirmed": True}), config=config):
                final_state = step
            await _send_whatsapp_message(
                from_phone,
                "✅ माहितीची पुष्टी झाली! काम कुटुंब बोर्डवर जोडले आहे. 🙏"
            )
            state = {}
            if final_state:
                for node_output in final_state.values():
                    if isinstance(node_output, dict):
                        state.update(node_output)
            if state.get("sibling_notification") and state.get("task_id"):
                await _notify_siblings_new_task(
                    member.household_id,
                    state["task_id"],
                    state["sibling_notification"],
                    sender_chat_id=from_phone,
                )
            return

        # Confirmation: confirm_no
        elif btn_id.startswith(("confirm_no:", "confirm:no:")):
            artifact_id = int(btn_id.split(":")[-1])
            async with AsyncSessionLocal() as db:
                artifact = await db.get(Artifact, artifact_id)
                if not artifact or artifact.household_id != household_id:
                    await _send_whatsapp_message(from_phone, "⚠️ हे काम तुमच्या कुटुंबाचे नाही.")
                    return

            graph = await get_compiled_graph()
            config = {"configurable": {"thread_id": str(artifact_id)}}
            async for step in graph.astream(Command(resume={"confirmed": False}), config=config):
                pass
            await _send_whatsapp_message(
                from_phone,
                "❌ ठीक आहे, आम्ही हे काम रद्द केले आहे. कृपया पुन्हा पाठवा. 🙏"
            )
            return

    # 2. Handle Text Messages & Status Queries
    text_content = msg.get("text", {}).get("body", "").strip()
    if text_content:
        if await _is_status_query(text_content):
            async with AsyncSessionLocal() as db:
                tasks_res = await db.execute(
                    select(Task).where(
                        Task.household_id == household_id,
                        Task.status.in_([TaskStatus.new, TaskStatus.confirmed, TaskStatus.claimed, TaskStatus.escalated, TaskStatus.needs_review]),
                    ).order_by(Task.due_date.asc())
                )
                pending_tasks = tasks_res.scalars().all()

            if not pending_tasks:
                reply = "सध्या कोणतीही कामे बाकी नाहीत! सर्व कामे पूर्ण झाली आहेत. 🙏"
            else:
                lines = ["📋 सध्या बाकी असलेली कामे:"]
                for i, t in enumerate(pending_tasks[:5], 1):
                    amt = f" ({t.amount})" if t.amount else ""
                    lines.append(f"{i}. {t.title}{amt}")
                reply = "\n".join(lines)

            await _send_whatsapp_message(from_phone, reply)
            return

        # Store text artifact and process with agent
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

        await _run_agent(
            artifact_id=artifact_id,
            household_id=household_id,
            artifact_type="image",
            file_url="text://message",
            chat_id=from_phone,
            channel="whatsapp",
        )
        return

    # 3. Handle Voice / Image
    msg_type = msg.get("type", "")
    if msg_type in ("audio", "voice"):
        media_id = msg.get(msg_type, {}).get("id", "")
        artifact_type = ArtifactType.voice
    elif msg_type == "image":
        media_id = msg.get("image", {}).get("id", "")
        artifact_type = ArtifactType.image
    else:
        await _send_whatsapp_message(from_phone, "🙏 संदेश मिळाला!")
        return

    async with AsyncSessionLocal() as db:
        artifact = Artifact(
            household_id=household_id,
            type=artifact_type,
            file_url=f"whatsapp://{media_id}",
        )
        db.add(artifact)
        await db.commit()
        await db.refresh(artifact)
        artifact_id = artifact.id

    await _run_agent(
        artifact_id=artifact_id,
        household_id=household_id,
        artifact_type=artifact_type.value,
        file_url=f"whatsapp://{media_id}",
        chat_id=from_phone,
        channel="whatsapp",
    )
