"""
Saath Telegram Bot (Long-polling & Webhook helper).
Supports:
1. Long polling for local development and live video recording without public HTTPS.
2. Voice notes & photo capture forwarding to FastAPI backend.
3. Inline Claim buttons for siblings.
4. Watch-friendly first lines in notifications.
5. Interactive terminal simulation mode when running without a bot token.
"""
import asyncio
import os
import sys
import logging
import httpx
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("saath-bot")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


async def send_telegram_nudge_with_claim(chat_id: str | int, task_id: int, title: str, amount: str, due_date: str):
    """
    Sends an escalation notification with a watch-friendly first line and an inline Claim button.
    Line 1: Action + deadline (for smartwatch screens).
    """
    if not BOT_TOKEN:
        logger.info(f"[SIMULATED BOT -> {chat_id}]:\n⚠️ {title} due soon, unclaimed!\nAmount: {amount}\n[Inline Button: ✅ Claim Task #{task_id}]")
        return

    text = (
        f"⚠️ *{title} due {due_date}, unclaimed!*\n\n"
        f"Amount: *{amount}*\n"
        f"Please tap below to claim and coordinate with your siblings."
    )
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ Claim Task", "callback_data": f"claim_{task_id}"},
                {"text": "📋 View Board", "url": f"http://localhost:3000"},
            ]
        ]
    }

    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": reply_markup,
            },
        )


async def handle_callback_query(callback: dict):
    """Handle inline button clicks like 'claim_123'."""
    cb_id = callback["id"]
    data = callback.get("data", "")
    user_id = callback["from"]["id"]
    chat_id = callback["message"]["chat"]["id"]

    if data.startswith("claim_"):
        task_id = int(data.split("_")[1])
        logger.info(f"User {user_id} clicked Claim on task {task_id}")

        # Update task in backend
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.patch(
                    f"{BACKEND_URL}/tasks/{task_id}",
                    json={"status": "claimed"},
                )
                if res.status_code == 200:
                    # Answer callback
                    await client.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery",
                        json={"callback_query_id": cb_id, "text": "✅ You claimed this task! Board updated."},
                    )
                    await client.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        json={"chat_id": chat_id, "text": f"🎉 You claimed Task #{task_id}. Marked on your shared family board."},
                    )
        except Exception as exc:
            logger.error(f"Failed to claim task: {exc}")


async def poll_telegram():
    """Long polling loop for Telegram updates."""
    offset = 0
    logger.info("Starting Telegram long-polling loop...")

    async with httpx.AsyncClient(timeout=40) as client:
        while True:
            try:
                resp = await client.get(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                    params={"offset": offset, "timeout": 25},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1

                        if "callback_query" in update:
                            await handle_callback_query(update["callback_query"])
                        elif "message" in update:
                            # Forward message to backend webhook endpoint
                            await client.post(
                                f"{BACKEND_URL}/webhook/telegram",
                                json=update,
                            )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Polling error: {e}. Retrying in 5s...")
                await asyncio.sleep(5)


async def interactive_terminal_mode():
    """Interactive mode for testing without a Telegram token."""
    print("\n=======================================================")
    print("      SAATH TELEGRAM SIMULATOR (CLI Mode)             ")
    print("=======================================================")
    print("No TELEGRAM_BOT_TOKEN set; running in local interactive simulation.")
    print("Type a Marathi or English family message to test live capture,")
    print("or 'quit' to exit.\n")

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            try:
                line = await asyncio.to_thread(input, "Parent/Child Message > ")
                if not line or line.strip().lower() in ("quit", "exit"):
                    break

                print("Sending to Saath backend agent...")
                res = await client.post(
                    f"{BACKEND_URL}/admin/ingest/simulate",
                    json={"household_id": 1, "type": "voice", "raw_text": line.strip()},
                )
                if res.status_code == 200:
                    print(f"✅ Processed successfully! Artifact #{res.json().get('artifact_id')}")
                    print("Check your board at http://localhost:3000 to see the new task.\n")
                else:
                    print(f"⚠️ Error from backend: {res.status_code} {res.text}\n")
            except (KeyboardInterrupt, EOFError):
                break


def main():
    if BOT_TOKEN:
        asyncio.run(poll_telegram())
    else:
        asyncio.run(interactive_terminal_mode())


if __name__ == "__main__":
    main()
