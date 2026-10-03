"""Validation engine do Sentinela: tenta CONFIRMAR, REFUTAR e CONTEXTUALIZAR uma investigação a partir dos sinais que a
originaram e das evidências da deep search. Determinístico, sem LLM.

Princípios (§21, §27, §28, §49):
- cópias da mesma matéria não são confirmações: títulos quase idênticos formam UM grupo;
- contradição não se resolve escolhendo a versão mais repetida: é REGISTRADA com quem diz o quê, e a versão oficial
  aparece à parte;
- rede social é sensor, nunca confirmação sozinha;
- o resultado sugere um estado e alimenta `EventStats.contradiction` e a confirmação oficial; não decide a verdade.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

from ..models import SOCIAL_CLASSES, Signal
from ..processing.clustering import tokens
from ..processing.keyword_engine import _fold
from .sentinel import Investigation

COPY_JACCARD = 0.8  # títulos com esta sobreposição de tokens são a mesma matéria republicada
MIN_INDEPENDENT_CONFIRMED = 3  # sem fonte oficial, confirmar exige 3 origens independentes...
MIN_TYPES_CONFIRMED = 2  # ...de ao menos 2 tipos de fonte, um deles não social

# (tema, lado A, lado B): pares de afirmações incompatíveis sobre o mesmo fato.
CLAIM_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("extensão do bloqueio", r"totalmente (fechad|interditad|bloquead)|bloqueio total|interdi\w+ total", r"bloqueio parcial|interdi\w+ parcial|uma faixa|liberad|trafego normal|normalizad"),
    ("vítimas", r"\bmortos?\b|\bmorre(u|m)\b|vitimas? fatais?|\bferidos?\b", r"sem vitimas|ninguem ferido|nao ha (mortos|feridos|vitimas)|nao houve (mortos|feridos|vitimas)"),
    ("situação do fogo/alagamento", r"fora de controle|sem controle|avanca|se espalha", r"controlad|extint|apagad|debelad|baixou|nivel (do rio )?(baixa|recua)"),
    ("energia/serviço", r"sem energia|sem luz|apagao|fora do ar", r"energia (restabelecid|normalizad)|servico (restabelecid|normalizad)|volta ao normal"),
)


@dataclass(frozen=True)
class Validation:
    event_candidate: str
    evidence: tuple[dict, ...]
    contradictions: tuple[dict, ...]
    official_confirmation: bool
    independent_sources: int
    source_types: int
    copy_ratio: float
    suggested_status: str
    contradiction_score: float  # 0-1, entra em EventStats.contradiction


def _origins(signals: list[Signal]) -> list[list[Signal]]:
    """Agrupa matérias quase idênticas (republicação): cada grupo vale UMA origem."""
    groups: list[tuple[frozenset[str], list[Signal]]] = []
    for s in signals:
        toks = tokens(s.title)
        for gtoks, members in groups:
            union = len(toks | gtoks)
            if union and len(toks & gtoks) / union >= COPY_JACCARD:
                members.append(s)
                break
        else:
            groups.append((toks, [s]))
    return [m for _, m in groups]


def find_contradictions(signals: list[Signal]) -> list[dict]:
    out = []
    folded = {s.hash: _fold(f"{s.title} {s.text or ''}") for s in signals}
    for topic, a, b in CLAIM_PAIRS:
        side_a = [s for s in signals if re.search(a, folded[s.hash])]
        side_b = [s for s in signals if re.search(b, folded[s.hash])]
        # um mesmo texto pode casar os dois lados ("sem feridos, mas 2 mortos" é outra história): só conta quem é de um lado só
        both = {s.hash for s in side_a} & {s.hash for s in side_b}
        side_a = [s for s in side_a if s.hash not in both]
        side_b = [s for s in side_b if s.hash not in both]
        if not side_a or not side_b:
            continue
        def pack(side: list[Signal]) -> dict:
            return {"sources": sorted({s.source_id for s in side}), "official": any(s.source_class == "OFFICIAL" for s in side),
                    "example": side[0].title}
        pa, pb = pack(side_a), pack(side_b)
        out.append({"topic": topic, "side_a": pa, "side_b": pb,
                    "official_side": "a" if pa["official"] and not pb["official"] else "b" if pb["official"] and not pa["official"] else None})
    return out


def _status(official: bool, contradictions: list[dict], independent: int, types: int, non_social: bool, current: str) -> str:
    if contradictions:
        return "DISPUTED"
    if official or (independent >= MIN_INDEPENDENT_CONFIRMED and types >= MIN_TYPES_CONFIRMED and non_social):
        return "CONFIRMED"
    if independent >= 2 and types >= 2:
        return "WAITING_CONFIRMATION"
    if independent >= 2:
        return "CORRELATING"
    return "INVESTIGATING" if current in ("NEW", "INVESTIGATING") else current


def validate(inv: Investigation, members: list[Signal], evidence_signals: list[Signal] | None = None) -> Validation:
    """`members`: sinais que originaram a investigação; `evidence_signals`: sinais achados pela deep search."""
    seen: dict[str, Signal] = {}
    for s in [*members, *(evidence_signals or [])]:
        seen.setdefault(s.hash, s)
    signals = list(seen.values())
    groups = _origins(signals)
    independent = len({s.source_id for g in groups for s in g[:1]}) if groups else 0
    classes = {s.source_class for s in signals}
    official = any(s.source_class == "OFFICIAL" for s in signals)
    non_social = bool(classes - SOCIAL_CLASSES)
    contradictions = find_contradictions(signals)
    copies = len(signals) - len(groups)
    # Fonte oficial que concorda com um dos lados não zera a disputa: a divergência fica registrada.
    status = _status(official, contradictions, independent, len(classes), non_social, inv.status)
    return Validation(
        event_candidate=f"{inv.category} em {inv.scope}", evidence=tuple(
            {"signal_hash": s.hash, "source_id": s.source_id, "source_class": s.source_class, "url": s.url, "title": s.title}
            for s in sorted(signals, key=lambda x: x.timestamp, reverse=True)[:30]),
        contradictions=tuple(contradictions), official_confirmation=official, independent_sources=independent,
        source_types=len(classes), copy_ratio=round(copies / len(signals), 3) if signals else 0.0,
        suggested_status=status, contradiction_score=min(1.0, len(contradictions) / 2),
    )


_FINAL = frozenset({"RESOLVING", "CLOSED"})


def apply_validation(inv: Investigation, v: Validation) -> Investigation:
    """Aplica o resultado à investigação. Investigação em encerramento (RESOLVING/CLOSED) não é reaberta pela validação."""
    if inv.status in _FINAL:
        return inv
    return replace(inv, status=v.suggested_status, official_confirmation=inv.official_confirmation or v.official_confirmation,
                   evidence_count=max(inv.evidence_count, len(v.evidence)))
