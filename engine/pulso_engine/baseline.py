"""Baseline: o que é "normal" para um escopo x categoria, a partir do histórico de contagens.

Estatística simples e explicável (média e desvio exponencialmente ponderados). Sem dados
suficientes o baseline é declarado INVÁLIDO; nunca se inventa um "normal".
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

MIN_HOURS = 12  # horas com dados exigidas para confiar no baseline
MIN_DATA_HOURS = 6  # ... das quais ao menos estas com algum sinal (horas zeradas podem ser lacuna de coleta, não calmaria)
ALPHA = 0.15  # peso da hora mais recente na EWMA


@dataclass(frozen=True)
class Baseline:
    mean: float
    std: float
    hours: int  # quantas horas de histórico sustentam o baseline
    data_hours: int = 0  # ... e em quantas delas houve ao menos um sinal

    @property
    def valid(self) -> bool:
        # Linhas só existem para janelas COM sinal: hora sem linha vira 0, e 0 pode ser calmaria OU uma lacuna de coleta
        # (o sistema não distingue). Um "normal" feito quase só de zeros faria 4 sinais parecerem uma anomalia enorme.
        return self.hours >= MIN_HOURS and self.data_hours >= max(MIN_DATA_HOURS, self.hours // 3)


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
        return Baseline(0.0, 0.0, 0, 0)
    mean = float(values[0])
    var = 0.0
    for v in values[1:]:
        diff = v - mean
        mean += ALPHA * diff
        var = (1 - ALPHA) * (var + ALPHA * diff * diff)
    return Baseline(mean, math.sqrt(var), len(values), sum(1 for v in values if v > 0))


# ---------------------------------------------------------------------------------------------------------------------
# Baseline sazonal (passo 2 do Sentinela): "normal" para ESTA hora do dia e, havendo semanas, ESTE dia da semana.
# Consome as observações horárias (`signal_observations`, ver docs/research/SPEC_01_HISTORY.md). Não substitui o EWMA:
# sem histórico suficiente devolve base INSUFICIENTE (valid=False) e quem chama usa o EWMA ou afirma nada.
# ---------------------------------------------------------------------------------------------------------------------
BR_TZ = timezone(timedelta(hours=-3))  # o Brasil não tem horário de verão desde 2019: "domingo 03:00" é hora de Brasília
MIN_SAMPLES_DOW_HOUR = 3  # ocorrências do MESMO dia da semana e hora (3 semanas)
MIN_SAMPLES_HOUR = 5  # ocorrências da mesma hora do dia (5 dias)
SEASONAL_LOOKBACK_H = 24 * 7 * 6  # até 6 semanas de histórico


@dataclass(frozen=True)
class SeasonalBaseline:
    """Mesma superfície de `Baseline` que `anomaly` usa (mean, std, valid), mais a base em que se apoia."""

    mean: float
    std: float
    samples: int  # quantas horas comparáveis sustentam o normal
    basis: str  # "dow_hour" | "hour" | "insufficient"
    data_hours: int = 0  # horas com ao menos um sinal entre as comparáveis
    values: tuple[int, ...] = ()  # as contagens comparáveis (base do percentil)

    @property
    def valid(self) -> bool:
        return self.basis != "insufficient"


INSUFFICIENT = SeasonalBaseline(0.0, 0.0, 0, "insufficient", 0)


def _parse_hour(v: str) -> datetime:
    return datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def seasonal_hourly(rows: list[dict], scope: str, category: str, until: datetime,
                    lookback_h: int = SEASONAL_LOOKBACK_H) -> dict[datetime, int]:
    """Contagem por hora cheia (soma das classes de fonte), EXCLUINDO a hora de `until`. Horas sem linha viram 0 só
    dentro da faixa coberta (da primeira à última hora com dado), como em `hourly_counts`: antes disso é desconhecido."""
    until = until.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = until - timedelta(hours=lookback_h)
    by_hour: dict[datetime, int] = {}
    for r in rows:
        if r["scope"] != scope or r["category"] != category:
            continue
        h = _parse_hour(r["hour"])
        if start <= h < until:
            by_hour[h] = by_hour.get(h, 0) + int(r["signals"])
    if not by_hour:
        return {}
    first = min(by_hour)
    n = int((until - first).total_seconds() // 3600)
    return {first + timedelta(hours=i): by_hour.get(first + timedelta(hours=i), 0) for i in range(n)}


def _mean_std(values: list[int]) -> tuple[float, float]:
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / max(1, len(values) - 1)
    return mean, math.sqrt(var)


def seasonal_baseline(rows: list[dict], scope: str, category: str, at: datetime) -> SeasonalBaseline:
    """Normal esperado para a hora de `at` (hora de Brasília). Tenta mesmo dia da semana e hora; senão só a hora do dia;
    senão INSUFICIENTE. Histórico esparso (quase só zeros) também é insuficiente: zero pode ser lacuna de coleta."""
    series = seasonal_hourly(rows, scope, category, at)
    if not series:
        return INSUFFICIENT
    if sum(1 for v in series.values() if v > 0) < max(MIN_DATA_HOURS, len(series) // 3):
        return INSUFFICIENT
    local = at.astimezone(BR_TZ)
    same_hour = [(h.astimezone(BR_TZ), v) for h, v in series.items() if h.astimezone(BR_TZ).hour == local.hour]
    same_slot = [v for lh, v in same_hour if lh.weekday() == local.weekday()]
    for basis, values, minimum in (("dow_hour", same_slot, MIN_SAMPLES_DOW_HOUR), ("hour", [v for _, v in same_hour], MIN_SAMPLES_HOUR)):
        if len(values) >= minimum:
            mean, std = _mean_std(values)
            return SeasonalBaseline(mean, std, len(values), basis, sum(1 for v in values if v > 0), tuple(values))
    return INSUFFICIENT
