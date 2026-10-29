from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database (defaults to local SQLite for easy zero-setup dev & tests; supports PostgreSQL in production)
    database_url: str = "sqlite+aiosqlite:///./saath.db"

    # Meta / Fireworks AI
    meta_api_key: str = ""
    muse_voice_model: str = "accounts/fireworks/models/whisper-v3"  # update from docs
    muse_spark_model: str = "accounts/fireworks/models/llama-v3p2-11b-vision-instruct"  # update from docs

    # Telegram
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""

    # App
    base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    default_language: str = "mr"  # Marathi; fall back to "hi" if transcription weak

    # Escalation
    escalation_days_before: int = 3

    class Config:
        env_file = ".env"


settings = Settings()
