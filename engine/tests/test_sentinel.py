from datetime import datetime, timedelta, timezone

from pulso_engine.models import Signal
from pulso_engine.radar import analyze
from pulso_engine.research.sentinel import SentinelConfig, advance, detect_candidates, find_active, should_investigate

NOW = datetime(2026, 10, 4, 6, 20, tzinfo=timezone.utc)  # domingo 03:20 em Brasília
CFG = SentinelConfig()


def sig(i, minutes_ago, source="s1", cls="NEWS_HIGH", cat="WEATHER", state="MG"):
    ts = NOW - timedelta(minutes=minutes_ago)
    return Signal(signal_id=str(i), source_id=source, source_class=cls, timestamp=ts, collected_at=ts, title="t",
                  category=cat, hash=f"h{i}", state=state)


def history(per_hour=4, days=10, cat="WEATHER", scope="BR"):
    rows = []
    end = NOW.replace(minute=0)
    for i in range(1, 24 * days):
        rows.append({"scope": scope, "category": cat, "source_class": "NEWS_HIGH",
                     "hour": (end - timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"), "signals": per_hour, "sources": 2, "duplicates": 0})
    return rows


def burst(n=40):
    return [sig(i, i % 14) for i in range(n)]


def test_normal_day_opens_nothing():
    sigs = [sig(i, i * 10) for i in range(4)]
    out = analyze(sigs, history(), [], NOW)
    assert out["investigations"] == [] and out["triggered"] == []


def test_flood_burst_opens_one_investigation_per_scope():
    out = analyze(burst(), history() + history(scope="UF:MG"), [], NOW)
    inv = out["investigations"]
    assert {i.scope for i in inv} == {"BR", "UF:MG"}
    assert all(i.status == "NEW" and i.initial_anomaly >= 0.65 for i in inv)
    assert any("anomalia" in r for i in inv for r in i.reasons)


def test_no_baseline_means_no_anomaly_trigger():
    c = detect_candidates(burst(), [], NOW)
    assert all(x.score == 0.0 for x in c)
    assert not any("anomalia" in r for x in c for r in should_investigate(x)[1])


def test_official_and_type_diversity_trigger():
    sigs = [sig(1, 5, cls="OFFICIAL", source="inmet")]
    assert should_investigate(detect_candidates(sigs, [], NOW)[0])[0]
    mix = [sig(1, 5, cls="OFFICIAL", source="a"), sig(2, 6, cls="NEWS_HIGH", source="b"), sig(3, 7, cls="SOCIAL", source="c")]
    reasons = should_investigate(detect_candidates(mix, [], NOW)[0])[1]
    assert any("tipos de fonte" in r for r in reasons)


def test_no_duplicate_investigation_and_update_in_place():
    rows = history() + history(scope="UF:MG")
    first = analyze(burst(), rows, [], NOW)["investigations"]
    later = NOW + timedelta(minutes=10)
    second = advance(first, detect_candidates(burst(), rows, later), later)
    assert {i.investigation_id for i in second} <= {i.investigation_id for i in first}
    assert all(i.status == "INVESTIGATING" for i in second)
    assert find_active(first, "UF:MG", "WEATHER", later) is not None
    assert find_active(first, "UF:MG", "TRAFFIC", later) is None


def test_cooldown_resolving_then_closed():
    first = analyze(burst(), history() + history(scope="UF:MG"), [], NOW)["investigations"]
    t1 = NOW + timedelta(minutes=CFG.resolve_after_min)
    r = advance(first, [], t1)
    assert r and all(i.status == "RESOLVING" for i in r)
    t2 = NOW + timedelta(minutes=CFG.resolve_after_min + CFG.close_after_min)
    c = advance(r, [], t2)
    assert c and all(i.status == "CLOSED" for i in c)
    assert advance(c, [], t2 + timedelta(hours=1)) == []  # fechada não muda mais
