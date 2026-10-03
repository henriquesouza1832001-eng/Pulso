import math
from datetime import datetime, timedelta, timezone

from pulso_engine.forecast import (
    MIN_PAIRS, brier, make_nowcasts, pair_deltas, prob_at_least, resolve_due, wilson,
)

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def series(scores, step_min=5, end=NOW):
    """Pontos do Pulso a cada `step_min`, terminando em `end` (último = scores[-1])."""
    n = len(scores)
    return [{"timestamp": iso(end - timedelta(minutes=step_min * (n - 1 - i))), "score": s} for i, s in enumerate(scores)]


def wave(n=80):
    """Pulso oscilando de forma regular entre 30 e 50, com variações de 60 min não triviais."""
    return [40 + round(10 * math.sin(i / 3)) for i in range(n)]


def test_pair_deltas_use_only_real_points_not_gaps():
    pts = series([10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34])  # 13 pontos = 60 min
    assert pair_deltas(pts) == [24]  # só o par (primeiro, último): 34 - 10
    gap = [p for i, p in enumerate(pts) if i != 12]  # remove o ponto de +60 min
    assert pair_deltas(gap) == []  # sem ponto real, sem par: nunca interpolamos


def test_wilson_and_laplace_never_certain():
    p, lo, hi, k = prob_at_least(40, [0.0] * 50, 100)  # impossível de acontecer nos dados
    assert 0 < p < 0.05 and lo <= p <= hi and k == 0
    p2, lo2, hi2, k2 = prob_at_least(40, [60.0] * 50, 60)  # sempre acontece nos dados
    assert 0.95 < p2 < 1 and lo2 <= p2 <= hi2 and k2 == 50
    assert wilson(0, 0) == (0.0, 1.0)


def test_no_forecast_without_enough_history():
    short = series(wave(20))  # menos de 36 pares
    assert make_nowcasts(short, NOW) == []
    assert make_nowcasts([], NOW) == []


def test_no_forecast_when_latest_point_is_stale():
    pts = series(wave(120), end=NOW - timedelta(minutes=30))
    assert make_nowcasts(pts, NOW) == []


def test_makes_valid_open_forecasts_with_evidence_and_immutable_id():
    pts = series(wave(120))
    fs = make_nowcasts(pts, NOW)
    assert fs, "com histórico suficiente deve prever"
    pairs = len(pair_deltas(pts))
    assert pairs >= MIN_PAIRS
    for f in fs:
        assert f["status"] == "open" and f["outcome"] is None and f["brier"] is None
        assert 0 < f["probability"] < 1 and f["interval_low"] <= f["probability"] <= f["interval_high"]
        assert f["evidence"]["pairs"] == pairs and f["evidence"]["current_score"] == pts[-1]["score"]
        assert f["resolves_at"] == iso(NOW + timedelta(minutes=60))
        assert f["threshold"] > pts[-1]["score"] and f["forecast_id"].startswith("fc-pulse-br-gte-")
    # mesma hora => mesmos ids (reenvio não duplica; o Worker ignora a reescrita)
    again = make_nowcasts(pts, NOW + timedelta(minutes=5))
    assert [f["forecast_id"] for f in again] == [f["forecast_id"] for f in fs]


def test_resolution_scores_with_brier_and_never_before_due():
    f = make_nowcasts(series(wave(120)), NOW)[0]
    # ainda não venceu
    assert resolve_due([f], series([60], end=NOW + timedelta(minutes=59)), NOW + timedelta(minutes=59)) == []
    due = NOW + timedelta(minutes=60)
    hit = resolve_due([f], [{"timestamp": iso(due + timedelta(minutes=2)), "score": f["threshold"] + 3}], due + timedelta(minutes=3))[0]
    assert hit["status"] == "resolved" and hit["outcome"] == 1
    assert hit["brier"] == round(brier(f["probability"], 1), 6) and hit["observed_value"] == f["threshold"] + 3
    miss = resolve_due([f], [{"timestamp": iso(due + timedelta(minutes=2)), "score": f["threshold"] - 5}], due + timedelta(minutes=3))[0]
    assert miss["outcome"] == 0 and miss["brier"] == round(brier(f["probability"], 0), 6)


def test_forecast_is_voided_when_no_observation_arrives_in_time():
    f = make_nowcasts(series(wave(120)), NOW)[0]
    late = NOW + timedelta(minutes=60 + 45)
    res = resolve_due([f], [], late)[0]
    assert res["status"] == "void" and res["outcome"] is None and res["brier"] is None
    assert resolve_due([f], [], NOW + timedelta(minutes=60 + 10)) == []  # ainda dá tempo de observar


def test_open_forecast_from_db_with_json_evidence_string_is_accepted():
    f = make_nowcasts(series(wave(120)), NOW)[0]
    row = {**f, "evidence": '{"current_score": 40}'}  # como vem do D1
    due = NOW + timedelta(minutes=61)
    out = resolve_due([row], [{"timestamp": iso(due), "score": 99}], due)[0]
    assert out["evidence"] == {"current_score": 40} and out["status"] == "resolved"


def test_pipeline_emits_forecasts_only_with_history():
    from tests.test_pipeline import rss, src
    from pulso_engine.pipeline import run_once

    feeds = {"https://a.com/rss": rss(("Temporal causa alagamento em Belo Horizonte", "https://a.com/1", 5))}
    no_hist = run_once([src("a")], lambda u: feeds[u], NOW)
    assert no_hist["forecasts"] == []
    with_hist = run_once([src("a")], lambda u: feeds[u], NOW, pulse_points=series(wave(120), end=NOW - timedelta(minutes=1)))
    assert with_hist["forecasts"] and all(x["status"] == "open" for x in with_hist["forecasts"])
