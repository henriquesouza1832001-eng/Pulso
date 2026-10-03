"""Séries agregadas: contagem de sinais por escopo x categoria x janela de 5 min (pela data de PUBLICAÇÃO)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import Signal

BUCKET_MIN = 5


def bucket_start(dt: datetime, minutes: int = BUCKET_MIN) -> datetime:
    dt = dt.astimezone(timezone.utc)
    return dt.replace(minute=dt.minute - dt.minute % minutes, second=0, microsecond=0)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_series(signals: list[Signal], now: datetime, lookback: timedelta = timedelta(hours=6)) -> list[dict]:
    """Conta sinais por janela. Só janelas recentes: o feed não tem memória longa, então
    janelas antigas já teriam contagem incompleta (o Worker guarda o MAIOR valor já visto)."""
    cutoff = bucket_start(now - lookback)
    acc: dict[tuple[str, str, datetime], dict] = {}
    for s in signals:
        if s.category == "OTHER":
            continue  # séries por tema; sinais sem categoria não formam baseline útil
        b = bucket_start(s.timestamp)
        if b < cutoff:
            continue
        scopes = ["BR"] + ([f"UF:{s.state}"] if s.state else [])
        for scope in scopes:
            cell = acc.setdefault((scope, s.category, b), {"signals": 0, "sources": set()})
            cell["signals"] += 1
            cell["sources"].add(s.source_id)
    return [
        {"scope": sc, "category": cat, "bucket": _iso(b), "signals": v["signals"], "sources": len(v["sources"])}
        for (sc, cat, b), v in sorted(acc.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2]))
    ]
