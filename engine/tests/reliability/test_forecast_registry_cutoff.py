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
    assert snapshot["forecast_at"] == entry["created_at"]
    assert snapshot["scope"] == "BR" and snapshot["horizon"] is None
    assert snapshot["probability_raw"] == 0.62 and snapshot["probability_calibrated"] is None
    assert snapshot["abstention"] is False and snapshot["calibrator_version"] is None
    assert verify(entry)


def test_registry_preserves_prospective_metadata_without_outcome_fields():
    cutoff = datetime(2026, 10, 3, 17, 30, tzinfo=timezone.utc)
    forecast = {**FORECAST, "event_id": "ev-1", "created_at": "2026-10-03T17:29:00Z",
                "horizon_minutes": 60, "probability_calibrated": 0.58,
                "calibrator_version": "cal-2", "coverage": 0.8,
                "evidence": {"missingness": {"energy": "stale"}}}
    snapshot = json.loads(build_entry(forecast, {"baseline": 12}, cutoff, "m1", "f1", "b1", {})["snapshot"])
    assert snapshot["event_id"] == "ev-1" and snapshot["forecast_at"] == forecast["created_at"]
    assert snapshot["horizon"] == 60 and snapshot["probability_calibrated"] == 0.58
    assert snapshot["coverage"] == 0.8 and snapshot["missingness"] == {"energy": "stale"}
    assert "outcome" not in snapshot and "resolved_at" not in snapshot


def test_registry_rejects_naive_cutoff_instead_of_ambiguously_timestamping_features():
    with pytest.raises(ValueError, match="timezone"):
        build_entry(FORECAST, {}, datetime(2026, 10, 3, 17, 30), "m1", "f1", "b1", {})


def test_registry_hash_is_deterministic_for_semantically_identical_feature_order():
    cutoff = datetime(2026, 10, 3, 17, 30, tzinfo=timezone.utc)
    first = build_entry(FORECAST, {"baseline": 12, "current": 33}, cutoff, "m1", "f1", "b1", {"A": False, "B": True})
    second = build_entry(FORECAST, {"current": 33, "baseline": 12}, cutoff, "m1", "f1", "b1", {"B": True, "A": False})
    assert first["snapshot"] == second["snapshot"]
    assert first["snapshot_hash"] == second["snapshot_hash"]
