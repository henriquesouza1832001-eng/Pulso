import json
from datetime import datetime, timezone

import pytest

from pulso_engine.validation.forecast_registry import build_entry, verify


FORECAST = {"forecast_id": "fc-cutoff", "probability": 0.62, "method": "m", "method_version": "1", "scope": "BR", "threshold": 50.0}


def test_registry_snapshot_binds_features_to_an_explicit_data_cutoff():
    cutoff = datetime(2026, 10, 3, 17, 30, tzinfo=timezone.utc)
    entry = build_entry(FORECAST, {"baseline": 12}, cutoff, "m1", "f1", "b1", {})
    snapshot = json.loads(entry["snapshot"])
    assert entry["created_at"] == "2026-10-03T17:30:00Z"
    assert snapshot["data_cutoff"] == entry["created_at"]
    assert snapshot["features"] == {"baseline": 12}
    assert verify(entry)


def test_registry_rejects_naive_cutoff_instead_of_ambiguously_timestamping_features():
    with pytest.raises(ValueError, match="timezone"):
        build_entry(FORECAST, {}, datetime(2026, 10, 3, 17, 30), "m1", "f1", "b1", {})


def test_registry_hash_is_deterministic_for_semantically_identical_feature_order():
    cutoff = datetime(2026, 10, 3, 17, 30, tzinfo=timezone.utc)
    first = build_entry(FORECAST, {"baseline": 12, "current": 33}, cutoff, "m1", "f1", "b1", {"A": False, "B": True})
    second = build_entry(FORECAST, {"current": 33, "baseline": 12}, cutoff, "m1", "f1", "b1", {"B": True, "A": False})
    assert first["snapshot"] == second["snapshot"]
    assert first["snapshot_hash"] == second["snapshot_hash"]
