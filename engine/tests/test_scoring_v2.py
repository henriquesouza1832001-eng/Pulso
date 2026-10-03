from datetime import datetime, timedelta, timezone

from pulso_engine.events import build_event, stats_for
from pulso_engine.models import EventStats, Signal
from pulso_engine.processing.clustering import cluster_signals
from pulso_engine.scoring.confidence import confidence
from pulso_engine.scoring.pulse import WEIGHTS, WEIGHTS_V2, pulse_score

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
V1_WEIGHTS = [("severity", 20), ("confidence", 15), ("velocity", 15), ("sources", 15), ("anomaly", 15),
              ("recency", 10), ("persistence", 5), ("geo_reach", 5)]


def sig(i, minutes_ago, cls="NEWS_HIGH", source=None, title="Acidente grave interdita a BR-381 em Betim"):
    ts = NOW - timedelta(minutes=minutes_ago)
    return Signal(signal_id=str(i), source_id=source or f"s{i}", source_class=cls, timestamp=ts, collected_at=ts, title=title,
                  category="TRAFFIC", hash=f"h{i}", state="MG")


def stats(**kw):
    base = dict(severity=50, signal_count=5, independent_sources=3, source_classes=frozenset({"NEWS_HIGH", "OFFICIAL"}),
                newest_age_min=5, persistence_min=30, velocity_per_hour=10)
    base.update(kw)
    return EventStats(**base)


def test_v1_weights_are_untouched_and_v2_sums_to_100():
    assert [(k, w) for k, _, w in WEIGHTS] == V1_WEIGHTS
    assert sum(w for _, _, w in WEIGHTS_V2) == 100 and {"acceleration", "sensors"} <= {k for k, _, _ in WEIGHTS_V2}


def test_flag_off_is_identical_to_v1_even_with_acceleration_present():
    for st in (stats(), stats(extra={"acceleration": 15.0}), stats(independent_sources=1, source_classes=frozenset({"SOCIAL"}))):
        assert pulse_score(st) == pulse_score(st, v2=False)
        assert not any(b["key"] in ("acceleration", "sensors") for b in pulse_score(st)[1])


def test_flag_on_via_environment(monkeypatch):
    monkeypatch.setenv("PULSO_FLAG_PULSE_V2", "1")
    assert pulse_score(stats(extra={"acceleration": 15.0})) == pulse_score(stats(extra={"acceleration": 15.0}), v2=True)
    monkeypatch.setenv("PULSO_FLAG_PULSE_V2", "0")
    assert pulse_score(stats(extra={"acceleration": 15.0})) == pulse_score(stats(extra={"acceleration": 15.0}), v2=False)


def test_v2_acceleration_adds_points_and_breakdown_sums():
    flat, _ = pulse_score(stats(), v2=True)
    rising, bd = pulse_score(stats(extra={"acceleration": 15.0}), v2=True)
    assert rising > flat and any(b["key"] == "acceleration" for b in bd) and sum(b["points"] for b in bd) == rising


def test_v2_falling_activity_gets_no_acceleration_points():
    assert not any(b["key"] == "acceleration" for b in pulse_score(stats(extra={"acceleration": -10.0}), v2=True)[1])


def test_v2_sensor_type_diversity_beats_raw_volume():
    same = pulse_score(stats(source_classes=frozenset({"NEWS_HIGH"})), v2=True)[0]
    diverse = pulse_score(stats(source_classes=frozenset({"NEWS_HIGH", "OFFICIAL", "SOCIAL"})), v2=True)[0]
    assert diverse > same


def test_stats_for_measures_acceleration_from_hour_over_hour():
    assert stats_for([sig(i, 5 + i) for i in range(8)] + [sig(100, 90)], NOW).extra["acceleration"] == 7.0
    assert stats_for([sig(1, 10)] + [sig(100 + i, 70 + i) for i in range(5)], NOW).extra["acceleration"] == -4.0


def test_build_event_without_contradiction_matches_v1_breakdown():
    c = cluster_signals([sig(1, 10), sig(2, 12, source="b")])[0]
    ev = build_event(c, NOW)
    assert not any(b["key"] in ("contradiction", "acceleration", "sensors") for b in ev["score_breakdown"])


def test_contradiction_lowers_confidence_and_is_explained():
    c = cluster_signals([sig(1, 10), sig(2, 12, source="b")])[0]
    plain, disputed = build_event(c, NOW), build_event(c, NOW, contradiction=1.0)
    assert disputed["confidence"] < plain["confidence"]
    assert any(b["key"] == "contradiction" and b["points"] == 0 for b in disputed["score_breakdown"])
    assert sum(b["points"] for b in disputed["score_breakdown"]) == disputed["pulse"]
    assert stats_for([sig(1, 5)], NOW, contradiction=7.0).contradiction == 1.0
    assert confidence(stats(contradiction=1.0)) < confidence(stats())
