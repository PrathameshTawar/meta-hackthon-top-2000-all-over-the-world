import os
import logging
from sqlalchemy import event
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from app.db.models import Base

logger = logging.getLogger(__name__)


def _apply_sqlite_pragmas(engine):
    if not str(engine.url).startswith("sqlite"):
        return
    @event.listens_for(engine.sync_engine, "connect")
    def _pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()


connect_args = {}
database_host = os.getenv("DB_HOST")
if database_host:
    database_username = os.getenv("DB_USER")
    database_password = os.getenv("DB_PASSWORD")
    database_name = os.getenv("DB_NAME")
    if not database_username or not database_password or not database_name:
        raise RuntimeError("DB_HOST requires DB_USER, DB_PASSWORD, and DB_NAME to be configured")
    db_url = URL.create(
        "postgresql+asyncpg",
        username=database_username,
        password=database_password,
        host=database_host,
        port=5432,
        database=database_name,
    ).render_as_string(hide_password=False)
else:
    db_url = os.getenv("DATABASE_URL") or settings.database_url

if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

try:
    engine = create_async_engine(db_url, echo=False, connect_args=connect_args)
    _apply_sqlite_pragmas(engine)
except Exception as exc:
    if settings.environment == "production":
        raise
    # If asyncpg or DB driver is not installed (e.g. local dev on Windows), fallback to SQLite
    logger.warning("Could not initialize DB with %s (%s). Falling back to SQLite.", db_url, exc)
    db_url = "sqlite+aiosqlite:///./saath.db"
    connect_args = {"check_same_thread": False}
    engine = create_async_engine(db_url, echo=False, connect_args=connect_args)
    _apply_sqlite_pragmas(engine)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    """Create all tables on startup (dev convenience; use Alembic for prod)."""
    global engine, AsyncSessionLocal

    def _migrate_sqlite(sync_conn):
        from sqlalchemy import text
        res = sync_conn.execute(text("PRAGMA table_info(members)"))
        cols = [row[1] for row in res.fetchall()]
        if cols and "language" not in cols:
            sync_conn.execute(text("ALTER TABLE members ADD COLUMN language VARCHAR(10) DEFAULT 'mr'"))
        if cols and "timezone" not in cols:
            sync_conn.execute(text("ALTER TABLE members ADD COLUMN timezone VARCHAR(50) DEFAULT 'Asia/Kolkata'"))
        if cols and "quiet_hours_start" not in cols:
            sync_conn.execute(text("ALTER TABLE members ADD COLUMN quiet_hours_start INTEGER DEFAULT 22"))
        if cols and "quiet_hours_end" not in cols:
            sync_conn.execute(text("ALTER TABLE members ADD COLUMN quiet_hours_end INTEGER DEFAULT 7"))

        res_v = sync_conn.execute(text("PRAGMA table_info(vitals)"))
        cols_v = [row[1] for row in res_v.fetchall()]
        if cols_v and "source" not in cols_v:
            sync_conn.execute(text("ALTER TABLE vitals ADD COLUMN source VARCHAR(20) DEFAULT 'voice'"))

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            if str(engine.url).startswith("sqlite"):
                await conn.run_sync(_migrate_sqlite)
    except Exception as exc:
        if not str(engine.url).startswith("sqlite"):
            if settings.environment == "production":
                raise
            logger.warning("PostgreSQL connection to %s failed (%s). Falling back to SQLite.", engine.url, exc)
            fallback_url = "sqlite+aiosqlite:///./saath.db"
            engine = create_async_engine(fallback_url, echo=False, connect_args={"check_same_thread": False})
            _apply_sqlite_pragmas(engine)
            AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                await conn.run_sync(_migrate_sqlite)
        else:
            raise


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
