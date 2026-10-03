"""Ponte entre observações horárias e a anomalia V2 (baseline sazonal -> EWMA -> inválido), para uso das features do Forecast V2.

Fica separada para as features não importarem o Sentinela inteiro. Mesma regra do Sentinela: sazonal quando válido, senão EWMA
das horas observadas, senão `BASELINE INSUFICIENTE` (nunca finge normal).
"""
from __future__ import annotations

from datetime import datetime

from .baseline import ewma_baseline, seasonal_baseline, seasonal_hourly
from .intelligence.anomaly_v2 import anomaly_v2


def window_anomaly_state(count: int, minutes: int, obs_rows: list[dict], scope: str, category: str, at: datetime) -> dict:
    base = seasonal_baseline(obs_rows, scope, category, at)
    if not base.valid:
        base = ewma_baseline(list(seasonal_hourly(obs_rows, scope, category, at).values()))
    return anomaly_v2(count, minutes, base)
