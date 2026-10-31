import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from app.db.models import Base

logger = logging.getLogger(__name__)

connect_args = {}
db_url = settings.database_url
if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

try:
    engine = create_async_engine(db_url, echo=False, connect_args=connect_args)
except (ModuleNotFoundError, Exception) as exc:
    # If asyncpg or DB driver is not installed (e.g. local dev on Windows), fallback to SQLite
    logger.warning("Could not initialize DB with %s (%s). Falling back to SQLite.", db_url, exc)
    db_url = "sqlite+aiosqlite:///./saath.db"
    connect_args = {"check_same_thread": False}
    engine = create_async_engine(db_url, echo=False, connect_args=connect_args)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    """Create all tables on startup (dev convenience; use Alembic for prod)."""
    global engine, AsyncSessionLocal
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        if not str(engine.url).startswith("sqlite"):
            logger.warning("PostgreSQL connection to %s failed (%s). Falling back to SQLite.", engine.url, exc)
            fallback_url = "sqlite+aiosqlite:///./saath.db"
            engine = create_async_engine(fallback_url, echo=False, connect_args={"check_same_thread": False})
            AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        else:
            raise


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
