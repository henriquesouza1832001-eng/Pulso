from datetime import datetime, timedelta, timezone

from pulso_engine.intelligence.anomaly_v2 import anomaly_v2, robust_baseline, robust_z
from pulso_engine.models import Signal
from pulso_engine.quality import duplication_probability, geo_quality, signal_quality
from pulso_engine.scoring.confidence_v2 import confidence_v2
from pulso_engine.scoring.national_pulse import national_pulse_v2
from pulso_engine.scoring.severity_v2 import severity_v2
from pulso_engine.baseline import INSUFFICIENT, SeasonalBaseline

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def sig(i, title="Acidente grave na BR-381 em Betim", cls="NEWS_HIGH", source=None, cat="TRAFFIC", state="MG", **kw):
    ts = NOW - timedelta(minutes=i)
    return Signal(signal_id=str(i), source_id=source or f"s{i}", source_class=cls, timestamp=ts, collected_at=ts, title=title,
                  category=cat, hash=f"h{i}", state=state, **kw)


# --- anomalia V2 ---
def test_robust_baseline_ignores_old_spikes():
    med, std = robust_baseline([4, 5, 4, 5, 4, 5, 4, 90])
    assert med == 4.5 and std < 3  # o z clássico seria inflado pelo 90
    assert robust_z(40, 15, []) is None


def test_anomaly_v2_score_and_confidence_are_separate():
    base = SeasonalBaseline(16.8, 4.0, 14, "dow_hour", 14, (14, 18, 17, 15, 19, 17, 16, 18, 17, 16, 15, 17, 18, 16))
    r = anomaly_v2(39, 15, base)
    assert r["status"] == "ANOMALY" and r["score"] >= 0.65 and r["confidence"] == 1.0
    weak = anomaly_v2(2, 15, base)
    assert weak["score"] == 0.0 and weak["status"] == "NORMAL"
    few = SeasonalBaseline(16.8, 4.0, 3, "hour", 3, (14, 18, 17))
    assert anomaly_v2(39, 15, few)["confidence"] < r["confidence"]  # mesma anomalia, base mais fraca = menos confiança


def test_anomaly_v2_without_baseline_claims_nothing():
    r = anomaly_v2(50, 15, INSUFFICIENT)
    assert r["score"] == 0.0 and r["confidence"] == 0.0 and r["status"] == "BASELINE INSUFICIENTE"


# --- confiança V2 ---
def test_copies_do_not_add_confidence():
    copies = [sig(i, source=f"portal{i}") for i in range(1, 11)]
    distinct = [sig(1, "Colisão interdita BR-381 em Betim", source="a"), sig(2, "Capotamento bloqueia rodovia na região de Betim", source="b", cls="NEWS_REGIONAL"),
                sig(3, "Engavetamento complica trânsito na BR 381 perto de Betim", source="c", cls="TRAFFIC_PROVIDER")]
    c_copies, _ = confidence_v2(copies)
    c_distinct, _ = confidence_v2(distinct)
    assert c_distinct > c_copies


def test_confidence_v2_explains_and_sums_to_score():
    score, bd = confidence_v2([sig(1, source="a", cls="OFFICIAL"), sig(2, "Colisão interdita a BR-381 perto de Betim", source="b")], contradiction=0.5)
    assert sum(b["points"] for b in bd) == score
    assert any(b["key"] == "official" for b in bd) and any(b["key"] == "contradiction" and b["points"] < 0 for b in bd)


def test_social_only_capped_and_cap_explained():
    posts = [sig(i, f"Relato diferente número {i} sobre alagamento", cls="SOCIAL", source=f"u{i}") for i in range(1, 30)]
    score, bd = confidence_v2(posts)
    assert score <= 40 and sum(b["points"] for b in bd) == score
    assert confidence_v2([]) == (0, [])


# --- severidade V2 ---
def test_severity_is_impact_not_volume():
    routine = [sig(i, "Trânsito intenso na avenida", source=f"s{i}") for i in range(1, 40)]
    harm = [sig(1, "Desabamento deixa mortos e feridos; hospital sem atendimento em dois bairros")]
    assert severity_v2(routine)["score"] < severity_v2(harm)["score"]
    v = severity_v2(harm)
    assert v["vector"]["physical_harm"] == 1.0 and v["vector"]["infrastructure"] > 0 and v["vector"]["services"] > 0
    assert sum(p["points"] for p in v["points"]) == v["score"]


def test_official_emergency_sets_official_severity():
    s = severity_v2([sig(1, "Aviso", cls="OFFICIAL", cat="EMERGENCY")])
    assert s["vector"]["official_severity"] == 1.0
    assert severity_v2([])["score"] == 0


# --- Pulso nacional V2 ---
def ev(pulse, state, cat="WEATHER"):
    return {"pulse": pulse, "state": state, "category": cat, "alert_level": 3}


def test_distributed_crisis_beats_single_strong_event():
    local = [ev(90, "MG")] + [ev(5, "SP")] * 3
    spread = [ev(60, u, c) for u, c in (("MG", "WEATHER"), ("SP", "TRAFFIC"), ("RJ", "WEATHER"), ("BA", "HEALTH"), ("PE", "WEATHER"), ("RS", "INFRASTRUCTURE"))]
    ls, _ = national_pulse_v2(local)
    ss, bd = national_pulse_v2(spread)
    assert ss > ls and sum(p["points"] for p in bd) == ss
    assert national_pulse_v2([]) == (0, [])


# --- qualidade ---
def test_quality_signals():
    full = sig(5, text="texto", url="https://x", city="Betim", geo_precision="CITY", geo_confidence=70)
    q = signal_quality(full, NOW, {"h5": 3})
    assert q["completeness"] == 1.0 and q["geo_quality"] == 0.7 and q["duplication_probability"] == 0.75 and 0 < q["freshness"] <= 1
    assert geo_quality(sig(1, state=None)) == 0.0
    assert geo_quality(sig(1, state="MG", geo_precision="STATE", geo_confidence=35)) < geo_quality(full)
    assert duplication_probability(full) == 0.0
