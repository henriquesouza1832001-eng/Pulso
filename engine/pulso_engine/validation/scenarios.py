"""Datasets pequenos e determinísticos usados pelo laboratório de confiabilidade."""
from __future__ import annotations

from datetime import datetime, timezone

from .replay import ReplayDataset, ReplayItem


def normal_weekday() -> ReplayDataset:
    """Dia de controle: atividade rotineira, sem evento forçado nem confirmação."""
    t = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    return ReplayDataset("normal_weekday", (
        ReplayItem("routine-1", {"category": "WEATHER", "routine": True}, event_time=t, observed_at=t),
        ReplayItem("routine-2", {"category": "TRAFFIC", "routine": True}, event_time=t.replace(minute=15), observed_at=t.replace(minute=15)),
    ))
