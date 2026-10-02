from pulso_engine.models import EventStats
from pulso_engine.scoring.confidence import SOCIAL_ONLY_CAP, confidence
from pulso_engine.scoring.pulse import alert_level, decay, pulse_score


def stats(**kw) -> EventStats:
    base = dict(
        severity=50, signal_count=5, independent_sources=1, source_classes=frozenset({"NEWS_HIGH"}),
        newest_age_min=5, persistence_min=10, velocity_per_hour=5,
    )
    base.update(kw)
    return EventStats(**base)


def test_social_only_is_capped():
    s = stats(independent_sources=30, source_classes=frozenset({"SOCIAL"}), official_confirmation=True)
    assert confidence(s) <= SOCIAL_ONLY_CAP


def test_official_plus_diverse_sources_raises_confidence():
    weak = stats()
    strong = stats(independent_sources=4, source_classes=frozenset({"OFFICIAL", "NEWS_HIGH", "TRAFFIC_PROVIDER"}),
                   official_confirmation=True, geo_consistency=1, temporal_consistency=1)
    assert confidence(strong) > 85 > confidence(weak)


def test_severity_and_confidence_are_independent():
    small_sure = stats(severity=35, independent_sources=4, official_confirmation=True,
                       source_classes=frozenset({"OFFICIAL", "NEWS_HIGH", "TRAFFIC_PROVIDER"}))
    big_unsure = stats(severity=92, source_classes=frozenset({"SOCIAL"}))
    assert confidence(small_sure) > 80
    assert confidence(big_unsure) <= SOCIAL_ONLY_CAP


def test_breakdown_sums_to_score_and_is_sorted():
    score, breakdown = pulse_score(stats(independent_sources=5, anomaly=0.8, velocity_per_hour=20))
    assert score == sum(b["points"] for b in breakdown)
    pts = [b["points"] for b in breakdown]
    assert pts == sorted(pts, reverse=True)
    assert 0 <= score <= 100


def test_decay_halves_at_half_life():
    assert abs(decay(90) - 0.5) < 1e-9
    assert decay(0) == 1.0 and decay(600) < 0.02


def test_old_event_scores_lower_than_fresh():
    fresh, _ = pulse_score(stats(newest_age_min=2))
    old, _ = pulse_score(stats(newest_age_min=600))
    assert old < fresh


def test_level5_requires_official_and_multiple_sources():
    s = stats(independent_sources=5, official_confirmation=True,
              source_classes=frozenset({"OFFICIAL", "NEWS_HIGH"}))
    assert alert_level(95, 90, s) == 5
    assert alert_level(95, 90, stats(independent_sources=5, official_confirmation=False)) == 4
    assert alert_level(95, 90, stats(independent_sources=2, official_confirmation=True)) == 4


def test_social_only_never_exceeds_level3():
    s = stats(independent_sources=50, source_classes=frozenset({"SOCIAL"}), official_confirmation=True)
    assert alert_level(100, 100, s) <= 3
