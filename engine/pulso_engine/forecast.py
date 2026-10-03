"""Previsões (NOWCAST) do Pulso: probabilidade calibrável, registrada antes e pontuada depois.

Previsor v1, deliberadamente simples e EXPERIMENTAL (docs/architecture/PREDICTION.md):
  pergunta  "o Pulso do escopo será >= T daqui a 60 min?"
  método    distribuição EMPÍRICA das variações de 60 min já observadas no próprio histórico do Pulso,
            aplicada ao valor atual (persistência + ruído histórico). Probabilidade com suavização de
            Laplace (nunca 0 nem 1) e intervalo de Wilson.
Sem histórico suficiente NÃO se prevê (nada de chute): devolve lista vazia.
"""
from __future__ import annotations

import bisect
import math
from datetime import datetime, timedelta, timezone

METHOD = "pulse_empirical_delta"
VERSION = "1"
HORIZON_MIN = 60
MIN_PAIRS = 36  # pares (t, t+60 min) exigidos: ~3,5 h de histórico contínuo
PAIR_TOL_MIN = 4  # tolerância ao procurar o ponto 60 min depois
FRESH_MIN = 15  # o ponto mais recente do Pulso precisa ser de no máximo 15 min atrás
RESOLVE_WINDOW_MIN = 10  # o valor observado deve estar até 10 min após o vencimento
VOID_AFTER_MIN = 30  # sem observação até 30 min após o vencimento => anulada
STEPS = (10, 20)  # perguntas: "Pulso >= atual+10" e "Pulso >= atual+20" (arredondado a 5)


def _ts(v: str) -> datetime:
    return datetime.fromisoformat(v.replace("Z", "+00:00"))


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pair_deltas(points: list[dict], horizon_min: int = HORIZON_MIN, tol_min: int = PAIR_TOL_MIN) -> list[float]:
    """Variações do Pulso em `horizon_min` minutos, formadas só por pontos REAIS (sem interpolar lacunas)."""
    pts = sorted(((_ts(p["timestamp"]), float(p["score"])) for p in points), key=lambda x: x[0])
    times = [t for t, _ in pts]
    out: list[float] = []
    for i, (t, v) in enumerate(pts):
        target = t + timedelta(minutes=horizon_min)
        j = bisect.bisect_left(times, target - timedelta(minutes=tol_min), lo=i + 1)
        if j < len(pts) and abs((times[j] - target).total_seconds()) <= tol_min * 60:
            out.append(pts[j][1] - v)
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def prob_at_least(current: float, deltas: list[float], threshold: float) -> tuple[float, float, float, int]:
    """(probabilidade, piso, teto, acertos). Laplace garante 0 < p < 1; o intervalo sempre contém p."""
    n = len(deltas)
    k = sum(1 for d in deltas if current + d >= threshold)
    p = (k + 1) / (n + 2)
    lo, hi = wilson(k, n)
    return p, min(lo, p), max(hi, p), k


def brier(p: float, outcome: int) -> float:
    return (p - outcome) ** 2


def _scope_slug(scope: str) -> str:
    return scope.lower().replace(":", "-")


def _scope_label(scope: str) -> str:
    return "Brasil" if scope == "BR" else scope.split(":")[1]


def make_nowcasts(points: list[dict], now: datetime, scope: str = "BR") -> list[dict]:
    """Novas previsões. [] se faltar histórico ou se o último ponto do Pulso estiver velho."""
    if not points:
        return []
    last = max(points, key=lambda p: _ts(p["timestamp"]))
    if (now - _ts(last["timestamp"])).total_seconds() > FRESH_MIN * 60:
        return []
    deltas = pair_deltas(points)
    if len(deltas) < MIN_PAIRS:
        return []
    current = float(last["score"])
    spans = sorted(_ts(p["timestamp"]) for p in points)
    out: list[dict] = []
    seen: set[int] = set()
    for step in STEPS:
        threshold = min(100, math.ceil((current + step) / 5) * 5)
        if threshold <= current or threshold in seen:
            continue
        seen.add(threshold)
        p, lo, hi, k = prob_at_least(current, deltas, threshold)
        out.append({
            "forecast_id": f"fc-pulse-{_scope_slug(scope)}-gte-{threshold}-h{HORIZON_MIN}-{now.strftime('%Y%m%d%H')}",
            "kind": "NOWCAST",
            "question": f"O Pulso do {_scope_label(scope)} será igual ou maior que {threshold} daqui a {HORIZON_MIN} minutos?",
            "scope": scope, "metric": "pulse", "comparator": "gte", "threshold": float(threshold),
            "method": METHOD, "method_version": VERSION,
            "probability": round(p, 4), "interval_low": round(lo, 4), "interval_high": round(hi, 4),
            "horizon_minutes": HORIZON_MIN,
            "created_at": _iso(now), "resolves_at": _iso(now + timedelta(minutes=HORIZON_MIN)),
            "evidence": {
                "current_score": current, "pairs": len(deltas), "hits": k,
                "history_hours": round((spans[-1] - spans[0]).total_seconds() / 3600, 1),
                "note": "variações de 60 min observadas no próprio histórico do Pulso",
            },
            "status": "open", "outcome": None, "observed_value": None, "resolved_at": None, "brier": None,
        })
    return out


def resolve_due(open_forecasts: list[dict], points: list[dict], now: datetime) -> list[dict]:
    """Resolve as previsões vencidas com o valor REAL observado; anula as sem observação a tempo."""
    pts = sorted(((_ts(p["timestamp"]), float(p["score"])) for p in points), key=lambda x: x[0])
    out: list[dict] = []
    for f in open_forecasts:
        due = _ts(f["resolves_at"])
        if due > now:
            continue
        evidence = f["evidence"] if isinstance(f["evidence"], dict) else _loads(f["evidence"])
        base = {**f, "evidence": evidence}
        obs = next((v for t, v in pts if due <= t <= due + timedelta(minutes=RESOLVE_WINDOW_MIN)), None)
        if obs is not None:
            hit = obs >= f["threshold"] if f["comparator"] == "gte" else obs <= f["threshold"]
            outcome = int(hit)
            out.append({**base, "status": "resolved", "outcome": outcome, "observed_value": obs,
                        "resolved_at": _iso(now), "brier": round(brier(f["probability"], outcome), 6)})
        elif (now - due).total_seconds() > VOID_AFTER_MIN * 60:
            out.append({**base, "status": "void", "outcome": None, "observed_value": None,
                        "resolved_at": _iso(now), "brier": None})
    return out


def _loads(s: str) -> dict:
    import json

    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return {}
