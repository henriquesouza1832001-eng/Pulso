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


# --- Anomalia v2 (passo 4): por janela, com percentil e base explícita ------------------------------------------------
import math  # noqa: E402

PERCENTILE_MIN_SAMPLES = 5  # com menos comparáveis o percentil não é afirmado
NO_BASELINE = "BASELINE INSUFICIENTE"


def percentile_rank(current: float, samples: tuple[int, ...] | list[int]) -> float | None:
    """Fração (0-1) das contagens comparáveis menores ou iguais a `current`. None sem amostras suficientes."""
    if len(samples) < PERCENTILE_MIN_SAMPLES:
        return None
    return sum(1 for v in samples if v <= current) / len(samples)


def window_anomaly(count: int, minutes: int, base) -> dict:
    """Anomalia de `count` sinais numa janela de `minutes` contra um baseline HORÁRIO (`Baseline` ou `SeasonalBaseline`).

    Escala o normal pela janela (média x minutes/60; desvio x raiz de minutes/60, como contagens independentes). Devolve
    o z, o percentil (se houver amostras sazonais), a base usada e `status`; com baseline inválido o score é 0 e o status
    diz BASELINE INSUFICIENTE: o sistema não finge anomalia."""
    if not base.valid:
        return {"score": 0.0, "z": 0.0, "percentile": None, "basis": getattr(base, "basis", "ewma"), "status": NO_BASELINE}
    frac = minutes / 60
    mean = base.mean * frac
    std = max(base.std * math.sqrt(frac), MIN_STD * math.sqrt(frac))
    z = (count - mean) / std
    pct = percentile_rank(count / frac, getattr(base, "values", ()))  # mesma unidade das contagens horárias
    score = max(0.0, min(1.0, z / Z_SATURATION))
    return {"score": round(score, 3), "z": round(z, 2), "percentile": None if pct is None else round(pct, 3),
            "basis": getattr(base, "basis", "ewma"), "status": "ANOMALY" if score >= 0.65 else "NORMAL"}
