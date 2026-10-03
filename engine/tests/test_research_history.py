from datetime import datetime, timedelta, timezone

from pulso_engine.models import Signal
from pulso_engine.research.history import build_observations

NOW = datetime(2026, 10, 3, 15, 20, tzinfo=timezone.utc)


def sig(h, ts, source="s1", cls="NEWS_HIGH", cat="WEATHER", state=None):
    return Signal(signal_id=h, source_id=source, source_class=cls, timestamp=ts, collected_at=ts,
                  title=h, category=cat, hash=h, state=state)


def test_current_hour_never_emitted():
    assert build_observations([sig("a", NOW - timedelta(minutes=10))], {}, NOW) == []


def test_closed_hour_counted_once_per_scope():
    ts = datetime(2026, 10, 3, 14, 30, tzinfo=timezone.utc)
    obs = build_observations([sig("a", ts, state="MG"), sig("b", ts, source="s2", state="MG")], {}, NOW)
    assert {(o["scope"], o["signals"], o["sources"]) for o in obs} == {("BR", 2, 2), ("UF:MG", 2, 2)}
    assert all(o["hour"] == "2026-10-03T14:00:00Z" for o in obs)


def test_scope_uf_only_with_state():
    ts = datetime(2026, 10, 3, 14, 30, tzinfo=timezone.utc)
    assert [o["scope"] for o in build_observations([sig("a", ts)], {}, NOW)] == ["BR"]


def test_other_excluded():
    ts = datetime(2026, 10, 3, 14, 30, tzinfo=timezone.utc)
    assert build_observations([sig("a", ts, cat="OTHER")], {}, NOW) == []


def test_duplicates_attributed_to_surviving_signal():
    ts = datetime(2026, 10, 3, 14, 30, tzinfo=timezone.utc)
    obs = build_observations([sig("a", ts)], {"a": 3, "zzz": 9}, NOW)
    assert obs[0]["duplicates"] == 3


def test_source_class_splits_cells_and_output_is_idempotent():
    ts = datetime(2026, 10, 3, 14, 30, tzinfo=timezone.utc)
    sigs = [sig("a", ts), sig("b", ts, cls="OFFICIAL", source="inmet")]
    first = build_observations(sigs, {}, NOW)
    assert len(first) == 2
    assert build_observations(list(reversed(sigs)), {}, NOW) == first


def test_late_arrival_corrects_previous_hour():
    ts = datetime(2026, 10, 3, 14, 50, tzinfo=timezone.utc)
    before = build_observations([sig("a", ts)], {}, NOW)
    after = build_observations([sig("a", ts), sig("b", ts, source="s2")], {}, NOW)
    assert before[0]["signals"] == 1 and after[0]["signals"] == 2


def test_seven_days_row_count_within_ceiling():
    sigs = [sig(f"h{i}", NOW - timedelta(hours=i + 1), state="SP") for i in range(168)]
    assert len(build_observations(sigs, {}, NOW)) <= 168 * 2
