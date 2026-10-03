"""Trend engine: métricas por janela temporal e a diferença entre "crescendo" e "alto porém estável".

Função pura sobre os sinais da rodada (publicação = `Signal.timestamp`). Janelas: 5, 15, 30, 60, 180, 360 e 1440 min.
Velocidade = sinais por hora na janela; aceleração = diferença entre a velocidade da janela e a da janela IMEDIATAMENTE
anterior de mesmo tamanho (positiva = acelerando). Sem dado suficiente a tendência é `INSUFFICIENT`, nunca inventada.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..models import Signal

WINDOWS_MIN = (5, 15, 30, 60, 180, 360, 1440)
MIN_SIGNALS_FOR_TREND = 4  # abaixo disso (atual + anterior) a tendência não é afirmada
RISE_RATIO = 1.5  # janela atual >= 1,5x a anterior = crescendo
FALL_RATIO = 0.67


@dataclass(frozen=True)
class WindowMetrics:
    minutes: int
    signal_count: int
    source_count: int
    source_type_count: int
    velocity: float  # sinais por hora
    acceleration: float  # velocidade atual - velocidade da janela anterior (sinais/hora)
    geographic_density: float  # UFs distintas por sinal com UF (0 = tudo no mesmo estado, 1 = cada sinal num estado)
    duplicate_ratio: float  # cópias descartadas / (sinais + cópias)
    official_confirmation: bool


def _in(signals: list[Signal], start: datetime, end: datetime) -> list[Signal]:
    return [s for s in signals if start < s.timestamp <= end]


def window_metrics(signals: list[Signal], now: datetime, minutes: int,
                   duplicates_by_hash: dict[str, int] | None = None) -> WindowMetrics:
    dups = duplicates_by_hash or {}
    delta = timedelta(minutes=minutes)
    cur = _in(signals, now - delta, now)
    prev = _in(signals, now - 2 * delta, now - delta)
    hours = minutes / 60
    vel, prev_vel = len(cur) / hours, len(prev) / hours
    ufs = [s.state for s in cur if s.state]
    copies = sum(max(0, dups.get(s.hash, 0)) for s in cur)
    return WindowMetrics(
        minutes=minutes,
        signal_count=len(cur),
        source_count=len({s.source_id for s in cur}),
        source_type_count=len({s.source_class for s in cur}),
        velocity=round(vel, 3),
        acceleration=round(vel - prev_vel, 3),
        geographic_density=round(len(set(ufs)) / len(ufs), 3) if ufs else 0.0,
        duplicate_ratio=round(copies / (len(cur) + copies), 3) if (cur or copies) else 0.0,
        official_confirmation=any(s.source_class == "OFFICIAL" for s in cur),
    )


def trend_state(signals: list[Signal], now: datetime, minutes: int = 60) -> str:
    """RISING | STABLE_HIGH | STABLE | FALLING | QUIET | INSUFFICIENT para a janela de `minutes`.

    Volume alto mas estável (atual ~ anterior) NÃO é crescimento: é STABLE_HIGH. Distinção que o Pulso precisa."""
    delta = timedelta(minutes=minutes)
    cur = len(_in(signals, now - delta, now))
    prev = len(_in(signals, now - 2 * delta, now - delta))
    if cur + prev < MIN_SIGNALS_FOR_TREND:
        return "INSUFFICIENT" if cur + prev else "QUIET"
    ratio = cur / prev if prev else float("inf")
    if ratio >= RISE_RATIO:
        return "RISING"
    if ratio <= FALL_RATIO:
        return "FALLING"
    return "STABLE_HIGH" if cur >= 2 * MIN_SIGNALS_FOR_TREND else "STABLE"


def persistence_min(signals: list[Signal], now: datetime, minutes: int = 1440) -> float:
    """Minutos desde o primeiro até o último sinal da janela: há quanto tempo o assunto se sustenta."""
    ts = sorted(s.timestamp for s in _in(signals, now - timedelta(minutes=minutes), now))
    return round((ts[-1] - ts[0]).total_seconds() / 60, 1) if len(ts) >= 2 else 0.0


def trends(signals: list[Signal], now: datetime, duplicates_by_hash: dict[str, int] | None = None) -> dict:
    """Pacote completo: métricas de todas as janelas, estado da tendência (1 h) e persistência (24 h)."""
    return {
        "windows": [window_metrics(signals, now, m, duplicates_by_hash) for m in WINDOWS_MIN],
        "state": trend_state(signals, now),
        "persistence_min": persistence_min(signals, now),
    }
