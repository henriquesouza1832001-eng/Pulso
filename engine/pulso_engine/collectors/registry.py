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
from .news.gdelt import GdeltAdapter
from .official.bcb_ptax import BcbPtaxAdapter
from .official.idap_cap import IdapCapAdapter
from .official.inmet import InmetAdapter
from .official.inpe_fires import InpeFiresAdapter
from .official.usgs import UsgsAdapter
from .social.mastodon import MastodonAdapter
from .social.reddit import RedditAdapter
from .social.x import XAdapter

ADAPTERS: dict[str, Callable] = {
    "rss": RssAdapter,
    "reddit": RedditAdapter,
    "x": XAdapter,
    "inmet": InmetAdapter,
    "gdelt": GdeltAdapter,
    "mastodon": MastodonAdapter,
    "usgs": UsgsAdapter,
    "inpe_fires": InpeFiresAdapter,
    "bcb_ptax": BcbPtaxAdapter,
    "idap_cap": IdapCapAdapter,
}

# Adaptadores que buscam URLs com o `fetcher` injetado (os sociais usam requisições autenticadas próprias).
URL_FETCH_ADAPTERS = frozenset({"rss", "inmet", "inpe_fires", "bcb_ptax"})


def build_adapter(source: dict, keywords, fetcher, now):
    cls = ADAPTERS.get(source.get("adapter", ""))
    if cls is None:
        raise KeyError(f"adapter '{source.get('adapter')}' não registrado em collectors/registry.py")
    return cls(source, keywords, fetcher, now)
