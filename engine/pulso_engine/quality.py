"""Qualidade de dado por sinal: completeness, freshness, geo_quality e duplication_probability (0-1 cada).

Não decide nada sozinha: é insumo de confiança, deduplicação e do relatório de saúde dos dados. Determinística. Um sinal
sem data confiável ou sem título tem qualidade baixa; a geolocalização nunca recebe nota melhor que a precisão que tem.
"""
from __future__ import annotations

from datetime import datetime

from .models import Signal

_PRECISION_SCORE = {"POINT": 1.0, "STREET": 0.95, "NEIGHBORHOOD": 0.85, "CITY": 0.7, "STATE": 0.4, "COUNTRY": 0.1}
FRESH_HALF_LIFE_MIN = 180.0


def completeness(s: Signal) -> float:
    """Fração dos campos úteis presentes: título, texto, URL, categoria, lugar, autor/fonte."""
    fields = [bool(s.title), bool(s.text), bool(s.url), s.category != "OTHER", bool(s.state or s.city or s.latitude is not None), bool(s.source_id)]
    return round(sum(fields) / len(fields), 3)


def freshness(s: Signal, now: datetime) -> float:
    age = max(0.0, (now - s.timestamp).total_seconds() / 60)
    return round(0.5 ** (age / FRESH_HALF_LIFE_MIN), 3)


def geo_quality(s: Signal) -> float:
    """Precisão declarada x confiança da geo: sem lugar = 0; nunca acima da precisão da categoria de lugar."""
    if s.latitude is None and not (s.state or s.city):
        return 0.0
    base = _PRECISION_SCORE.get(s.geo_precision or ("CITY" if s.city else "STATE"), 0.4)
    return round(base * min(1.0, (s.geo_confidence if s.geo_confidence is not None else 50) / 70), 3)


def duplication_probability(s: Signal, duplicates_by_hash: dict[str, int] | None = None) -> float:
    """Probabilidade de o sinal ser cópia: cresce com as cópias já descartadas na dedup do MESMO hash (n / (n + 1))."""
    n = max(0, (duplicates_by_hash or {}).get(s.hash, 0))
    return round(n / (n + 1), 3)


def signal_quality(s: Signal, now: datetime, duplicates_by_hash: dict[str, int] | None = None) -> dict[str, float]:
    return {"completeness": completeness(s), "freshness": freshness(s, now), "geo_quality": geo_quality(s),
            "duplication_probability": duplication_probability(s, duplicates_by_hash)}
