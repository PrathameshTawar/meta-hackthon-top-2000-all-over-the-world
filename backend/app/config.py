from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Database (defaults to local SQLite for zero-setup dev & eval; PostgreSQL in production)
    database_url: str = "sqlite+aiosqlite:///./saath.db"
    checkpoints_db_path: str = "data/checkpoints.db"

    # Meta AI Model API (Official Meta Endpoint: https://api.meta.ai/v1)
    # Alternative / Backup: Baseten endpoint "https://inference.baseten.co/v1" with model "meta-models/muse-spark-open-1026"
    llm_base_url: str = "https://api.meta.ai/v1"
    llm_api_key: str = ""
    muse_spark_model: str = "muse-spark-1.3"
    muse_voice_model: str = "muse-voice-transcribe-1.0"
    
    # Backwards-compatibility aliases
    meta_api_key: str = ""

    # Security & Admin
    admin_secret: str = "saath_admin_secret_demo"
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]

    # Telegram
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""

    # WhatsApp Cloud API (Meta)
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""  # Set via .env for webhook handshake
    whatsapp_app_secret: str = ""
    whatsapp_api_version: str = "v22.0"  # Current Meta Graph API version (v21.0 or v22.0)

    # App & Localization
    base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    default_language: str = "mr"  # Marathi ("mr") or Hindi ("hi")
    timezone_name: str = "Asia/Kolkata"

    # Escalation
    escalation_days_before: int = 3

    class Config:
        env_file = (".env", "../.env")
        extra = "ignore"

    def get_api_key(self) -> str:
        key = (self.llm_api_key or self.meta_api_key or os.getenv("BASETEN_API_KEY", "")).strip()
        placeholders = {
            "",
            "your_meta_api_key_here",
            "your-meta-api-key",
            "your_api_key_here",
            "your_key_here",
            "your-key-here",
            "change_me",
        }
        return "" if key in placeholders else key


settings = Settings()
