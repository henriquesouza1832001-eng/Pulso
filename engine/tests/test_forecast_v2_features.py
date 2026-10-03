from datetime import datetime, timedelta, timezone

from pulso_engine.forecast_v2_features import (MISSING, NOT_APPLICABLE, STALE, UNAVAILABLE, VALUE, VALUE_ZERO, build_snapshot,
                                               family_agreement, sensor_coverage, visible_signals)
from pulso_engine.models import Signal

CUTOFF = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)


def sig(i, minutes_before, source="g1", cls="NEWS_HIGH", cat="WEATHER", state="MG", title="Chuva forte alaga ruas em Belo Horizonte", collected_delay=1):
    ts = CUTOFF - timedelta(minutes=minutes_before)
    return Signal(signal_id=str(i), source_id=source, source_class=cls, timestamp=ts, collected_at=ts + timedelta(minutes=collected_delay),
                  title=title, category=cat, hash=f"h{i}", state=state)


def history(per_hour=3, days=10):
    end = CUTOFF.replace(minute=0)
    return [{"scope": "UF:MG", "category": "WEATHER", "source_class": "NEWS_HIGH", "hour": (end - timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "signals": per_hour, "sources": 2, "duplicates": 0} for h in range(1, 24 * days)]


def test_p0_future_and_late_collected_signals_are_invisible():
    ok = sig(1, 10)
    future = sig(2, -5)  # publicado DEPOIS do cutoff
    late = sig(3, 3, collected_delay=10)  # publicado antes, mas só coletado depois do cutoff
    seen, excluded = visible_signals([ok, future, late], CUTOFF)
    assert seen == [ok] and excluded == 2
    snap = build_snapshot([ok, future, late], CUTOFF, "UF:MG", "WEATHER")
    assert snap.excluded_future == 2 and snap.features["signals_60m"].value == 1.0


def test_p0_adding_future_data_does_not_change_the_snapshot():
    base = [sig(1, 10), sig(2, 20, source="g2")]
    future = [sig(9, -30), sig(10, -1, source="g3")]
    a = build_snapshot(base, CUTOFF, "UF:MG", "WEATHER", history())
    b = build_snapshot(base + future, CUTOFF, "UF:MG", "WEATHER", history())
    assert {k: f.as_dict() for k, f in a.features.items()} == {k: f.as_dict() for k, f in b.features.items()}
    assert a.coverage == b.coverage and a.agreement == b.agreement  # só excluded_future difere (e é declarado)


def test_p1_snapshot_is_deterministic_and_versioned():
    sigs = [sig(1, 10), sig(2, 20, source="g2")]
    a, b = build_snapshot(sigs, CUTOFF, "UF:MG", "WEATHER", history()), build_snapshot(list(reversed(sigs)), CUTOFF, "UF:MG", "WEATHER", history())
    assert a.hash == b.hash and a.feature_version == "1" and a.data_cutoff == "2026-10-04T15:00:00Z"
    assert build_snapshot(sigs, CUTOFF + timedelta(minutes=5), "UF:MG", "WEATHER", history()).hash != a.hash


def test_p2_absence_is_never_a_silent_zero():
    empty = build_snapshot([], CUTOFF, "UF:MG", "WEATHER")
    assert empty.features["signals_15m"].state == UNAVAILABLE and empty.features["signals_15m"].value is None
    assert empty.features["anomaly_15m"].state == MISSING and empty.features["persistence_min"].state == MISSING
    quiet = build_snapshot([sig(1, 200, cat="TRAFFIC")], CUTOFF, "UF:MG", "WEATHER")  # há dados, mas nenhum do tema agora
    assert quiet.features["signals_15m"].state == VALUE_ZERO and quiet.features["signals_15m"].value == 0.0
    assert build_snapshot([sig(1, 5)], CUTOFF, "UF:MG", "WEATHER").features["anomaly_15m"].state == MISSING  # sem baseline: não é 0
    assert build_snapshot([sig(1, 5)], CUTOFF, "UF:MG", "WEATHER", history()).features["anomaly_15m"].state in (VALUE, VALUE_ZERO)


def test_p2_stale_evidence_is_flagged():
    old = build_snapshot([sig(1, 300)], CUTOFF, "UF:MG", "WEATHER")
    assert old.features["evidence_age_min"].state == STALE and old.features["evidence_age_min"].value == 300.0


def test_p3_coverage_expected_available_stale_missing():
    sigs = [sig(1, 10, "inmet-avisos", "OFFICIAL"), sig(2, 200, "defesa-civil-idap", "OFFICIAL", title="Defesa Civil alerta"),
            sig(3, 5, "bluesky-clima", "SOCIAL"), sig(4, 5, "g1", "NEWS_HIGH")]
    c = sensor_coverage(sigs, CUTOFF, "FLOOD")
    assert "rainfall" in c["available"] and "social" in c["available"] and "news" in c["available"]
    assert "civil_defense" in c["stale"] and "radar" in c["missing"] and "river_level" in c["missing"]
    assert c["ratio"] == round(len(c["available"]) / len(c["expected"]), 3)
    assert sensor_coverage(sigs, CUTOFF, None)["status"] == NOT_APPLICABLE


def test_p4_hundred_republications_are_one_origin():
    wave = [sig(i, 5 + i % 20, source=f"portal{i}", title="Chuva forte alaga ruas em Belo Horizonte hoje") for i in range(1, 31)]
    f = build_snapshot(wave, CUTOFF, "UF:MG", "WEATHER").features
    assert f["independent_origins_60m"].value == 1.0 and f["copy_ratio_60m"].value > 0.9


def test_p5_family_agreement_and_social_only_discordance():
    social = [sig(i, 5, source=f"u{i}", cls="SOCIAL", title=f"relato {i} de alagamento") for i in range(1, 40)]
    a = family_agreement(social, CUTOFF)
    assert a["discordant"] and a["uncertainty_hint"] == "SOCIAL_ONLY" and not a["concordant"]
    mixed = social[:3] + [sig(90, 5, "inmet-avisos", "OFFICIAL"), sig(91, 5, "g1", "NEWS_HIGH")]
    b = family_agreement(mixed, CUTOFF)
    assert b["concordant"] and not b["discordant"] and {"physical", "social", "news"} <= set(b["active_families"])
