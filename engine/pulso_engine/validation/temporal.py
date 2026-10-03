"""Splits temporais puros para avaliação científica, sem embaralhar o futuro no passado."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class TemporalSplit:
    """Índices [início, fim) de treino, calibração e teste consecutivos."""

    train: tuple[int, int]
    calibration: tuple[int, int]
    test: tuple[int, int]


def _validate_times(times: Sequence[datetime]) -> None:
    if any(value.tzinfo is None for value in times):
        raise ValueError("splits temporais requerem timestamps com timezone")
    if any(later <= earlier for earlier, later in zip(times, times[1:])):
        raise ValueError("timestamps devem estar em ordem estritamente crescente")


def walk_forward_splits(times: Sequence[datetime], *, train_size: int, calibration_size: int,
                        test_size: int, step: int | None = None) -> tuple[TemporalSplit, ...]:
    """Janelas móveis train → calibration → test, sem observação compartilhada.

    A função só cria a geometria da avaliação; o chamador decide features e
    calibrador usando exclusivamente os intervalos recebidos.
    """
    if min(train_size, calibration_size, test_size) <= 0:
        raise ValueError("todos os tamanhos devem ser positivos")
    _validate_times(times)
    width = train_size + calibration_size + test_size
    stride = step if step is not None else test_size
    if stride <= 0:
        raise ValueError("step deve ser positivo")
    splits: list[TemporalSplit] = []
    for start in range(0, len(times) - width + 1, stride):
        train_end = start + train_size
        calibration_end = train_end + calibration_size
        splits.append(TemporalSplit((start, train_end), (train_end, calibration_end), (calibration_end, calibration_end + test_size)))
    return tuple(splits)


def final_holdout(times: Sequence[datetime], *, holdout_size: int) -> tuple[int, int]:
    """Reserva o trecho final, que não pode orientar seleção/calibração/tuning."""
    if holdout_size <= 0 or holdout_size >= len(times):
        raise ValueError("holdout deve ser positivo e menor que o dataset")
    _validate_times(times)
    return len(times) - holdout_size, len(times)
