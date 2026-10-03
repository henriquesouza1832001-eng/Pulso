"""History: contagens agregadas por hora x escopo x categoria x classe de fonte (docs/research/SPEC_01_HISTORY.md).

Função pura: sem rede, sem banco. Só horas FECHADAS são emitidas (a hora corrente é incompleta e continua vindo de
`series`), para que cada célula seja gravada uma vez e o orçamento de escrita do banco seja respeitado.
Só contagens: nenhum conteúdo de terceiros.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import Signal


def _hour(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_observations(signals: list[Signal], duplicates_by_hash: dict[str, int], now: datetime) -> list[dict]:
    """Uma linha por (escopo, categoria, classe de fonte, hora fechada) COM sinal.

    `duplicates_by_hash`: quantas cópias foram descartadas na dedup de cada sinal (chave = `Signal.hash`); as cópias
    contam na célula do sinal que ficou. Sinais `OTHER` ficam de fora, como em `series.build_series`.
    """
    current = _hour(now)
    acc: dict[tuple[str, str, str, datetime], dict] = {}
    for s in signals:
        if s.category == "OTHER":
            continue
        hour = _hour(s.timestamp)
        if hour >= current:
            continue
        dups = max(0, int(duplicates_by_hash.get(s.hash, 0)))
        scopes = ["BR"] + ([f"UF:{s.state}"] if s.state else [])
        for scope in scopes:
            cell = acc.setdefault((scope, s.category, s.source_class, hour), {"signals": 0, "sources": set(), "duplicates": 0})
            cell["signals"] += 1
            cell["sources"].add(s.source_id)
            cell["duplicates"] += dups
    return [
        {"scope": sc, "category": cat, "source_class": cls, "hour": _iso(h),
         "signals": v["signals"], "sources": len(v["sources"]), "duplicates": v["duplicates"]}
        for (sc, cat, cls, h), v in sorted(acc.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], kv[0][3]))
    ]
