from datetime import datetime, timedelta, timezone

from pulso_engine.baseline import BR_TZ
from pulso_engine.forecast import make_nowcasts, resolve_due
from pulso_engine.forecast_v2 import MIN_PAIRS, annotate_shadow, hour_deltas, shadow_rows, v2_probability
from pulso_engine.validation.shadow_compare import promotion_gate

NOW = datetime(2026, 10, 4, 21, 0, tzinfo=timezone.utc)  # 18:00 em Brasília


def pts(days=6, step=10):
    """Pulso com ciclo diário: sobe de 10 a 40 entre 17h e 19h locais; no resto fica em 10."""
    out, t = [], NOW - timedelta(days=days)
    while t <= NOW:
        h = t.astimezone(BR_TZ).hour
        out.append({"timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "score": 40 if h in (18, 19) else 10})
        t += timedelta(minutes=step)
    return out


def test_hour_deltas_only_use_nearby_local_hours():
    d = hour_deltas(pts(), NOW)
    assert len(d) >= MIN_PAIRS
    deltas_all = hour_deltas(pts(), NOW.replace(hour=6))  # 03h local: ciclo plano
    assert max(abs(x) for x in deltas_all) <= 30


def test_v2_abstains_without_enough_history():
    assert v2_probability(pts(days=1)[:30], NOW, 10.0, 15.0) is None
    assert v2_probability([], NOW, 10.0, 15.0) is None


def test_v2_sees_daily_cycle_that_v1_averages_away():
    points = pts()
    cur = 10.0  # 18h local: o V1 mistura todas as horas; o V2 sabe que 17h-19h costuma subir
    v1 = make_nowcasts(points[:-1] + [{"timestamp": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "score": 10}], NOW)
    assert v1  # V1 prevê (histórico suficiente)
    v2 = v2_probability(points, NOW, cur, 30.0)
    v1_p = next(f["probability"] for f in v1 if f["threshold"] >= 30) if any(f["threshold"] >= 30 for f in v1) else None
    assert v2 is not None and 0 < v2["probability"] < 1
    if v1_p is not None:
        assert v2["probability"] != v1_p


def make_forecast(**kw):
    base = {"forecast_id": "fc-1", "kind": "NOWCAST", "metric": "pulse", "scope": "BR", "threshold": 30.0, "comparator": "gte",
            "method": "pulse_empirical_delta", "method_version": "1", "probability": 0.3, "status": "open",
            "evidence": {"current_score": 10.0}, "resolves_at": (NOW + timedelta(minutes=60)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    base.update(kw)
    return base


def test_annotate_only_open_pulse_nowcasts_and_leaves_v1_untouched():
    f = make_forecast()
    out = annotate_shadow([f, make_forecast(forecast_id="x", metric="signals_traffic"), make_forecast(forecast_id="y", status="resolved")],
                          {"BR": pts()}, NOW)
    assert out[0]["evidence"]["shadow_v2"]["method"] == "pulse_hour_conditioned"
    assert {k: v for k, v in out[0].items() if k != "evidence"} == {k: v for k, v in f.items() if k != "evidence"}  # V1 idêntico
    assert out[0]["evidence"]["current_score"] == 10.0
    assert "shadow_v2" not in out[1]["evidence"] and "shadow_v2" not in out[2]["evidence"]
    assert annotate_shadow([f], {"BR": []}, NOW)[0] == f  # sem histórico: abstém, previsão intacta
    assert "shadow_v2" not in f["evidence"]  # a entrada não é mutada


def test_shadow_rows_only_for_resolved_with_v2_and_feed_the_gate():
    f = annotate_shadow([make_forecast()], {"BR": pts()}, NOW)[0]
    resolved = resolve_due([f], [{"timestamp": (NOW + timedelta(minutes=60)).strftime("%Y-%m-%dT%H:%M:%SZ"), "score": 45}], NOW + timedelta(minutes=61))
    rows = shadow_rows(resolved)
    assert len(rows) == 1 and rows[0]["outcome"] == 1 and rows[0]["method"] == "pulse_empirical_delta"
    assert 0 < rows[0]["p_v1"] < 1 and 0 < rows[0]["p_v2"] < 1 and rows[0]["scope"] == "BR"
    assert shadow_rows([make_forecast()]) == [] and shadow_rows([{**make_forecast(), "status": "resolved", "outcome": 1}]) == []
    gate = promotion_gate([{**r, "item_id": f"i{i}"} for i, r in enumerate(rows)])
    assert not gate["passed"] and "INSUFFICIENT_DATA" in gate["reasons"][0]  # uma amostra nunca promove nada
