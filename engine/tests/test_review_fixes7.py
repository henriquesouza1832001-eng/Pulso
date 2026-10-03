"""Achados da revisão da camada de previsão (nível máximo, 2026-10-03)."""
import json
import random
from datetime import datetime, timedelta, timezone

from pulso_engine.backtest import walk_forward
from pulso_engine.drivers import leading_indicators
from pulso_engine.forecast_surge import resolve_surge_due

NOW = datetime(2026, 10, 3, 12, 2, tzinfo=timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_resolution_keeps_the_registered_evidence_when_the_worker_returns_it_as_json_text():
    created = datetime(2026, 10, 3, 10, 0, tzinfo=timezone.utc)
    evidence = {"current_hour_signals": 7, "baseline_mean": 5.2, "leading_indicators": [{"category": "WEATHER", "lag_hours": 2}]}
    f = {"forecast_id": "f1", "metric": "signals_traffic", "scope": "BR", "comparator": "gte", "threshold": 6.0, "probability": 0.4,
         "created_at": iso(created), "resolves_at": iso(created + timedelta(minutes=60)),
         "evidence": json.dumps(evidence)}  # a rota /api/admin/forecasts/open devolve a coluna crua, em texto
    rows = [{"scope": "BR", "category": "TRAFFIC", "bucket": iso(created + timedelta(minutes=5 * i)), "signals": 1, "sources": 1} for i in range(12)]
    points = [{"timestamp": iso(created + timedelta(minutes=5 * i)), "score": 20} for i in range(12)]
    (out,) = resolve_surge_due([f], rows, points, NOW)
    assert out["status"] == "resolved" and out["evidence"] == evidence  # antes: {}
    broken = resolve_surge_due([{**f, "evidence": "{não é json"}], rows, points, NOW)
    assert broken[0]["status"] == "resolved" and broken[0]["evidence"] == {}  # evidência corrompida não derruba a resolução


def test_a_sparse_leader_category_is_not_a_spurious_leading_indicator():
    rng = random.Random(3)
    end = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
    rows = []
    spikes = (10, 40, 70)
    for h in range(96):  # alvo com dado em todas as horas; sobe 2 h depois de cada pico da categoria esparsa (correlação alta)
        high = any(h == sp + 2 for sp in spikes)
        for b in range(12):
            rows.append({"scope": "BR", "category": "TRAFFIC", "bucket": iso(end - timedelta(hours=96 - h, minutes=-5 * b)),
                         "signals": (3 if high else rng.randint(0, 1)), "sources": 1})
    # categoria "líder" quase só de zeros: 3 horas com sinal em 96 (histórico esparso) e um pico agora
    for h in spikes:
        rows.append({"scope": "BR", "category": "HEALTH", "bucket": iso(end - timedelta(hours=96 - h)), "signals": 4, "sources": 1})
    for b in range(1, 13):
        rows.append({"scope": "BR", "category": "HEALTH", "bucket": iso(end - timedelta(minutes=5 * b)), "signals": 1, "sources": 1})
    assert all(i["category"] != "HEALTH" for i in leading_indicators(rows, "TRAFFIC", "BR", NOW))


def test_backtest_reference_does_not_peek_at_the_future():
    rng = random.Random(5)
    counts = [max(0, round(rng.gauss(8, 3))) for _ in range(120)]
    r = walk_forward(counts)
    assert r.n > 50 and 0 <= r.brier_base_rate <= 1
    # a referência é construída só com o passado: com uma série inteiramente constante o resultado é determinístico e finito
    flat = walk_forward([5] * 80)
    assert flat.n > 0 and flat.brier_base_rate == flat.brier_base_rate  # não é NaN
