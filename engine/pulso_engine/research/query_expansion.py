"""Query expansion: de uma anomalia (categoria + lugar + termos vistos) a consultas direcionadas, sem LLM.

Sinônimos vêm das famílias de `processing/keywords.json` (a mesma fonte do keyword engine, recarregável); o contexto
(lugar, entidades) restringe a consulta para reduzir falso positivo: "acidente" vira "acidente Venda Nova", nunca só
"acidente". Determinístico e com teto de consultas.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ..models import Signal
from ..processing.keyword_engine import DEFAULT_PATH, _fold

MAX_TERMS = 6
MAX_PLACES = 4
MAX_QUERIES = 12
SAFETY_TERMS = {"WEATHER": "defesa civil", "EMERGENCY": "defesa civil", "INFRASTRUCTURE": "defesa civil", "TRAFFIC": "interdição"}


@dataclass(frozen=True)
class Query:
    term: str
    place: str

    @property
    def text(self) -> str:
        return f"{self.term} {self.place}".strip()


def family_terms(category: str, path: Path = DEFAULT_PATH) -> list[str]:
    families = json.loads(path.read_text(encoding="utf-8"))
    return list(families.get(category, []))


def place_terms(scope: str, signals: list[Signal], limit: int = MAX_PLACES) -> list[str]:
    """Lugares mais citados nos sinais da investigação (cidade), mais a sigla da UF quando o escopo é estadual."""
    cities = Counter(s.city for s in signals if s.city)
    out = [c for c, _ in cities.most_common(limit)]
    if scope.startswith("UF:") and len(out) < limit:
        out.append(scope[3:])
    return out[:limit]


def seed_terms(category: str, signals: list[Signal], path: Path = DEFAULT_PATH) -> list[str]:
    """Termos da família que JÁ aparecem nos sinais (os mais frequentes primeiro): a investigação parte do que se viu."""
    text = _fold(" ".join(f"{s.title} {s.text or ''}" for s in signals))
    hits: Counter[str] = Counter()
    for term in family_terms(category, path):
        n = len(re.findall(rf"\b{re.escape(_fold(term))}\b", text))
        if n:
            hits[term] = n
    return [t for t, _ in hits.most_common(MAX_TERMS)]


def expand(category: str, places: list[str], seeds: list[str] | None = None, path: Path = DEFAULT_PATH,
           max_queries: int = MAX_QUERIES) -> list[Query]:
    """Consultas termo x lugar, intercaladas (cada lugar recebe os melhores termos antes de qualquer um receber todos).
    Sem lugar não há consulta: "acidente" sozinho seria ampla demais."""
    if not places:
        return []
    terms: list[str] = []
    for t in [*(seeds or []), *family_terms(category, path)]:
        if t not in terms:
            terms.append(t)
    terms = terms[:MAX_TERMS]
    extra = SAFETY_TERMS.get(category)
    if extra and extra not in terms:
        terms.append(extra)
    queries: list[Query] = []
    for t in terms:
        for p in places[:MAX_PLACES]:
            q = Query(t, p)
            if q not in queries:
                queries.append(q)
            if len(queries) >= max_queries:
                return queries
    return queries
