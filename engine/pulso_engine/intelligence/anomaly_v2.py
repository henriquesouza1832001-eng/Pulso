"""Anomalia V2: `anomaly_score` (quão fora do normal) e `anomaly_confidence` (quanto se pode confiar nessa medida) SEPARADOS.

Usa estatística robusta (mediana e MAD) além do z-score: um baseline com poucos picos antigos não infla o desvio. Reaproveita
`anomaly.window_anomaly` para o z escalado pela janela e o percentil. Sem baseline válido: score 0, confiança 0 e status
`BASELINE INSUFICIENTE`, nunca uma anomalia inventada. Sem LLM.
"""
from __future__ import annotations

import math
import statistics

from ..anomaly import NO_BASELINE, window_anomaly

MAD_SCALE = 1.4826  # converte MAD em desvio padrão equivalente sob normalidade
MIN_ROBUST_STD = 1.0
Z_SATURATION = 4.0
FULL_CONFIDENCE_SAMPLES = 12  # amostras comparáveis para confiança máxima da medida


def robust_baseline(values: list[int] | tuple[int, ...]) -> tuple[float, float]:
    """(mediana, desvio robusto) das contagens horárias comparáveis."""
    if not values:
        return 0.0, 0.0
    med = statistics.median(values)
    mad = statistics.median(abs(v - med) for v in values)
    return float(med), float(mad * MAD_SCALE)


def robust_z(count: int, minutes: int, values: list[int] | tuple[int, ...]) -> float | None:
    """z robusto de `count` sinais em `minutes` contra contagens horárias; None sem amostras."""
    if not values:
        return None
    med, std = robust_baseline(values)
    frac = minutes / 60
    return round((count - med * frac) / (max(std, MIN_ROBUST_STD) * math.sqrt(frac)), 2)


def anomaly_confidence(base, n_signals: int) -> float:
    """0-1: cresce com as amostras do baseline, é maior na base sazonal por dia da semana e cai quando a janela atual tem
    poucos sinais (uma contagem de 1 ou 2 é ruído, mesmo contra um baseline bom)."""
    if not getattr(base, "valid", False):
        return 0.0
    samples = getattr(base, "samples", None) or getattr(base, "hours", 0)
    basis_factor = {"dow_hour": 1.0, "hour": 0.8}.get(getattr(base, "basis", "ewma"), 0.6)
    volume = min(1.0, n_signals / 5)
    return round(min(1.0, samples / FULL_CONFIDENCE_SAMPLES) * basis_factor * volume, 3)


def anomaly_v2(count: int, minutes: int, base) -> dict:
    """Resultado completo. `base`: `SeasonalBaseline` (preferido) ou `Baseline`."""
    classic = window_anomaly(count, minutes, base)
    if classic["status"] == NO_BASELINE:
        return {**classic, "robust_z": None, "confidence": 0.0}
    rz = robust_z(count, minutes, getattr(base, "values", ()))
    # o score usa o MENOR entre z clássico e robusto quando ambos existem: só é anomalia se as duas réguas concordam
    z = classic["z"] if rz is None else min(classic["z"], rz)
    score = round(max(0.0, min(1.0, z / Z_SATURATION)), 3)
    return {**classic, "z": round(z, 2), "robust_z": rz, "score": score, "confidence": anomaly_confidence(base, count),
            "status": "ANOMALY" if score >= 0.65 else "NORMAL"}
