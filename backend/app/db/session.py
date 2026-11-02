import logging
from sqlalchemy import event
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
db_url = settings.database_url
if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

try:
    engine = create_async_engine(db_url, echo=False, connect_args=connect_args)
    _apply_sqlite_pragmas(engine)
except (ModuleNotFoundError, Exception) as exc:
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

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            if str(engine.url).startswith("sqlite"):
                await conn.run_sync(_migrate_sqlite)
    except Exception as exc:
        if not str(engine.url).startswith("sqlite"):
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
