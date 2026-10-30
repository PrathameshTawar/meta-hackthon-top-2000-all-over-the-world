import pytest
from app.db.session import init_db


@pytest.fixture(autouse=True)
async def tables():
    """Ensure all database tables exist before each test (create_all skips existing tables)."""
    await init_db()
