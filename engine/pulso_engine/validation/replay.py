"""Replay determinístico e conservador para validação fora de produção.

O replay separa o instante em que algo ocorreu do instante em que o PULSO
poderia sabê-lo. Um item nunca é entregue antes de todos os seus timestamps
de disponibilidade conhecidos; isto privilegia não vazar futuro a simular um
sensor otimista demais.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterable, Mapping

_OUTCOME_KEYS = frozenset({"outcome", "resolved_at", "resolution"})


def _aware(value: datetime | None, name: str) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError(f"{name} deve ter timezone")
    return value


@dataclass(frozen=True)
class ReplayClock:
    """Relógio explícito: nenhum código de replay consulta a hora da máquina."""

    current_time: datetime

    def __post_init__(self) -> None:
        _aware(self.current_time, "current_time")

    def move_to(self, when: datetime) -> "ReplayClock":
        _aware(when, "when")
        if when < self.current_time:
            raise ValueError("o relógio de replay não pode voltar no tempo")
        return ReplayClock(when)


@dataclass(frozen=True)
class ReplayItem:
    """Fato ou atualização com seus tempos de ocorrência e disponibilidade."""

    item_id: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    event_time: datetime | None = None
    published_at: datetime | None = None
    observed_at: datetime | None = None
    fetched_at: datetime | None = None
    confirmed_at: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("event_time", "published_at", "observed_at", "fetched_at", "confirmed_at"):
            _aware(getattr(self, name), name)
        if not self.item_id:
            raise ValueError("item_id é obrigatório")

        # O observer recebe `payload` como feature observável. Desfecho e
        # resolução pertencem à avaliação posterior, nunca à inferência.
        forbidden = _OUTCOME_KEYS.intersection(str(key).lower() for key in self.payload)
        if forbidden:
            raise ValueError(f"payload de replay não pode conter desfecho/resolução: {', '.join(sorted(forbidden))}")

    @property
    def available_at(self) -> datetime | None:
        """Primeiro instante seguro de exposição ao motor.

        ``event_time`` descreve o mundo, não a descoberta. Quando há mais de
        uma marca de disponibilidade, usa-se a última: um item publicado mas
        só obtido depois não pode aparecer no replay antes do fetch.
        """
        known = [x for x in (self.published_at, self.observed_at, self.fetched_at, self.confirmed_at) if x is not None]
        return max(known) if known else None

    def visible_at(self, clock: ReplayClock) -> bool:
        available = self.available_at
        return available is not None and available <= clock.current_time


@dataclass(frozen=True)
class ReplayDataset:
    """Coleção imutável, com ordem estável inclusive para timestamps iguais."""

    name: str
    items: tuple[ReplayItem, ...]

    def __init__(self, name: str, items: Iterable[ReplayItem]):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "items", tuple(items))
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValueError("ReplayDataset requer item_id único")

    def timeline(self) -> tuple[datetime, ...]:
        return tuple(sorted({item.available_at for item in self.items if item.available_at is not None}))

    def visible(self, clock: ReplayClock) -> tuple[ReplayItem, ...]:
        return tuple(sorted((item for item in self.items if item.visible_at(clock)), key=lambda item: (item.available_at, item.item_id)))


ReplayObserver = Callable[[ReplayClock, tuple[ReplayItem, ...]], Any]


@dataclass(frozen=True)
class ReplayRunner:
    """Executa snapshots crescentes do dataset, sempre sem olhar o futuro."""

    dataset: ReplayDataset
    clock: ReplayClock

    def run(self, observer: ReplayObserver) -> tuple[Any, ...]:
        clock = self.clock
        results: list[Any] = []
        for when in self.dataset.timeline():
            if when < clock.current_time:
                continue
            clock = clock.move_to(when)
            results.append(observer(clock, self.dataset.visible(clock)))
        return tuple(results)
