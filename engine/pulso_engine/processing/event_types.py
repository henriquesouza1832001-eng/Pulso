"""Catálogo de tipos de evento e precursores (config/event_types.json).

Classifica o texto de um evento em tipos ("chuva extrema", "operação policial", "embaixada fechando"...) e, dado o que
está acontecendo AGORA, lista os tipos ativos que a hipótese editorial diz que costumam elevar o volume de uma categoria.
Isso vira EVIDÊNCIA da previsão ("por que esta previsão?"); não altera a probabilidade enquanto um backtest com dados
reais não provar ganho (docs/architecture/PREDICTION.md). O indicador do PULSO mostra só o momento atual.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from .keyword_engine import _fold

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "event_types.json"


@lru_cache(maxsize=4)
def load_types(path: Path = DEFAULT_PATH) -> tuple[dict, ...]:
    types = json.loads(path.read_text(encoding="utf-8"))["types"]
    out = []
    for t in types:
        pats = [re.compile(rf"(?<![a-z0-9]){re.escape(_fold(term))}(?![a-z0-9])") for term in t["terms"]]
        out.append({**t, "_pats": tuple(pats)})
    return tuple(out)


def classify(text: str, path: Path = DEFAULT_PATH) -> list[str]:
    """Ids dos tipos cujos termos aparecem no texto (um texto pode ter mais de um tipo)."""
    folded = _fold(text)
    return [t["id"] for t in load_types(path) if any(p.search(folded) for p in t["_pats"])]


def active_precursors(events: Iterable[dict], target_category: str, scope: str, path: Path = DEFAULT_PATH) -> list[dict]:
    """Tipos ativos agora (nos `events` publicados) que a hipótese diz que elevam `target_category`.

    `events`: dicts com `title`, `state` e `alert_level`. `scope`: "BR" (todos os eventos) ou "UF:XX" (só aquele estado).
    Ordena pelo número de eventos e devolve no máximo 3, para a evidência não virar lista infinita.
    """
    by_id = {t["id"]: t for t in load_types(path)}
    counts: dict[str, int] = {}
    for e in events:
        if scope != "BR" and f"UF:{e.get('state')}" != scope:
            continue
        for tid in classify(str(e.get("title", "")), path):
            counts[tid] = counts.get(tid, 0) + 1
    out = []
    for tid, n in counts.items():
        t = by_id[tid]
        if target_category in t["raises"]:
            out.append({"type": tid, "name": t["name"], "events": n, "lead_hours": t["lead_hours"], "status": "hipótese a validar"})
    out.sort(key=lambda d: -d["events"])
    return out[:3]
