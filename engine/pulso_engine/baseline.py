"""Baseline: o que é "normal" para um escopo x categoria, a partir do histórico de contagens.

Estatística simples e explicável (média e desvio exponencialmente ponderados). Sem dados
suficientes o baseline é declarado INVÁLIDO; nunca se inventa um "normal".
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

MIN_HOURS = 12  # horas com dados exigidas para confiar no baseline
ALPHA = 0.15  # peso da hora mais recente na EWMA


@dataclass(frozen=True)
class Baseline:
    mean: float
    std: float
    hours: int  # quantas horas de histórico sustentam o baseline

    @property
    def valid(self) -> bool:
        return self.hours >= MIN_HOURS


def hourly_counts(rows: list[dict], scope: str, category: str, until: datetime, hours: int = 48) -> list[int]:
    """Soma as janelas de 5 min em horas cheias, da mais antiga à mais recente, EXCLUINDO a hora de `until`
    (a hora corrente é incompleta e é comparada ao baseline, não faz parte dele). Horas sem linha contam 0
    somente se houver dados em horas vizinhas, para não confundir lacuna de coleta com calmaria."""
    until = until.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = until - timedelta(hours=hours)
    by_hour: dict[datetime, int] = {}
    for r in rows:
        if r["scope"] != scope or r["category"] != category:
            continue
        b = datetime.fromisoformat(r["bucket"].replace("Z", "+00:00")).replace(minute=0, second=0, microsecond=0)
        if start <= b < until:
            by_hour[b] = by_hour.get(b, 0) + int(r["signals"])
    if not by_hour:
        return []
    first = min(by_hour)
    n = int((until - first).total_seconds() // 3600)
    return [by_hour.get(first + timedelta(hours=i), 0) for i in range(n)]


def ewma_baseline(values: list[int]) -> Baseline:
    if not values:
        return Baseline(0.0, 0.0, 0)
    mean = float(values[0])
    var = 0.0
    for v in values[1:]:
        diff = v - mean
        mean += ALPHA * diff
        var = (1 - ALPHA) * (var + ALPHA * diff * diff)
    return Baseline(mean, math.sqrt(var), len(values))
