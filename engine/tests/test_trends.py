from datetime import datetime, timedelta, timezone

from pulso_engine.intelligence.trends import persistence_min, trend_state, trends, window_metrics
from pulso_engine.models import Signal

NOW = datetime(2026, 10, 3, 15, 0, tzinfo=timezone.utc)


def sig(i, minutes_ago, source="s1", cls="NEWS_HIGH", state=None):
    ts = NOW - timedelta(minutes=minutes_ago)
    return Signal(signal_id=f"{i}", source_id=source, source_class=cls, timestamp=ts, collected_at=ts, title="t", hash=f"h{i}", state=state)


def test_rising_vs_stable_high():
    rising = [sig(i, 5 + i) for i in range(10)] + [sig(100 + i, 65 + i * 5) for i in range(3)]
    stable = [sig(i, 5 + i * 5) for i in range(10)] + [sig(100 + i, 65 + i * 5) for i in range(10)]
    assert trend_state(rising, NOW) == "RISING"
    assert trend_state(stable, NOW) == "STABLE_HIGH"


def test_few_signals_not_asserted():
    assert trend_state([sig(1, 5), sig(2, 70)], NOW) == "INSUFFICIENT"
    assert trend_state([], NOW) == "QUIET"


def test_falling():
    falling = [sig(i, 5 + i * 10) for i in range(2)] + [sig(100 + i, 65 + i * 4) for i in range(12)]
    assert trend_state(falling, NOW) == "FALLING"


def test_window_metrics_fields():
    sigs = [sig(1, 3, "a", "NEWS_HIGH", "MG"), sig(2, 4, "b", "OFFICIAL", "SP"), sig(3, 10, "c")]
    m = window_metrics(sigs, NOW, 5, {"h1": 2})
    assert (m.signal_count, m.source_count, m.source_type_count) == (2, 2, 2)
    assert m.official_confirmation and m.geographic_density == 1.0
    assert m.duplicate_ratio == round(2 / 4, 3)
    assert m.velocity == 24.0  # 2 sinais em 5 min


def test_acceleration_sign():
    sigs = [sig(i, 1 + i) for i in range(6)]  # 6 nos últimos 15 min, 0 nos 15 anteriores
    assert window_metrics(sigs, NOW, 15).acceleration > 0


def test_persistence_and_bundle():
    sigs = [sig(1, 5), sig(2, 125)]
    assert persistence_min(sigs, NOW) == 120.0
    out = trends(sigs, NOW)
    assert len(out["windows"]) == 7 and out["state"] in ("INSUFFICIENT", "QUIET")
