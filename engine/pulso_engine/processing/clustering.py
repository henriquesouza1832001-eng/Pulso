"""Clusterização de sinais em eventos: similaridade textual + janela temporal.

Estado atual: recalculado a cada rodada a partir dos itens vigentes nos feeds (stateless).
Quando o Engine guardar sinais, a mesma função passa a receber o histórico.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import timedelta

from ..models import Signal
from .normalizer import normalized_title

_STOP = frozenset(
    """de da do das dos em no na nos nas um uma uns umas para por com sem sobre apos ate entre como mais
    menos que quem foi ser sao tem tera diz fala afirma pode deve vai contra desde ainda ja ao aos seu sua
    seus suas esta este essa esse nao sim""".split()
)

WINDOW = timedelta(hours=12)
JACCARD_MIN = 0.34
MIN_SHARED = 3
MIN_HIT_RATIO = 0.25  # fração dos membros com que a matéria nova deve se parecer (evita ligação em cadeia)
CONFIDENT_GEO = 60


def tokens(title: str) -> frozenset[str]:
    return frozenset(t for t in normalized_title(title).split() if len(t) >= 4 and t not in _STOP)


def similar(a: frozenset[str], b: frozenset[str]) -> bool:
    shared = len(a & b)
    if shared < MIN_SHARED:
        return False
    return shared / len(a | b) >= JACCARD_MIN or shared / min(len(a), len(b)) >= 0.6


@dataclass
class Cluster:
    signals: list[Signal] = field(default_factory=list)
    member_tokens: list[frozenset[str]] = field(default_factory=list)

    def add(self, s: Signal, toks: frozenset[str]) -> None:
        self.signals.append(s)
        self.member_tokens.append(toks)

    def matches(self, s: Signal, toks: frozenset[str]) -> bool:
        if abs(s.timestamp - self.signals[-1].timestamp) > WINDOW:
            return False
        # A mesma fonte publicando o mesmo assunto para UFs diferentes (ex.: um aviso do INMET por estado)
        # descreve eventos distintos: juntar apagaria estados do mapa.
        if s.state and any(m.source_id == s.source_id and m.state and m.state != s.state for m in self.signals):
            return False
        # Estados diferentes, ambos bem localizados (lugar explícito no texto): são acontecimentos distintos.
        if s.state and (s.geo_confidence or 0) >= CONFIDENT_GEO and any(
                m.state and m.state != s.state and (m.geo_confidence or 0) >= CONFIDENT_GEO for m in self.signals):
            return False
        # Semelhança com ALGUNS membros, não com qualquer um: senão pautas amplas (ex.: eleições) encadeiam
        # centenas de matérias diferentes em um só "evento".
        hits = sum(1 for m in self.member_tokens if similar(toks, m))
        return hits >= max(1, math.ceil(MIN_HIT_RATIO * len(self.member_tokens)))


def cluster_signals(signals: list[Signal]) -> list[Cluster]:
    clusters: list[Cluster] = []
    for s in sorted(signals, key=lambda x: x.timestamp):
        toks = tokens(s.title)
        target = next((c for c in clusters if c.matches(s, toks)), None)
        if target is None:
            target = Cluster()
            clusters.append(target)
        target.add(s, toks)
    return clusters
