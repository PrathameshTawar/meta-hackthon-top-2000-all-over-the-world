import pytest
from app.db.session import init_db


@pytest.fixture(autouse=True)
async def tables():
    """Ensure all database tables exist before each test."""
    await init_db()
