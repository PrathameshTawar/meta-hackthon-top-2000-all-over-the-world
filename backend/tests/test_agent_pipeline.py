import asyncio
import pytest
from app.db.session import init_db
from app.db.seed import seed_data
from app.api.webhooks import _run_agent
from app.db.models import Artifact, ArtifactType, Task, Evidence
from app.db.session import AsyncSessionLocal
from sqlalchemy import select


@pytest.mark.asyncio
async def test_agent_pipeline():
    await init_db()
    await seed_data()

    async with AsyncSessionLocal() as db:
        art = Artifact(
            household_id=1,
            type=ArtifactType.image,
            file_url="test://msedcl_dec.png",
            raw_text="Mahavitaran Electricity Bill. Due Date: 2026-11-20. Total Amount: ₹2,150. Payee: Mahavitaran (MSEDCL).",
        )
        db.add(art)
        await db.commit()
        await db.refresh(art)
        art_id = art.id

    await _run_agent(
        artifact_id=art_id,
        household_id=1,
        artifact_type="image",
        file_url="test://msedcl_dec.png",
        chat_id="test_chat",
    )

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Task).where(Task.household_id == 1).order_by(Task.id.desc()))
        latest_task = res.scalars().first()
        assert latest_task is not None
        assert "2,150" in (latest_task.amount or "")
        assert latest_task.payee == "Mahavitaran (MSEDCL)"

        ev_res = await db.execute(select(Evidence).where(Evidence.task_id == latest_task.id))
        evs = ev_res.scalars().all()
        assert len(evs) > 0
        field_names = [e.field_name for e in evs]
        assert "amount" in field_names
        print("Test passed! Latest task created with verified evidence.")


if __name__ == "__main__":
    asyncio.run(test_agent_pipeline())
