from datetime import datetime, timedelta, timezone

from pulso_engine.source_freshness import (EMPTY, FRESH, QUIET, STALE, UNKNOWN, SourceReading, assess, coverage, freshness_percentiles,
                                           next_state_transition, stale_after_min)

NOW = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)
SRC = {"id": "g1", "source_class": "NEWS_HIGH"}  # limite padrão 360 min


def reading(transport="ONLINE", ages=(10,), hashes=None, parse_ok=True, sid="g1"):
    hs = tuple(hashes if hashes is not None else (f"h{i}" for i in range(len(ages))))
    return SourceReading(sid, transport, parse_ok, hs, tuple(NOW - timedelta(minutes=a) for a in ages))


def state(r, src=SRC, known=frozenset(), prev=None):
    return assess(src, r, NOW, known, prev)


def test_http_200_with_recent_items_is_fresh():
    a = state(reading(ages=(5, 40)))
    assert a["freshness"]["state"] == FRESH and a["quality"]["new_records"] == 2


def test_200_with_old_timestamp_is_stale_not_fresh():
    a = state(reading(ages=(2000, 3000)))
    assert a["transport"] == "ONLINE" and a["freshness"]["state"] == STALE and "2000" in a["freshness"]["reason"]


def test_200_with_repeated_content_is_stale_when_newest_is_old():
    r = reading(ages=(2000,), hashes=["h0"])
    a = state(r, known={"h0"}, prev=NOW - timedelta(hours=40))
    assert a["freshness"]["state"] == STALE and "conteúdo repetido" in a["freshness"]["reason"]
    assert a["quality"]["new_records"] == 0 and a["freshness"]["last_content_advance"] == (NOW - timedelta(hours=40)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_repeated_but_recent_content_is_still_fresh():
    a = state(reading(ages=(20,), hashes=["h0"]), known={"h0"})  # nada novo, mas o último item é de 20 min
    assert a["freshness"]["state"] == FRESH and a["quality"]["new_records"] == 0


def test_empty_is_not_normal_but_quiet_threshold_source_is():
    assert state(reading(ages=()))["freshness"]["state"] == EMPTY
    q = state(reading(ages=()), {**SRC, "quiet_ok": True})
    assert q["freshness"]["state"] == QUIET  # silêncio legítimo: nem falha, nem "fresco"


def test_transport_failure_is_unknown_never_zero_or_stale():
    for t in ("OFFLINE", "RATE_LIMITED", "AUTH_ERROR"):
        a = state(reading(transport=t, ages=()))
        assert a["freshness"]["state"] == UNKNOWN and a["freshness"]["newest_item_age_min"] is None
    assert state(reading(parse_ok=False, ages=(5,)))["freshness"]["state"] == UNKNOWN  # parse quebrado não vira dado


def test_degraded_transport_still_judges_the_data_it_got():
    assert state(reading(transport="DEGRADED", ages=(5,)))["freshness"]["state"] == FRESH
    assert state(reading(transport="DEGRADED", ages=()))["freshness"]["state"] == EMPTY  # "feed sem itens válidos" não é "normal"


def test_items_without_dates_cannot_be_verified():
    r = SourceReading("g1", "ONLINE", True, ("h0",), (None,))
    assert state(r)["freshness"]["state"] == UNKNOWN


def test_fresh_to_stale_to_fresh_and_offline_recovery_transitions():
    seq = [reading(ages=(10,)), reading(ages=(700,), hashes=["h0"]), reading(transport="OFFLINE", ages=()), reading(ages=(5,), hashes=["n1"])]
    states = [state(r, known={"h0"})["freshness"]["state"] for r in seq]
    assert states == [FRESH, STALE, UNKNOWN, FRESH]
    assert [next_state_transition(a, b) for a, b in zip([None, *states], states)] == [None, "FRESH->STALE", "STALE->UNKNOWN", "UNKNOWN->FRESH"]
    assert next_state_transition("FRESH", "STALE") == "FRESH->STALE" and next_state_transition("FRESH", "FRESH") is None


def test_duplicate_records_are_counted_and_per_source_threshold_applies():
    a = state(reading(ages=(5, 6, 7), hashes=["a", "a", "b"]))
    assert a["quality"] == {"parse_ok": True, "records": 3, "new_records": 2, "duplicate_records": 1}
    assert stale_after_min({"source_class": "OFFICIAL"}) == 1440 and stale_after_min({"stale_after_min": 30}) == 30
    assert state(reading(ages=(100,)), {**SRC, "stale_after_min": 60})["freshness"]["state"] == STALE


def test_coverage_counts_unknown_as_lost_coverage_and_quiet_as_neutral():
    items = [state(reading(ages=(5,), sid="a")), state(reading(ages=(900,), sid="b")), state(reading(transport="OFFLINE", ages=(), sid="c")),
             state(reading(ages=(), sid="d"), {**SRC, "quiet_ok": True})]
    cov = coverage(items, {"a": "news", "b": "news", "c": "news", "d": "official"})
    assert cov["news"] == {"FRESH": 1, "STALE": 1, "EMPTY": 0, "QUIET": 0, "UNKNOWN": 1, "sources": 3, "ready_ratio": 0.333}
    assert cov["official"]["ready_ratio"] is None and cov["official"]["QUIET"] == 1


def test_freshness_percentiles():
    items = [state(reading(ages=(a,), sid=f"s{a}")) for a in (10, 20, 30, 40, 1000)]
    p = freshness_percentiles(items)
    assert p == {"n": 5, "p50": 30.0, "p95": 1000.0, "max": 1000.0}
    assert freshness_percentiles([state(reading(ages=()))]) == {"n": 0, "p50": None, "p95": None, "max": None}
