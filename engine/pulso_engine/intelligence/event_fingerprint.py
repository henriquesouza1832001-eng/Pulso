"""Identidade estável de uma história além do título (fingerprint).

O título muda entre veículos e ao longo do dia; as ENTIDADES (nomes próprios, códigos de via), a categoria, o lugar e a
janela de tempo mudam muito menos. O fingerprint reúne esses elementos num conjunto comparável: duas versões da mesma
história têm fingerprints sobrepostos mesmo com títulos diferentes. Complementa o `event_id` estável do pipeline (que
depende dos sinais já gravados) e serve para reencontrar uma história que se fragmentou. Determinístico, sem NLP pesado.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta

from ..models import Signal
from ..processing.cluster_refine import entities
from ..processing.normalizer import fold

MIN_OVERLAP = 0.5  # fração das entidades da menor história que precisa coincidir
MAX_GAP = timedelta(hours=6)


@dataclass(frozen=True)
class Fingerprint:
    category: str
    state: str | None
    city: str | None
    entities: frozenset[str]
    start: object  # datetime do primeiro sinal
    end: object

    @property
    def key(self) -> str:
        """Hash curto e estável do conteúdo identitário (categoria + lugar + entidades ordenadas), sem a janela de tempo."""
        raw = "|".join([self.category, self.state or "", fold(self.city or ""), ",".join(sorted(self.entities))])
        return "fp-" + hashlib.sha1(raw.encode()).hexdigest()[:12]


def fingerprint(signals: list[Signal]) -> Fingerprint:
    ents: dict[str, int] = {}
    for s in signals:
        for e in entities(s.title):
            ents[e] = ents.get(e, 0) + 1
    # entidade citada por mais de um sinal (ou única, em histórias pequenas) é identitária; menções isoladas em grupo grande são ruído
    # o LUGAR já é comparado à parte: cidade como "entidade" faria duas notícias distintas da mesma cidade parecerem a mesma história
    places = {fold(s.city) for s in signals if s.city}
    keep = frozenset(e for e, n in ents.items() if e not in places and (n >= 2 or len(signals) <= 2))
    cats: dict[str, int] = {}
    for s in signals:
        cats[s.category] = cats.get(s.category, 0) + 1
    states = [s.state for s in signals if s.state]
    cities = [s.city for s in signals if s.city]
    times = [s.timestamp for s in signals]
    return Fingerprint(max(cats, key=lambda c: (cats[c], c)), max(set(states), key=states.count) if states else None,
                       max(set(cities), key=cities.count) if cities else None, keep, min(times), max(times))


def same_story(a: Fingerprint, b: Fingerprint) -> bool:
    """Mesma história? Mesma categoria, janelas próximas, lugar compatível e entidades suficientemente sobrepostas.
    Sem entidades em comum nunca é a mesma história (título parecido não basta)."""
    if a.category != b.category or a.category == "OTHER":
        return False
    gap = max(a.start, b.start) - min(a.end, b.end)
    if gap > MAX_GAP:
        return False
    if a.state and b.state and a.state != b.state:
        return False
    if a.city and b.city and fold(a.city) != fold(b.city):
        return False
    if not a.entities or not b.entities:
        return False
    overlap = len(a.entities & b.entities) / min(len(a.entities), len(b.entities))
    return overlap >= MIN_OVERLAP
