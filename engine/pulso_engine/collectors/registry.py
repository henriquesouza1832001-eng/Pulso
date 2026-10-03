"""Registro de coletores: `adapter` em config/sources.json -> classe.

Para criar uma fonte nova SEM mexer no pipeline:
1. Crie `collectors/<tipo>/<fonte>.py` com uma classe com o mesmo construtor do RssAdapter
   `(source, keywords, fetcher, now)` e o método `run() -> list[Signal]`.
2. Registre aqui com UMA linha em ADAPTERS.
3. Adicione a fonte em `config/sources.json` seguindo o protocolo (docs/COLLECTION_PROTOCOL.md).
"""
from __future__ import annotations

from typing import Callable

from .news.rss import RssAdapter

ADAPTERS: dict[str, Callable] = {
    "rss": RssAdapter,
    # "oficial-inmet": InmetAdapter,
    # "reddit": RedditAdapter,
}


def build_adapter(source: dict, keywords, fetcher, now):
    cls = ADAPTERS.get(source.get("adapter", ""))
    if cls is None:
        raise KeyError(f"adapter '{source.get('adapter')}' não registrado em collectors/registry.py")
    return cls(source, keywords, fetcher, now)
