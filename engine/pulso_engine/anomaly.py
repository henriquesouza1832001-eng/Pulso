"""Anomalia: quão acima do normal está a atividade atual (0 = normal, 1 = muito anormal)."""
from __future__ import annotations

from .baseline import Baseline

MIN_STD = 1.0  # evita z-score explosivo quando o histórico é quase constante
Z_SATURATION = 4.0  # z >= 4 desvios = anomalia máxima


def zscore(current: float, base: Baseline) -> float:
    return (current - base.mean) / max(base.std, MIN_STD)


def anomaly_score(current: float, base: Baseline) -> float:
    """0 se o baseline não é válido (sem histórico suficiente não se afirma anomalia) ou se está abaixo do normal."""
    if not base.valid:
        return 0.0
    return max(0.0, min(1.0, zscore(current, base) / Z_SATURATION))
