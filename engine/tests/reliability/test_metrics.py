from datetime import datetime, timezone

import pytest

from pulso_engine.validation.metrics import (abstention_rate, base_rate_reference, brier, brier_skill, calibration_error,
                                             classification, coverage, detection_delay, false_negative_rate, lead_time,
                                             lead_time_summary, log_loss)


def test_metrics_cover_perfect_wrong_and_empty_predictions():
    assert brier([(1.0, 1), (0.0, 0)]) == 0.0
    assert brier([(1.0, 0), (0.0, 1)]) == 1.0
    assert brier([]) is None and log_loss([]) is None and calibration_error([]) is None


def test_constant_half_predictions_and_classification():
    pairs = [(0.5, 1), (0.5, 0)]
    assert brier(pairs) == 0.25 and base_rate_reference([1, 0]) == 0.25
    assert classification(pairs)["recall"] == 1.0


def test_metric_boundary_rejects_invalid_probability_outcome_and_bins():
    for metric in (brier, log_loss, calibration_error):
        with pytest.raises(ValueError):
            metric([(1.01, 0)])
        with pytest.raises(ValueError):
            metric([(0.5, 2)])
    with pytest.raises(ValueError):
        calibration_error([(0.5, 1)], bins=0)


def test_metrics_are_order_invariant_and_zero_positive_cases_are_honest():
    pairs = [(0.9, 1), (0.8, 1), (0.2, 0), (0.1, 0)]
    assert brier(pairs) == 0.025
    assert brier(pairs) == brier(list(reversed(pairs)))
    assert log_loss(pairs) == log_loss(list(reversed(pairs)))
    assert calibration_error(pairs) == calibration_error(list(reversed(pairs)))
    assert classification(pairs) == classification(list(reversed(pairs)))
    assert classification([(0.1, 0), (0.2, 0)])["recall"] is None
    assert classification([(0.9, 0), (0.1, 1)])["f1"] == 0.0


def test_lead_time_summary_includes_abstentions_as_missing_detection():
    summary = lead_time_summary([28.0, None])
    assert summary["coverage"] == 0.5 and summary["median"] == 28.0


def test_skill_error_rates_coverage_and_temporal_metrics():
    pairs = [(0.9, 1), (0.8, 0), (0.1, 1), (0.1, 0)]
    assert brier_skill(0.16, 0.20) == 0.2 and brier_skill(0.1, 0) is None
    assert false_negative_rate(pairs) == 0.5
    assert coverage(["detected", None, "detected"]) == 0.6667 and abstention_rate(["detected", None, "detected"]) == 0.3333
    event = datetime(2026, 10, 3, 17, tzinfo=timezone.utc)
    detected = datetime(2026, 10, 3, 17, 32, tzinfo=timezone.utc)
    confirmed = datetime(2026, 10, 3, 18, tzinfo=timezone.utc)
    assert detection_delay(event, detected) == 32 and lead_time(detected, confirmed) == 28
    assert lead_time(confirmed, detected) == -28
