from datetime import datetime, timezone

from pulso_engine.intelligence.signatures import best_signature, load_signatures, match_signature, sensor_graph, sensor_of
from pulso_engine.models import Signal

TS = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def sig(source, cls, cat="WEATHER"):
    return Signal(signal_id=source, source_id=source, source_class=cls, timestamp=TS, collected_at=TS, title="t", category=cat, hash=source)


def test_all_fourteen_documented_types_exist_with_three_stages():
    types = load_signatures()
    assert len(types) == 14 and {"FLOOD", "BLACKOUT", "INTERNET_OUTAGE", "AIRPORT_DISRUPTION"} <= set(types)
    assert all(set(t) >= {"category", "leading", "concurrent", "confirming"} for t in types.values())


def test_sensor_of_by_class_and_source():
    assert sensor_of(sig("inmet-avisos", "OFFICIAL")) == "rainfall"
    assert sensor_of(sig("defesa-civil-idap", "OFFICIAL", "EMERGENCY")) == "civil_defense"
    assert sensor_of(sig("bluesky-clima", "SOCIAL")) == "social"
    assert sensor_of(sig("g1", "NEWS_HIGH")) == "news"
    assert sensor_of(sig("usgs-terremotos", "OFFICIAL", "EMERGENCY")) == "seismic"


def test_flood_signature_order_and_lead():
    obs = [("rainfall", 0.0), ("traffic", 1000.0), ("social", 1500.0), ("civil_defense", 3000.0), ("news", 3600.0)]
    m = match_signature("FLOOD", obs)
    assert m["leading_before_confirming"] is True and m["lead_seconds"] == 3000.0
    assert m["missing"]["leading"] == ["radar", "river_level"] and m["coverage"] > 0.5


def test_news_before_sensors_is_not_a_lead():
    m = match_signature("FLOOD", [("news", 0.0), ("rainfall", 600.0)])
    assert m["leading_before_confirming"] is False and m["lead_seconds"] is None


def test_nothing_observed_means_no_claim():
    assert best_signature([]) is None
    assert match_signature("FLOOD", [])["leading_before_confirming"] is None


def test_best_signature_respects_category_and_graph_has_correlation_edges():
    best = best_signature([("rainfall", 0.0), ("radar", 10.0), ("civil_defense", 900.0)], "WEATHER")
    assert best["event_type"] in ("FLOOD", "STORM", "LANDSLIDE")
    g = sensor_graph()
    assert g["rainfall"]["traffic"] >= 1 and "civil_defense" in g["river_level"]
