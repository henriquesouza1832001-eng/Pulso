"""Métricas de avaliação (puras): Brier, log loss, erro de calibração (ECE), precision/recall/F1, FPR, lead time e cobertura.

Entrada: pares `(probabilidade, desfecho 0/1)`. Quando não há amostras as métricas devolvem None: nunca 0 fingindo acerto.
"""
from __future__ import annotations

import math
import statistics

EPS = 1e-9


def brier(pairs: list[tuple[float, int]]) -> float | None:
    return round(sum((p - o) ** 2 for p, o in pairs) / len(pairs), 6) if pairs else None


def log_loss(pairs: list[tuple[float, int]]) -> float | None:
    if not pairs:
        return None
    total = sum(-(o * math.log(min(max(p, EPS), 1 - EPS)) + (1 - o) * math.log(min(max(1 - p, EPS), 1 - EPS))) for p, o in pairs)
    return round(total / len(pairs), 6)


def calibration_error(pairs: list[tuple[float, int]], bins: int = 5) -> float | None:
    """ECE: média ponderada de |frequência observada - probabilidade média prevista| por faixa."""
    if not pairs:
        return None
    err = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        cell = [(p, o) for p, o in pairs if lo <= p < hi or (b == bins - 1 and p == 1.0)]
        if cell:
            err += len(cell) / len(pairs) * abs(sum(o for _, o in cell) / len(cell) - sum(p for p, _ in cell) / len(cell))
    return round(err, 6)


def confusion(pairs: list[tuple[float, int]], cutoff: float = 0.5) -> dict[str, int]:
    tp = sum(1 for p, o in pairs if p >= cutoff and o == 1)
    fp = sum(1 for p, o in pairs if p >= cutoff and o == 0)
    fn = sum(1 for p, o in pairs if p < cutoff and o == 1)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": len(pairs) - tp - fp - fn}


def _ratio(a: int, b: int) -> float | None:
    return round(a / b, 4) if b else None


def classification(pairs: list[tuple[float, int]], cutoff: float = 0.5) -> dict[str, float | None]:
    c = confusion(pairs, cutoff)
    precision, recall = _ratio(c["tp"], c["tp"] + c["fp"]), _ratio(c["tp"], c["tp"] + c["fn"])
    f1 = round(2 * precision * recall / (precision + recall), 4) if precision and recall else None
    return {"precision": precision, "recall": recall, "f1": f1, "fpr": _ratio(c["fp"], c["fp"] + c["tn"])}


def lead_time_summary(lead_minutes: list[float | None]) -> dict[str, float | int | None]:
    """Mediana e p90 só dos eventos detectados antes do T0 (None = não detectado); `coverage` = fração detectada."""
    got = sorted(x for x in lead_minutes if x is not None)
    return {"events": len(lead_minutes), "detected": len(got),
            "coverage": _ratio(len(got), len(lead_minutes)),
            "median": round(statistics.median(got), 1) if got else None,
            "p90": round(got[min(len(got) - 1, math.ceil(0.9 * len(got)) - 1)], 1) if got else None}


def base_rate_reference(outcomes: list[int]) -> float | None:
    """Brier do previsor ingênuo (sempre a frequência observada): a régua que todo modelo precisa vencer."""
    if not outcomes:
        return None
    p = sum(outcomes) / len(outcomes)
    return round(sum((p - o) ** 2 for o in outcomes) / len(outcomes), 6)
