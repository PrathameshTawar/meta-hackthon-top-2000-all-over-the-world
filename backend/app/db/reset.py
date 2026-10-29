"""
Reset script for Saath.
Wipes existing tables and re-seeds the demo household cleanly.
Can be executed via: python -m app.db.reset
"""
import asyncio
from app.db.session import engine, init_db
from app.db.models import Base
from app.db.seed import seed_data


async def reset_db():
    print("Dropping all existing tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("Re-creating all tables...")
    await init_db()
    print("Seeding fresh demo data...")
    await seed_data()
    print("Reset complete!")


if __name__ == "__main__":
    asyncio.run(reset_db())
