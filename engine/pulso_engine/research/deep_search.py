"""Deep search ORÇADO: pesquisa direcionada sobre as fontes JÁ cadastradas e coletadas (nada de fonte nova, nada de
raspagem, nada de motor de busca externo). Dispara só para investigações do Sentinela e respeita tetos por ciclo e por
investigação, mais um cache de consultas na rodada. Devolve evidências (sinais que casam com a consulta), nunca
conclusões: a validação é o passo seguinte.

Matriz de contexto (§56): uma anomalia de clima não ativa sensores sem relação (economia, política...).
É uma matriz de correlação/assinatura, não de causalidade.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..models import Signal
from ..processing.keyword_engine import _fold
from .query_expansion import Query, expand, place_terms, seed_terms
from .sentinel import Investigation

# categoria investigada -> categorias de sinal que podem servir de evidência
SENSOR_MATRIX: dict[str, frozenset[str]] = {
    "WEATHER": frozenset({"WEATHER", "TRAFFIC", "INFRASTRUCTURE", "EMERGENCY", "HEALTH"}),
    "TRAFFIC": frozenset({"TRAFFIC", "WEATHER", "PROTEST", "EMERGENCY", "INFRASTRUCTURE"}),
    "INFRASTRUCTURE": frozenset({"INFRASTRUCTURE", "WEATHER", "EMERGENCY", "TRAFFIC", "TECH"}),
    "EMERGENCY": frozenset({"EMERGENCY", "WEATHER", "INFRASTRUCTURE", "TRAFFIC", "SECURITY", "HEALTH"}),
    "SECURITY": frozenset({"SECURITY", "EMERGENCY", "PROTEST", "TRAFFIC"}),
    "PROTEST": frozenset({"PROTEST", "TRAFFIC", "SECURITY", "POLITICS"}),
    "HEALTH": frozenset({"HEALTH", "EMERGENCY", "WEATHER"}),
    "TECH": frozenset({"TECH", "INFRASTRUCTURE", "ECONOMY"}),
    "ECONOMY": frozenset({"ECONOMY", "POLITICS"}),
    "POLITICS": frozenset({"POLITICS", "ECONOMY", "PROTEST"}),
}


@dataclass
class DeepSearchBudget:
    """Tetos configuráveis. `max_queries_cycle` protege o tempo do ciclo (8 min) e o tráfego; o cache evita repetir."""
    max_queries_cycle: int = 40
    max_queries_investigation: int = 12
    lookback_min: int = 360
    used_cycle: int = 0
    cache: dict[str, list[dict]] = field(default_factory=dict)

    def remaining(self, used_by_investigation: int = 0) -> int:
        return max(0, min(self.max_queries_cycle - self.used_cycle, self.max_queries_investigation - used_by_investigation))


@dataclass(frozen=True)
class DeepSearchResult:
    investigation_id: str
    queries: tuple[str, ...]
    evidence: tuple[dict, ...]
    skipped_by_budget: int  # consultas planejadas que o teto cortou (visível: nada some em silêncio)


def _matches(q: Query, folded: str) -> bool:
    return all(re.search(rf"\b{re.escape(_fold(part))}\b", folded) for part in (q.term, q.place) if part)


def _evidence(s: Signal, q: Query) -> dict:
    return {"signal_hash": s.hash, "source_id": s.source_id, "source_class": s.source_class, "category": s.category,
            "url": s.url, "title": s.title, "timestamp": s.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"), "query": q.text}


def deep_search(inv: Investigation, pool: list[Signal], now: datetime, budget: DeepSearchBudget,
                members: list[Signal] | None = None) -> DeepSearchResult:
    """`pool`: sinais já coletados (janela de 24 h do pipeline). `members`: os sinais que originaram a investigação
    (de onde saem lugar e termos); sem lugar não se pesquisa."""
    known = set(inv.signal_hashes)
    members = members if members is not None else [s for s in pool if s.hash in known]
    queries = expand(inv.category, place_terms(inv.scope, members), seed_terms(inv.category, members))
    allowed = SENSOR_MATRIX.get(inv.category, frozenset())
    n = budget.remaining()
    run, skipped = queries[:n], max(0, len(queries) - n)
    cutoff = now - timedelta(minutes=budget.lookback_min)
    uf = inv.scope[3:] if inv.scope.startswith("UF:") else None
    candidates = [s for s in pool if s.hash not in known and s.timestamp >= cutoff and s.category in allowed
                  and (uf is None or s.state in (None, uf))]
    folded = {s.hash: _fold(f"{s.title} {s.text or ''}") for s in candidates}
    found: dict[str, dict] = {}
    for q in run:
        budget.used_cycle += 1
        hits = budget.cache.get(q.text)
        if hits is None:
            hits = [_evidence(s, q) for s in candidates if _matches(q, folded[s.hash])]
            budget.cache[q.text] = hits
        for e in hits:
            found.setdefault(e["signal_hash"], e)
    ordered = sorted(found.values(), key=lambda e: (e["timestamp"], e["signal_hash"]), reverse=True)
    return DeepSearchResult(inv.investigation_id, tuple(q.text for q in run), tuple(ordered), skipped)
