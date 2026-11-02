import os
import tempfile
import shutil
from pathlib import Path
import pytest

# Isolate test database before any app imports
_test_dir = tempfile.mkdtemp(prefix="saath_pytest_db_")
_test_db = Path(_test_dir) / "test_saath.db"
_test_checkpoints = Path(_test_dir) / "test_checkpoints.db"

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_test_db.as_posix()}"
os.environ["CHECKPOINTS_DB_PATH"] = str(_test_checkpoints.as_posix())
os.environ["ADMIN_SECRET"] = "saath_test_admin_secret"

from app.config import settings

# Force override in case settings was initialized earlier
settings.database_url = os.environ["DATABASE_URL"]
settings.checkpoints_db_path = os.environ["CHECKPOINTS_DB_PATH"]
settings.admin_secret = os.environ["ADMIN_SECRET"]

from app.db.session import init_db


@pytest.fixture(autouse=True)
async def tables():
    """Ensure all database tables exist before each test (create_all skips existing tables)."""
    await init_db()


@pytest.fixture(scope="session", autouse=True)
def cleanup_temp_dir():
    yield
    try:
        shutil.rmtree(_test_dir, ignore_errors=True)
    except Exception:
        pass
