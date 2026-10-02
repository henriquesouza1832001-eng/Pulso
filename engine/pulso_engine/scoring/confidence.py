"""Confiança do evento (0-100). Independente de severidade.

confidence = base + diversidade de fontes + confirmação oficial + consistências
             - penalidade por contradição - penalidade por duplicatas
Só redes sociais ("sensor social") nunca passa de SOCIAL_ONLY_CAP.
"""
from __future__ import annotations

from ..models import SOCIAL_CLASSES, EventStats

SOCIAL_ONLY_CAP = 40


def confidence(s: EventStats) -> int:
    value = 10.0
    value += min(30, 10 * max(0, s.independent_sources - 1))  # fontes independentes
    value += min(20, 7 * max(0, len(s.source_classes) - 1))  # tipos de fonte diferentes
    value += 25 if s.official_confirmation else 0
    value += 10 * s.geo_consistency + 5 * s.temporal_consistency
    value -= 30 * s.contradiction
    value -= 20 * s.duplicate_ratio
    value = max(0.0, min(100.0, value))
    if s.source_classes and s.source_classes <= SOCIAL_CLASSES:
        value = min(value, SOCIAL_ONLY_CAP)
    return round(value)
