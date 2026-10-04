"""Clusterização v2: pós-passo que reúne grupos que contam a MESMA história com títulos diferentes.

O agrupamento por título (`clustering.py`, calibrado em coleta real) fica intacto. Este módulo olha para os grupos já
formados e funde dois deles quando, juntos, coincidem: mesma categoria, janela curta, lugar compatível (mesma cidade ou
coordenadas próximas), entidades compartilhadas e alguma semelhança textual. Corrige o caso conhecido de "a mesma
história em dois eventos" (BACKEND_STATUS, limitação 3) sem inventar ligações: na dúvida NÃO funde.

Determinístico, sem dependência nova (DBSCAN/embeddings só se uma medição mostrar ganho; ADR 0009).
"""
from __future__ import annotations

import math
import re
from datetime import timedelta

from ..models import Signal
from .clustering import CONFIDENT_GEO, Cluster, tokens
from .normalizer import fold

MAX_GAP = timedelta(hours=3)
MAX_KM = 15.0
MIN_SHARED_ENTITIES = 1
MIN_TEXT = 0.12  # semelhança textual mínima (bem abaixo do 0,34 do agrupamento por título)
MERGE_SCORE = 0.6
MAX_CLUSTER = 40  # nunca forma um grupo gigante por encadeamento

_ENTITY = re.compile(r"\b(?:[A-Z]{2,3}[- ]?\d{2,4}|[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ]+)*)\b")
_DATELINE = re.compile(r"^[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ]+)*\s*(?::|\s[-–]\s)")
_COMMON = frozenset({"governo", "prefeitura", "policia", "brasil", "estado", "ministerio", "defesa", "civil", "veja", "saiba"})


def entities(title: str) -> frozenset[str]:
    """Nomes próprios e códigos (BR-381) do título, sem a primeira palavra (maiúscula só por começar a frase).
    Exceção: dateline ("Petrópolis: chuva provoca...", "Recife - ..."): ali a primeira palavra É o lugar (QA-005)."""
    if _DATELINE.match(title):
        body = title
    else:
        body = title.split(" ", 1)[1] if " " in title else ""
    found = {fold(m.group(0)) for m in _ENTITY.finditer(body)}
    return frozenset(e for e in found if e not in _COMMON and len(e) >= 3)


def haversine_km(a: Signal, b: Signal) -> float | None:
    if None in (a.latitude, a.longitude, b.latitude, b.longitude):
        return None
    p1, p2 = math.radians(a.latitude), math.radians(b.latitude)
    dphi, dl = p2 - p1, math.radians(b.longitude - a.longitude)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def geo_affinity(a: Signal, b: Signal) -> float | None:
    """1 = mesmo lugar (cidade igual ou coordenadas a <= 15 km); 0,5 = mesmo estado; None = incompatível (veto)."""
    km = haversine_km(a, b)
    if km is not None:
        return 1.0 if km <= MAX_KM else None
    if a.city and b.city and fold(a.city) == fold(b.city):
        return 1.0
    if a.state and b.state:
        if a.state != b.state:
            both_sure = (a.geo_confidence or 0) >= CONFIDENT_GEO and (b.geo_confidence or 0) >= CONFIDENT_GEO
            return None if both_sure else 0.0
        return 0.5
    return 0.0


def pair_score(a: Signal, b: Signal) -> float:
    """0-1; 0 quando há veto (categoria diferente, janela longa, lugares incompatíveis ou nenhuma entidade em comum)."""
    if a.category != b.category or a.category == "OTHER" or abs(a.timestamp - b.timestamp) > MAX_GAP:
        return 0.0
    geo = geo_affinity(a, b)
    if geo is None or geo < 0.5:
        return 0.0
    shared = len(entities(a.title) & entities(b.title))
    if shared < MIN_SHARED_ENTITIES:
        return 0.0
    ta, tb = tokens(a.title), tokens(b.title)
    text = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    if text < MIN_TEXT:
        return 0.0
    return round(0.4 * geo + 0.3 * min(1.0, shared / 2) + 0.3 * min(1.0, text / 0.34), 3)


def cluster_score(x: Cluster, y: Cluster) -> float:
    """Melhor par entre os dois grupos (qualquer par basta como ponte, mas o par precisa passar em TODOS os vetos)."""
    return max((pair_score(a, b) for a in x.signals for b in y.signals), default=0.0)


def refine_clusters(clusters: list[Cluster]) -> list[Cluster]:
    """Funde pares de grupos com score >= MERGE_SCORE (do maior para o menor), respeitando MAX_CLUSTER. Os grupos
    resultantes mantêm a ordem de entrada; o primeiro grupo é o que sobrevive (preserva ids de evento por `choose_event_id`)."""
    groups = list(clusters)
    while True:
        best: tuple[float, int, int] | None = None
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                if len(groups[i].signals) + len(groups[j].signals) > MAX_CLUSTER:
                    continue
                score = cluster_score(groups[i], groups[j])
                if score >= MERGE_SCORE and (best is None or score > best[0]):
                    best = (score, i, j)
        if best is None:
            return groups
        _, i, j = best
        for s, t in zip(groups[j].signals, groups[j].member_tokens):
            groups[i].add(s, t)
        del groups[j]
