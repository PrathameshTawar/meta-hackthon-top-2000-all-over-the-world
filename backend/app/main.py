from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.db.session import init_db
from app.db.seed import seed_data
from app.scheduler.escalation import start_scheduler
from app.agent.graph import close_checkpointer
from app.api import artifacts, tasks, members, households, webhooks, events, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_data()  # auto-seed demo household if empty
    scheduler = start_scheduler()
    yield
    if scheduler:
        scheduler.shutdown()
    await close_checkpointer()


app = FastAPI(
    title="Saath API",
    description="Family coordination agent backend (Meta Global AI Developer Hackathon)",
    version="0.2.0",
    lifespan=lifespan,
)

# Secure CORS: explicit origin list for frontend and local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Webhooks: distinct routes for Telegram (/webhook/telegram) and WhatsApp (/chat/webhook)
app.include_router(webhooks.telegram_router)
app.include_router(webhooks.whatsapp_router)
app.include_router(artifacts.router, prefix="/artifacts", tags=["artifacts"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(members.router, prefix="/members", tags=["members"])
app.include_router(households.router, prefix="/households", tags=["households"])
app.include_router(events.router, prefix="/events", tags=["events"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])


@app.get("/health")
@app.get("/healthz")
async def health():
    return {
        "status": "ok",
        "app": "saath",
        "version": "0.2.0",
        "model": settings.muse_spark_model,
        "llm_base_url": settings.llm_base_url,
    }
