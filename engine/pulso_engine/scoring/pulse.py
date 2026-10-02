"""Pulso Score (0-100) explicável + nível PULSO 1-5.

Cada componente vira 0-1, é multiplicado pelo peso e vira PONTOS. A soma dos pontos é o score,
e a lista de pontos é exatamente o "POR QUE 87?" mostrado na interface.
"""
from __future__ import annotations

import math

from ..models import SOCIAL_CLASSES, EventStats
from .confidence import confidence

HALF_LIFE_MIN = 90.0  # decaimento temporal: após 90 min, a recência vale metade

# (chave, rótulo, peso). Pesos somam 100.
WEIGHTS: list[tuple[str, str, int]] = [
    ("severity", "Severidade", 20),
    ("confidence", "Confiança", 15),
    ("velocity", "Velocidade de sinais", 15),
    ("sources", "Diversidade de fontes", 15),
    ("anomaly", "Anomalia vs. baseline", 15),
    ("recency", "Recência", 10),
    ("persistence", "Persistência", 5),
    ("geo_reach", "Alcance geográfico", 5),
]
assert sum(w for _, _, w in WEIGHTS) == 100


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def decay(age_min: float, half_life: float = HALF_LIFE_MIN) -> float:
    """Peso temporal 0-1: 1 agora, 0,5 na meia-vida, tendendo a 0."""
    return math.exp(-math.log(2) * max(0.0, age_min) / half_life)


def components(s: EventStats, conf: int) -> dict[str, float]:
    return {
        "severity": _clamp01(s.severity / 100),
        "confidence": _clamp01(conf / 100),
        "velocity": _clamp01(s.velocity_per_hour / 30),
        "sources": _clamp01((s.independent_sources - 1) / 9) * 0.7 + _clamp01((len(s.source_classes) - 1) / 3) * 0.3,
        "anomaly": _clamp01(s.anomaly),
        "recency": decay(s.newest_age_min),
        "persistence": _clamp01(s.persistence_min / 120),
        "geo_reach": _clamp01(s.geo_reach),
    }


def pulse_score(s: EventStats) -> tuple[int, list[dict]]:
    """Retorna (score, breakdown). Os pontos do breakdown somam o score (após arredondamento)."""
    comp = components(s, confidence(s))
    breakdown = [
        {"key": k, "label": label, "points": round(comp[k] * w)} for k, label, w in WEIGHTS
    ]
    breakdown = [b for b in breakdown if b["points"] > 0]
    breakdown.sort(key=lambda b: -b["points"])
    return sum(b["points"] for b in breakdown), breakdown


def alert_level(score: int, conf: int, s: EventStats) -> int:
    """PULSO 1-5. O nível 5 exige fonte oficial + >=3 fontes independentes; social sozinho nunca passa de 3."""
    social_only = bool(s.source_classes) and s.source_classes <= SOCIAL_CLASSES
    if (
        score >= 90
        and conf >= 85
        and s.official_confirmation
        and s.independent_sources >= 3
        and not social_only
    ):
        return 5
    if score >= 75 and conf >= 70 and s.independent_sources >= 2 and not social_only:
        return 4
    if score >= 55 and conf >= 40:
        return 3
    if score >= 30:
        return 2
    return 1
