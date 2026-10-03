"""Indicadores antecedentes entre categorias: "o clima costuma subir ~2 h antes do trânsito?".

Mede, no próprio histórico, a correlação entre a série horária de uma categoria A e a de B deslocada de 1 a 6 h.
Se A tem correlação defasada relevante com B E A está agora acima do normal, A entra como EVIDÊNCIA na previsão de B
("por que esta previsão?"). Honestidade: correlação não é causa, e o indicador NÃO altera a probabilidade (isso só
pode acontecer depois que melhorar o Brier num backtest, ver backtest.py e docs/architecture/PREDICTION.md).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from .baseline import ewma_baseline
from .forecast import _ts

MIN_HOURS_WITH_DATA = 48  # horas distintas com dado (de 96) para confiar numa correlação
MAX_LAG_H = 6
MIN_R = 0.3
MIN_Z = 1.0  # a categoria líder precisa estar >= 1 desvio acima do normal agora
TOP = 3


def _hour(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def aligned_hourly(rows: list[dict], scope: str, categories: set[str], until: datetime, hours: int = 96) -> dict[str, list[int]] | None:
    """Séries horárias de várias categorias, alinhadas, das últimas `hours` horas COMPLETAS antes de `until`.
    None se houver pouca cobertura (poucas horas com dado), para não correlacionar lacunas de coleta."""
    end = _hour(until)
    start = end - timedelta(hours=hours)
    counts = {c: [0] * hours for c in categories}
    covered: set[int] = set()
    for r in rows:
        if r["scope"] != scope or r["category"] not in counts:
            continue
        idx = int((_hour(_ts(r["bucket"])) - start) / timedelta(hours=1))
        if 0 <= idx < hours:
            counts[r["category"]][idx] += int(r["signals"])
            covered.add(idx)
    return counts if len(covered) >= MIN_HOURS_WITH_DATA else None


def pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 3 or n != len(y):
        return 0.0
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx == 0 or syy == 0:
        return 0.0
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(sxx * syy)


def best_lead(a: list[int], b: list[int], max_lag: int = MAX_LAG_H) -> tuple[int, float]:
    """Defasagem (em horas) em que `a` melhor antecede `b`, e a correlação nela."""
    best = (0, 0.0)
    for lag in range(1, max_lag + 1):
        r = pearson([float(v) for v in a[:-lag]], [float(v) for v in b[lag:]])
        if r > best[1]:
            best = (lag, r)
    return best


def leading_indicators(rows: list[dict], target: str, scope: str, now: datetime) -> list[dict]:
    """Categorias que historicamente antecedem `target` neste escopo e estão acima do normal agora."""
    from .forecast_surge import rolling_hour  # import tardio: forecast_surge importa este módulo

    cats = {r["category"] for r in rows if r["scope"] == scope and r["category"] != "OTHER"}
    if target not in cats or len(cats) < 2:
        return []
    counts = aligned_hourly(rows, scope, cats, now)
    if counts is None:
        return []
    out = []
    for c in sorted(cats - {target}):
        lag, r = best_lead(counts[c], counts[target])
        if r < MIN_R:
            continue
        base = ewma_baseline(counts[c])
        z = (rolling_hour(rows, scope, c, now) - base.mean) / max(base.std, 1.0)
        if z >= MIN_Z:
            out.append({"category": c, "lag_hours": lag, "correlation": round(r, 2), "current_z": round(z, 1)})
    out.sort(key=lambda d: -(d["correlation"] * d["current_z"]))
    return out[:TOP]
