"""Severidade V2: vetor de IMPACTO observado, nunca popularidade.

Dimensões (0-1 cada): dano físico, mobilidade, infraestrutura, alcance, extensão, duração, serviços e severidade oficial.
Cada uma vem de evidência no texto/metadados (padrões explícitos) e o resultado mostra o vetor, não só um número. Quantidade
de matérias ou de cópias NÃO entra. Sem evidência em nenhuma dimensão a severidade é baixa por definição (não se infla).
Atrás da flag `SEVERITY_V2`; o V1 (`events.stats_for`) não é alterado.
"""
from __future__ import annotations

import re

from ..models import Signal
from ..processing.keyword_engine import _fold

# dimensão -> (peso, padrões sobre texto dobrado). Pesos somam 100.
DIMENSIONS: dict[str, tuple[int, tuple[str, ...]]] = {
    "physical_harm": (25, (r"\bmort[oa]s?\b", r"\bmorre(u|m)\b", r"\bferid[oa]s?\b", r"vitimas?", r"desaparecid", r"\bdesabrigad", r"\bdesalojad", r"\bresgat")),
    "mobility": (15, (r"interdit", r"bloque", r"engarrafamento", r"transito parado", r"via fechada", r"voos? (cancelad|atrasad)", r"metro parado|trens? parad")),
    "infrastructure": (15, (r"desabament", r"rompiment", r"apagao", r"sem energia", r"sem agua", r"queda de (ponte|energia)", r"colapso")),
    "reach": (10, (r"\bbairros?\b", r"\bcidades?\b", r"\bmunicipios?\b", r"regiao metropolitana", r"estado inteiro", r"milhares", r"\bmil (pessoas|moradores|casas)")),
    "extent": (10, (r"\bquilometros?\b|\bkm\b", r"\bhectares?\b", r"\bfocos?\b", r"area (atingida|afetada)", r"varias (ruas|vias|casas)")),
    "duration": (5, (r"desde (ontem|a madrugada|domingo|segunda)", r"ha (horas|dias)", r"segundo dia", r"continua", r"sem previsao")),
    "services": (10, (r"hospital", r"escolas? (fechad|suspens)", r"aulas suspensas", r"sem atendimento", r"pronto[- ]socorro", r"upas?\b")),
    "official_severity": (10, ()),  # vem do metadado (fonte oficial EMERGENCY), não do texto
}
assert sum(w for w, _ in DIMENSIONS.values()) == 100
_COMPILED = {d: tuple(re.compile(p) for p in pats) for d, (_, pats) in DIMENSIONS.items()}


def _dimension(text: str, dim: str) -> float:
    hits = sum(1 for p in _COMPILED[dim] if p.search(text))
    return min(1.0, hits / 2)  # duas evidências distintas saturam a dimensão


def severity_v2(signals: list[Signal]) -> dict:
    """{'score': 0-100, 'vector': {dim: 0-1}, 'points': [...], 'evidence_dimensions': n}. Usa a MAIOR evidência de cada dimensão
    entre os sinais (uma matéria com vítimas basta; cem sem vítimas não somam)."""
    vector = {d: 0.0 for d in DIMENSIONS}
    for s in signals:
        text = _fold(f"{s.title}. {s.text or ''}")
        for d in vector:
            if d != "official_severity":
                vector[d] = max(vector[d], _dimension(text, d))
        if s.source_class == "OFFICIAL" and s.category == "EMERGENCY":
            vector["official_severity"] = 1.0
    points = [{"key": d, "label": d, "points": round(DIMENSIONS[d][0] * v)} for d, v in vector.items() if v > 0]
    points.sort(key=lambda p: -p["points"])
    return {"score": min(100, sum(p["points"] for p in points)), "vector": {d: round(v, 2) for d, v in vector.items()},
            "points": points, "evidence_dimensions": sum(1 for v in vector.values() if v > 0)}
