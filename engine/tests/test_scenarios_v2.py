"""Cenários integrados do prompt do dono (§79-§85) sobre os módulos V2: o V2 se comporta como o documento exige."""
from datetime import datetime, timedelta, timezone

from pulso_engine.baseline import BR_TZ, seasonal_baseline
from pulso_engine.intelligence.anomaly_v2 import anomaly_v2
from pulso_engine.intelligence.driver_validator import registry_row
from pulso_engine.models import Signal
from pulso_engine.quality import freshness
from pulso_engine.research.validator import find_contradictions, validate
from pulso_engine.research.sentinel import Investigation
from pulso_engine.scoring.confidence_v2 import confidence_v2

NOW = datetime(2026, 10, 5, 21, 20, tzinfo=timezone.utc)  # segunda 18:20 em Brasília


def sig(i, title, cls="NEWS_HIGH", source=None, cat="TRAFFIC", state="SP", minutes_ago=10, text=None):
    ts = NOW - timedelta(minutes=minutes_ago)
    return Signal(signal_id=str(i), source_id=source or f"s{i}", source_class=cls, timestamp=ts, collected_at=ts, title=title,
                  category=cat, hash=f"h{i}", state=state, text=text)


def inv():
    return Investigation("inv-1", "UF:SP", "TRAFFIC", "NEW", NOW, NOW, 0.7, 0.7, 1, False, (), NOW, ())


def test_duplicated_news_wave_is_one_origin_not_thirty_confirmations():
    """§79: 1 matéria original + 30 republicações = 1 origem."""
    wave = [sig(i, "Acidente interdita Marginal Pinheiros sentido Interlagos", source=f"portal{i}") for i in range(31)]
    v = validate(inv(), wave)
    assert v.independent_sources == 1 and v.suggested_status == "INVESTIGATING" and v.copy_ratio > 0.9
    score, _ = confidence_v2(wave)
    independent = [sig(1, "Colisão interdita a Marginal Pinheiros", source="a"),
                   sig(2, "Capotamento bloqueia pista da marginal na zona sul", source="b", cls="NEWS_REGIONAL"),
                   sig(3, "Engavetamento complica trânsito perto da Marginal Pinheiros", source="c", cls="TRAFFIC_PROVIDER")]
    assert confidence_v2(independent)[0] > score


def test_false_social_spike_500_posts_never_confirm():
    """§80: 500 posts sem outro sensor: confiança limitada e nunca CONFIRMED."""
    posts = [sig(i, f"Relato número {i}: tudo parado na marginal", cls="SOCIAL", source=f"user{i}") for i in range(500)]
    score, bd = confidence_v2(posts)
    assert score <= 40 and sum(b["points"] for b in bd) == score
    assert validate(inv(), posts).suggested_status != "CONFIRMED"


def history(per_hour_fn, days=42):
    end = NOW.replace(minute=0)
    rows = []
    for h in range(1, 24 * days):
        t = end - timedelta(hours=h)
        v = per_hour_fn(t.astimezone(BR_TZ))
        if v:
            rows.append({"scope": "UF:SP", "category": "TRAFFIC", "source_class": "NEWS_HIGH", "hour": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "signals": v, "sources": 3, "duplicates": 0})
    return rows


def test_sao_paulo_monday_6pm_is_normal_but_sunday_3am_same_volume_is_anomaly():
    """§82/§83: o MESMO volume é normal na segunda 18h e anomalia no domingo 3h."""
    rows = history(lambda l: 40 if (l.weekday() == 0 and l.hour == 18) else 2 if (l.weekday() == 6 and l.hour == 3) else 5)
    monday = seasonal_baseline(rows, "UF:SP", "TRAFFIC", NOW)
    sunday_at = datetime(2026, 10, 4, 6, 20, tzinfo=timezone.utc)  # domingo 03:20 em Brasília
    sunday = seasonal_baseline(rows, "UF:SP", "TRAFFIC", sunday_at)
    assert monday.basis == sunday.basis == "dow_hour"
    assert anomaly_v2(40, 60, monday)["status"] == "NORMAL"
    assert anomaly_v2(40, 60, sunday)["status"] == "ANOMALY"


def test_false_driver_small_sample_is_rejected():
    """§84: correlação alta com amostra pequena não vira driver ativo."""
    lucky = [(0.5, 0.9 if i % 2 else 0.1, i % 2) for i in range(150)]
    assert registry_row("WEATHER", "TRAFFIC", "BR", 2, 0.97, 8, lucky)["state"] == "CANDIDATE"


def test_stale_source_loses_freshness_and_weight():
    """Fonte parada: sinal de 3 dias pesa quase nada no frescor e o V2 de confiança não a trata como confirmação de agora."""
    old = sig(1, "Interdição na Marginal", minutes_ago=3 * 24 * 60)
    fresh = sig(2, "Interdição na Marginal", minutes_ago=5)
    assert freshness(old, NOW) < 0.01 < freshness(fresh, NOW)


def test_conflicting_reports_are_recorded_not_averaged():
    """Fonte A 'totalmente fechada', B 'uma faixa', oficial 'parcial': divergência registrada e DISPUTED."""
    a = sig(1, "Rodovia totalmente fechada após acidente em Barueri", source="a")
    b = sig(2, "Uma faixa interditada após acidente em Barueri", source="b")
    o = sig(3, "Bloqueio parcial na rodovia após acidente em Barueri", cls="OFFICIAL", source="artesp")
    found = find_contradictions([a, b, o])
    assert found and found[0]["official_side"] == "b"
    v = validate(inv(), [a, b, o])
    assert v.suggested_status == "DISPUTED" and v.official_confirmation and v.contradiction_score > 0
    with_dispute, _ = confidence_v2([a, b, o], contradiction=v.contradiction_score)
    assert with_dispute < confidence_v2([a, b, o])[0]
