from datetime import datetime, timedelta, timezone

from pulso_engine.forecast_v2_features import build_snapshot
from pulso_engine.forecast_v2_model import (GLOBAL_RATE, MIN_CALIBRATION_SAMPLES, Prior, abstention, apply_calibrator, fit_platt, forecast,
                                           hierarchical_prior)
from pulso_engine.models import Signal

CUTOFF = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)


def sig(i, minutes_before, source="g1", cls="NEWS_HIGH", cat="WEATHER", state="MG", title="Chuva forte alaga ruas"):
    ts = CUTOFF - timedelta(minutes=minutes_before)
    return Signal(signal_id=str(i), source_id=source, source_class=cls, timestamp=ts, collected_at=ts, title=title, category=cat, hash=f"h{i}", state=state)


def history(per_hour=3, days=10):
    end = CUTOFF.replace(minute=0)
    return [{"scope": "UF:MG", "category": "WEATHER", "source_class": "NEWS_HIGH", "hour": (end - timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "signals": per_hour, "sources": 2, "duplicates": 0} for h in range(1, 24 * days)]


def strong():
    return ([sig(i, 1 + i % 12, source=f"s{i % 7}", title=f"Alagamento {i} em Venda Nova") for i in range(40)]
            + [sig(100, 10, "inmet-avisos", "OFFICIAL"), sig(101, 8, "defesa-civil-idap", "OFFICIAL", title="Defesa Civil alerta"),
               sig(102, 5, "bluesky-clima", "SOCIAL")])


PRIOR = Prior(0.05, "nacional/categoria", 120)


def test_hierarchical_prior_falls_back_and_records_the_level():
    levels = [("cidade/categoria/hora", [1, 0, 0]), ("estado/categoria/hora", [0] * 40), ("nacional/categoria", [0] * 500)]
    p = hierarchical_prior(levels)
    assert p.level == "estado/categoria/hora" and p.samples == 40 and p.rate < 0.05
    none = hierarchical_prior([("cidade", [1, 1])])
    assert none.level == "global" and none.rate == GLOBAL_RATE and none.samples == 0


def test_rare_event_is_not_high_probability_just_because_of_a_few_signals():
    weak = build_snapshot([sig(1, 5), sig(2, 6, source="g2")], CUTOFF, "UF:MG", "WEATHER", history())
    r = forecast(weak, Prior(0.01, "global", 500))
    assert r["status"] == "UNCALIBRATED_EXPERIMENTAL" and r["probability"] < 0.2


def test_strong_independent_evidence_raises_probability_and_explains_why():
    s = build_snapshot(strong(), CUTOFF, "UF:MG", "WEATHER", history(), "FLOOD")
    r = forecast(s, PRIOR)
    weak = forecast(build_snapshot([sig(1, 5)], CUTOFF, "UF:MG", "WEATHER", history()), PRIOR)
    assert r["probability"] > weak["probability"] and 0 < r["probability"] < 1
    assert r["contributions"] and r["contributions"][0]["log_odds"] >= r["contributions"][-1]["log_odds"]
    assert r["raw_probability"] == r["probability"] and r["calibrated_probability"] is None  # sem calibrador: bruto separado
    assert r["interval_low"] <= r["probability"] <= r["interval_high"]


def test_discordance_raises_uncertainty_not_probability():
    social = [sig(i, 3, source=f"u{i}", cls="SOCIAL", title=f"relato {i}") for i in range(1, 50)]
    mixed = social[:3] + [sig(90, 5, "inmet-avisos", "OFFICIAL"), sig(91, 5, "g1")]
    a = forecast(build_snapshot(social, CUTOFF, "UF:MG", "WEATHER", history()), PRIOR)
    b = forecast(build_snapshot(mixed, CUTOFF, "UF:MG", "WEATHER", history()), PRIOR)
    assert a["uncertainty"] > b["uncertainty"] and any("discord" in r for r in a["uncertainty_reasons"])
    assert a["probability"] < b["probability"]  # 49 posts sem outro sensor não valem mais que oficial + imprensa


def test_abstains_instead_of_inventing_a_probability():
    empty = forecast(build_snapshot([], CUTOFF, "UF:MG", "WEATHER", None, "FLOOD"), PRIOR)
    assert empty["status"] == "INSUFFICIENT_DATA" and empty["probability"] is None and empty["abstention_reason"]
    low_cov = build_snapshot([sig(1, 5, "g1")], CUTOFF, "UF:MG", "WEATHER", history(), "BLACKOUT")  # sensores esperados quase todos ausentes
    assert abstention(low_cov) is not None and forecast(low_cov, PRIOR)["status"] == "INSUFFICIENT_DATA"
    assert "missing_evidence_priorities" in empty


def test_calibrator_needs_enough_samples_and_never_uses_future():
    few = [(0.3, 0)] * 50 + [(0.7, 1)] * 50
    assert fit_platt(few, "2026-10-01T00:00:00Z", "cal-1") is None  # amostra insuficiente: não calibra
    assert fit_platt([(0.5, 1)] * 300, "2026-10-01T00:00:00Z", "cal-1") is None  # um só desfecho: sem informação
    pairs = [(0.9, 1 if i % 10 else 0) for i in range(150)] + [(0.1, 1 if i % 10 == 0 else 0) for i in range(150)]
    assert len(pairs) >= MIN_CALIBRATION_SAMPLES
    cal = fit_platt(pairs, "2026-10-01T00:00:00Z", "cal-1")
    assert cal and cal.samples == 300 and cal.fit_until == "2026-10-01T00:00:00Z" and cal.version == "cal-1"
    assert 0.8 < apply_calibrator(0.9, cal) < 0.95 and 0.05 < apply_calibrator(0.1, cal) < 0.2  # observado ~0,9 e ~0,1
    assert apply_calibrator(0.5, None) is None


def test_calibrated_forecast_keeps_raw_and_marks_status():
    pairs = [(0.9, 1 if i % 10 else 0) for i in range(150)] + [(0.1, 1 if i % 10 == 0 else 0) for i in range(150)]
    cal = fit_platt(pairs, "2026-10-01T00:00:00Z", "cal-1")
    s = build_snapshot(strong(), CUTOFF, "UF:MG", "WEATHER", history(), "FLOOD")
    r = forecast(s, PRIOR, cal)
    assert r["status"] == "OK_CALIBRATED" and r["calibrator_version"] == "cal-1"
    assert r["raw_probability"] is not None and r["calibrated_probability"] == r["probability"]
    assert forecast(s, PRIOR) == forecast(s, PRIOR)  # determinístico


def test_probability_is_never_zero_or_one():
    s = build_snapshot(strong(), CUTOFF, "UF:MG", "WEATHER", history(), "FLOOD")
    for prior in (Prior(0.9999, "x", 999), Prior(0.0001, "x", 999)):
        p = forecast(s, prior)["probability"]
        assert 0 < p < 1
