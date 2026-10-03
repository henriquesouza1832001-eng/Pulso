from pulso_engine.anomaly import NO_BASELINE, percentile_rank, window_anomaly
from pulso_engine.baseline import INSUFFICIENT, Baseline, SeasonalBaseline


def test_insufficient_baseline_never_anomaly():
    r = window_anomaly(50, 15, INSUFFICIENT)
    assert r["score"] == 0.0 and r["status"] == NO_BASELINE


def test_spec_example_is_anomaly():
    base = SeasonalBaseline(16.8, 4.0, 6, "dow_hour", 6, (14, 18, 17, 15, 19, 17))  # 4,2 sinais/15 min
    r = window_anomaly(39, 15, base)
    assert r["status"] == "ANOMALY" and r["z"] > 6 and r["percentile"] == 1.0


def test_normal_level_is_normal():
    base = SeasonalBaseline(16.8, 4.0, 6, "dow_hour", 6, (14, 18, 17, 15, 19, 17))
    r = window_anomaly(4, 15, base)
    assert r["status"] == "NORMAL" and r["score"] == 0.0


def test_ewma_baseline_works_without_percentile():
    r = window_anomaly(30, 60, Baseline(5.0, 2.0, 24, 20))
    assert r["basis"] == "ewma" and r["percentile"] is None and r["status"] == "ANOMALY"


def test_percentile_needs_samples():
    assert percentile_rank(10, [1, 2, 3]) is None
    assert percentile_rank(3, [1, 2, 3, 4, 5]) == 0.6
