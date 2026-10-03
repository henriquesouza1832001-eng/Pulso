"""Termos emergentes: palavras e entidades que crescem sem estar cadastradas ("Vilarinho +830%").

Compara a frequência relativa de cada unigrama/bigrama (e entidade) na janela RECENTE contra a janela de REFERÊNCIA,
com suavização de Laplace e um piso de ocorrências (um termo raro que aparece 2 vezes não é "+200%"). Estatística pura
(TF temporal), sem NLP pesado. Termos que já são keywords das famílias são marcados `known`: o interesse do Sentinela
está justamente no que NÃO está cadastrado.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..models import Signal
from ..processing.cluster_refine import entities
from ..processing.clustering import _STOP
from ..processing.keyword_engine import DEFAULT_PATH, _fold

RECENT_MIN = 60
REFERENCE_MIN = 24 * 60
MIN_RECENT = 4  # ocorrências na janela recente (em sinais distintos) para valer
MIN_SOURCES = 2  # em fontes distintas: um único veículo repetindo não é termo emergente
SCORE_SATURATION = 8.0  # razão de frequência >= 8x = score 1
_WORD = re.compile(r"[a-z0-9\-]{3,}")


@dataclass(frozen=True)
class EmergingTerm:
    term: str
    recent: int
    reference: int
    sources: int
    growth: float  # razão de frequência relativa (recente / referência), suavizada
    score: float  # 0-1
    known: bool  # já é keyword de alguma família


def _terms(s: Signal) -> set[str]:
    text = _fold(f"{s.title} {s.text or ''}")
    words = [w for w in _WORD.findall(text) if w not in _STOP and not w.isdigit()]
    grams = set(words) | {f"{a} {b}" for a, b in zip(words, words[1:])}
    return grams | {_fold(e) for e in entities(s.title)}


def _known() -> set[str]:
    families = json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))
    return {_fold(t) for terms in families.values() for t in terms}


def emerging_terms(signals: list[Signal], now: datetime, top: int = 10, min_score: float = 0.0) -> list[EmergingTerm]:
    """Termos em crescimento, do maior score ao menor. Sem sinais recentes ou sem referência: lista vazia."""
    recent_cut, ref_cut = now - timedelta(minutes=RECENT_MIN), now - timedelta(minutes=REFERENCE_MIN)
    recent = [s for s in signals if recent_cut < s.timestamp <= now]
    ref = [s for s in signals if ref_cut < s.timestamp <= recent_cut]
    if not recent or not ref:
        return []  # sem referência não se afirma crescimento (BASELINE INSUFICIENTE)
    rc, fc = Counter(), Counter()
    srcs: dict[str, set[str]] = {}
    for s in recent:
        for t in _terms(s):
            rc[t] += 1
            srcs.setdefault(t, set()).add(s.source_id)
    for s in ref:
        for t in _terms(s):
            fc[t] += 1
    known, out = _known(), []
    nr, nf = len(recent), len(ref)
    for t, n in rc.items():
        if n < MIN_RECENT or len(srcs[t]) < MIN_SOURCES:
            continue
        growth = ((n + 1) / (nr + 2)) / ((fc[t] + 1) / (nf + 2))
        score = max(0.0, min(1.0, (growth - 1) / (SCORE_SATURATION - 1)))
        if score > min_score:
            out.append(EmergingTerm(t, n, fc[t], len(srcs[t]), round(growth, 2), round(score, 3), t in known))
    out.sort(key=lambda e: (-e.score, -e.recent, e.term))
    return out[:top]
