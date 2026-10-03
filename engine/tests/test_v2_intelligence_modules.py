from datetime import datetime, timedelta, timezone

from pulso_engine.intelligence.event_escalation import build_history, p_escalation
from pulso_engine.intelligence.event_fingerprint import fingerprint, same_story
from pulso_engine.intelligence.sensor_reliability import NEUTRAL, summarize, weight_for
from pulso_engine.models import Signal

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def sig(i, title, minutes_ago=10, cat="TRAFFIC", state="MG", city="Betim", source=None):
    ts = NOW - timedelta(minutes=minutes_ago)
    return Signal(signal_id=str(i), source_id=source or f"s{i}", source_class="NEWS_HIGH", timestamp=ts, collected_at=ts, title=title,
                  category=cat, hash=f"h{i}", state=state, city=city)


def test_same_story_with_different_titles_and_stable_key():
    a = fingerprint([sig(1, "Acidente fecha BR-381 em Betim", 30), sig(2, "Batida na BR-381 em Betim deixa feridos", 25)])
    b = fingerprint([sig(3, "Colisão interdita a BR-381 perto de Betim", 15), sig(4, "Betim: BR-381 segue bloqueada", 10)])
    assert same_story(a, b) and a.key.startswith("fp-")
    assert fingerprint([sig(1, "Acidente fecha BR-381 em Betim", 30), sig(2, "Batida na BR-381 em Betim deixa feridos", 25)]).key == a.key


def test_not_same_story_when_place_category_time_or_entities_differ():
    base = fingerprint([sig(1, "Acidente fecha BR-381 em Betim", 30)])
    assert not same_story(base, fingerprint([sig(2, "Acidente fecha BR-381 em Betim", 30, state="SP", city="Campinas")]))
    assert not same_story(base, fingerprint([sig(3, "Acidente fecha BR-381 em Betim", 30, cat="SECURITY")]))
    assert not same_story(base, fingerprint([sig(4, "Acidente fecha BR-381 em Betim", 30 + 10 * 60)]))
    assert not same_story(base, fingerprint([sig(5, "Obra interdita avenida central em Betim", 20)]))


def test_escalation_requires_samples_and_is_experimental():
    few = build_history([{"category": "WEATHER", "level_at_t": 2, "max_level_by_horizon": 3}] * 5)
    r = p_escalation(few, "WEATHER", 2)
    assert r["status"] == "INSUFFICIENT_DATA" and r["probability"] is None and r["label"] == "EXPERIMENTAL"
    hist = build_history([{"category": "WEATHER", "level_at_t": 2, "max_level_by_horizon": 3 if i % 4 == 0 else 2} for i in range(80)])
    ok = p_escalation(hist, "WEATHER", 2)
    assert ok["status"] == "OK" and 0 < ok["interval_low"] <= ok["probability"] <= ok["interval_high"] < 1
    assert abs(ok["probability"] - 0.25) < 0.05
    assert p_escalation(hist, "WEATHER", 5)["status"] == "NOT_APPLICABLE"
    assert p_escalation(hist, "TRAFFIC", 2)["status"] == "INSUFFICIENT_DATA"


def obs(source, n, hits, event="FLOOD", geo="UF:MG", lead=20.0):
    return [{"source_id": source, "event_type": event, "geography": geo, "confirmed": i < hits, "lead_minutes": lead if i < hits else None,
             "available": True} for i in range(n)]


def test_wilson_lower_bound_penalizes_small_perfect_record():
    s = summarize(obs("tiny", 3, 3) + obs("big", 100, 90))
    assert s[("tiny", "FLOOD", "UF:MG")]["status"] == "INSUFFICIENT_DATA" and weight_for(s, "tiny", "FLOOD", "UF:MG") == NEUTRAL
    assert weight_for(s, "big", "FLOOD", "UF:MG") > 0.8
    assert s[("big", "FLOOD", "UF:MG")]["median_lead_min"] == 20.0
    assert weight_for(s, "unknown", "FLOOD", "UF:MG") == NEUTRAL
    assert weight_for(summarize(obs("poor", 100, 20)), "poor", "FLOOD", "UF:MG") < 0.3
