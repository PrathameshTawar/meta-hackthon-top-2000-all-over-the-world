import pytest
from pathlib import Path
from tests.run_eval import evaluate_vitals_set, VITALS_PATH


@pytest.mark.asyncio
async def test_vitals_evaluation_slice(monkeypatch):
    """Verify that evaluate_vitals_set runs cleanly on vitals_items.json and reaches targets."""
    class DummyArgs:
        live = False

    res = await evaluate_vitals_set(VITALS_PATH, DummyArgs())
    assert res["reading_accuracy"] >= 90.0
    assert res["threshold_accuracy"] == 100.0
    assert res["non_vital_rejection_rate"] == 100.0
    assert res["non_vital_rejected"] == 5

