import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from datetime import datetime

from app.main import app
from app.config import settings
from app.db.models import Household, Member, MemberRole
from app.db.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_h1_data_models_and_api_skeleton(monkeypatch):
    monkeypatch.setattr(settings, "admin_secret", "saath_admin_secret_demo")

    def unique_phone():
        return f"+919{uuid.uuid4().int % 1000000000:09d}"

    # 1. Setup a test household with a parent and child, plus another household
    async with AsyncSessionLocal() as db:
        h1 = Household(name="Health Family 1", primary_language="mr")
        h2 = Household(name="Health Family 2", primary_language="mr")
        db.add_all([h1, h2])
        await db.commit()
        await db.refresh(h1)
        await db.refresh(h2)

        parent1 = Member(household_id=h1.id, name="Aai", role=MemberRole.parent, phone=unique_phone())
        child1 = Member(household_id=h1.id, name="Rohan", role=MemberRole.child, phone=unique_phone())
        parent2 = Member(household_id=h2.id, name="Other Parent", role=MemberRole.parent, phone=unique_phone())
        db.add_all([parent1, child1, parent2])
        await db.commit()
        await db.refresh(parent1)
        await db.refresh(child1)
        await db.refresh(parent2)

        h1_id = h1.id
        parent1_id = parent1.id
        child1_id = child1.id
        parent2_id = parent2.id

    headers = {"X-Admin-Token": "saath_admin_secret_demo"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test 1: Create medication with invalid time -> 422
        res_invalid_time = await client.post(
            "/health/medications",
            json={
                "household_id": h1_id,
                "member_id": parent1_id,
                "name": "Blood Pressure Pill",
                "dose_text": "1 tablet",
                "times": ["25:99"],
                "owner_child_id": child1_id,
            },
            headers=headers,
        )
        assert res_invalid_time.status_code == 422, f"Expected 422 for invalid time, got {res_invalid_time.status_code}"

        # Test 2: Member from another household -> 404
        res_wrong_household = await client.post(
            "/health/medications",
            json={
                "household_id": h1_id,
                "member_id": parent2_id,  # belongs to h2!
                "name": "Blood Pressure Pill",
                "dose_text": "1 tablet",
                "times": ["08:00"],
                "owner_child_id": child1_id,
            },
            headers=headers,
        )
        assert res_wrong_household.status_code == 404, f"Expected 404 for member from another household, got {res_wrong_household.status_code}"

        # Test 3: Member is not a parent -> 422
        res_not_parent = await client.post(
            "/health/medications",
            json={
                "household_id": h1_id,
                "member_id": child1_id,  # child, not parent!
                "name": "Blood Pressure Pill",
                "dose_text": "1 tablet",
                "times": ["08:00"],
                "owner_child_id": child1_id,
            },
            headers=headers,
        )
        assert res_not_parent.status_code == 422, f"Expected 422 for non-parent member_id, got {res_not_parent.status_code}"

        # Test 4: Valid creation of medication
        res_create_med = await client.post(
            "/health/medications",
            json={
                "household_id": h1_id,
                "member_id": parent1_id,
                "name": "Amlodipine",
                "dose_text": "1 tab",
                "times": ["08:00", "20:00"],
                "owner_child_id": child1_id,
            },
            headers=headers,
        )
        assert res_create_med.status_code in (200, 201), f"Expected 200/201, got {res_create_med.status_code}: {res_create_med.text}"
        med_id = res_create_med.json()["id"]

        # Test 5: Valid creation of threshold
        res_create_thresh = await client.post(
            "/health/thresholds",
            json={
                "household_id": h1_id,
                "member_id": parent1_id,
                "kind": "bp",
                "field": "value_1",
                "op": "gt",
                "limit": 150.0,
                "note": "Doctor advised",
                "set_by_member_id": child1_id,
            },
            headers=headers,
        )
        assert res_create_thresh.status_code in (200, 201), f"Expected 200/201, got {res_create_thresh.status_code}: {res_create_thresh.text}"

        # Test 6: Summary returns created items
        res_summary = await client.get(f"/health/{h1_id}/summary", headers=headers)
        assert res_summary.status_code == 200, f"Expected 200, got {res_summary.status_code}"
        summary_data = res_summary.json()
        assert len(summary_data["active_medications"]) >= 1
        assert any(m["id"] == med_id for m in summary_data["active_medications"])
        assert len(summary_data["active_thresholds"]) >= 1
