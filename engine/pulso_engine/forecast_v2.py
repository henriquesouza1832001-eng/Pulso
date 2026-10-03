"""Previsor V2 do Pulso em SHADOW: o mesmo desenho do V1, condicionado à HORA DO DIA.

V1 (`forecast.py`) usa todas as variações de 60 min já vistas. O Pulso tem ciclo diário (madrugada calma, fim de tarde
agitado): o V2 usa só variações iniciadas na mesma hora local (+-1 h) da previsão. Se não houver pares suficientes NÃO prevê
(o V2 se abstém e o item não entra na comparação). O V2 nunca aparece ao usuário: a probabilidade fica em
`evidence.shadow_v2` da previsão do V1 e, quando ela resolve, vira uma linha de `shadow_results` (V1 x V2 x desfecho), que
alimenta o portão de promoção. Atrás da flag `FORECAST_V2_SHADOW`. Probabilidade só de estatística, nunca de LLM.
"""
from __future__ import annotations

import bisect
from datetime import datetime, timedelta

from .baseline import BR_TZ
from .forecast import HORIZON_MIN, PAIR_TOL_MIN, _ts, prob_at_least

METHOD = "pulse_hour_conditioned"
VERSION = "1"
MIN_PAIRS = 24  # pares na mesma hora do dia (o V1 exige 36 no total)
HOUR_WINDOW = 1  # +-1 hora local


def _circular_hour_gap(a: int, b: int) -> int:
    d = abs(a - b) % 24
    return min(d, 24 - d)


def hour_deltas(points: list[dict], at: datetime) -> list[float]:
    """Variações de 60 min de pontos REAIS cujo início cai a +-1 h da hora local de `at`."""
    pts = sorted(((_ts(p["timestamp"]), float(p["score"])) for p in points), key=lambda x: x[0])
    times = [t for t, _ in pts]
    target_hour = at.astimezone(BR_TZ).hour
    out: list[float] = []
    for i, (t, v) in enumerate(pts):
        if _circular_hour_gap(t.astimezone(BR_TZ).hour, target_hour) > HOUR_WINDOW:
            continue
        target = t + timedelta(minutes=HORIZON_MIN)
        j = bisect.bisect_left(times, target - timedelta(minutes=PAIR_TOL_MIN), lo=i + 1)
        if j < len(pts) and abs((times[j] - target).total_seconds()) <= PAIR_TOL_MIN * 60:
            out.append(pts[j][1] - v)
    return out


def v2_probability(points: list[dict], now: datetime, current: float, threshold: float) -> dict | None:
    """{'probability', 'pairs'} ou None (abstenção) se faltar histórico na mesma hora do dia."""
    deltas = hour_deltas(points, now)
    if len(deltas) < MIN_PAIRS:
        return None
    p, _, _, _ = prob_at_least(current, deltas, threshold)
    return {"probability": round(p, 4), "pairs": len(deltas)}


def annotate_shadow(forecasts: list[dict], points_by_scope: dict[str, list[dict]], now: datetime) -> list[dict]:
    """Acrescenta `evidence.shadow_v2` às previsões ABERTAS de Pulso (novas); o resto passa intacto. O V1 não muda."""
    out = []
    for f in forecasts:
        if f.get("status") != "open" or f.get("metric") != "pulse" or f.get("kind") != "NOWCAST" or not isinstance(f.get("evidence"), dict):
            out.append(f)
            continue
        res = v2_probability(points_by_scope.get(f["scope"], []), now, float(f["evidence"].get("current_score", 0.0)), float(f["threshold"]))
        if res is None:
            out.append(f)
            continue
        out.append({**f, "evidence": {**f["evidence"], "shadow_v2": {"method": METHOD, "version": VERSION, **res}}})
    return out


def shadow_rows(resolved: list[dict]) -> list[dict]:
    """Linhas de `shadow_results` das previsões que acabaram de RESOLVER e tinham `evidence.shadow_v2`."""
    rows = []
    for f in resolved:
        ev = f.get("evidence")
        sh = ev.get("shadow_v2") if isinstance(ev, dict) else None
        if f.get("status") != "resolved" or f.get("outcome") not in (0, 1) or not sh:
            continue
        rows.append({"item_id": f["forecast_id"], "method": f["method"], "scope": f["scope"],
                     "p_v1": float(f["probability"]), "p_v2": float(sh["probability"]), "outcome": int(f["outcome"])})
    return rows
