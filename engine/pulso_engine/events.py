"""Constrói eventos (e seus scores) a partir de clusters de sinais."""
from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime

from .models import EventStats, Signal, SOCIAL_CLASSES
from .processing.clustering import Cluster
from .processing.importance import assess
from .processing.normalizer import normalized_title
from .scoring.confidence import confidence
from .scoring.pulse import HALF_LIFE_BY_CATEGORY, HALF_LIFE_MIN, alert_level, pulse_score

IMPACT_WEIGHT = 0.3  # pontos de severidade por ponto de importância do texto (importance.assess: 0-100)

# Severidade-base por categoria (heurística inicial, a calibrar com dados reais).
BASE_SEVERITY = {
    "EMERGENCY": 70, "SECURITY": 60, "WEATHER": 55, "INFRASTRUCTURE": 55, "PROTEST": 45,
    "TRAFFIC": 40, "HEALTH": 45, "POLITICS": 35, "INTERNATIONAL": 35, "ECONOMY": 35, "OTHER": 15,
}


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def dominant_category(signals: list[Signal]) -> str:
    counts = Counter(s.category for s in signals if s.category != "OTHER")
    return counts.most_common(1)[0][0] if counts else "OTHER"


def stats_for(signals: list[Signal], now: datetime, anomaly: float = 0.0) -> EventStats:
    category = dominant_category(signals)
    sources = {s.source_id for s in signals}
    times = [s.timestamp for s in signals]
    titles = Counter(normalized_title(s.title) for s in signals)
    duplicates = sum(c - 1 for c in titles.values())
    last_hour = sum(1 for t in times if (now - t).total_seconds() <= 3600)
    # Severidade = base da categoria + corroboração (fontes) + IMPACTO DO TEXTO (mortes, desabamento... pesam mais
    # que um relato de rotina da mesma categoria). Ruído de entretenimento já vem com importância baixa.
    impact = max(assess(f"{s.title}. {s.text or ''}").score for s in signals)
    severity = BASE_SEVERITY.get(category, 15) + min(20, 4 * (len(sources) - 1)) + round(IMPACT_WEIGHT * impact)
    return EventStats(
        severity=min(100, severity),
        signal_count=len(signals),
        independent_sources=len(sources),
        source_classes=frozenset(s.source_class for s in signals),
        newest_age_min=max(0.0, (now - max(times)).total_seconds() / 60),
        persistence_min=(max(times) - min(times)).total_seconds() / 60,
        velocity_per_hour=float(last_hour),
        anomaly=anomaly,  # 0 enquanto o baseline não tiver histórico suficiente (não se inventa anomalia)
        geo_reach=0.0,
        official_confirmation=any(s.source_class == "OFFICIAL" for s in signals),
        geo_consistency=1.0 if len({s.state for s in signals if s.state}) <= 1 else 0.3,
        temporal_consistency=1.0 if len(signals) > 1 else 0.5,
        duplicate_ratio=duplicates / len(signals),
        half_life_min=HALF_LIFE_BY_CATEGORY.get(category, HALF_LIFE_MIN),
    )


def status_for(stats: EventStats) -> str:
    # Volume de relatos sociais não é confirmação independente.
    if stats.source_classes <= SOCIAL_CLASSES:
        return "DETECTED"
    if stats.official_confirmation or stats.independent_sources >= 3:
        return "CONFIRMED"
    if stats.independent_sources >= 2:
        return "DEVELOPING" if stats.newest_age_min <= 90 else "STABLE"
    return "DETECTED"


# Categorias em que UMA fonte, sozinha, já pode virar evento (se o texto for de impacto).
SINGLE_SOURCE_CATEGORIES = frozenset({"EMERGENCY", "WEATHER", "INFRASTRUCTURE", "HEALTH", "SECURITY", "TRAFFIC"})


def is_publishable(cluster: Cluster) -> bool:
    """Evita inundar o mapa. Vira evento: o que tem 2+ fontes independentes; o que vem de fonte OFICIAL com
    categoria; ou notícia isolada de categoria de impacto cujo TEXTO é de impacto (mortes, desabamento...).
    Uma matéria isolada de política/economia/internacional espera uma segunda fonte."""
    sigs = cluster.signals
    category = dominant_category(sigs)
    if len({s.source_id for s in sigs}) >= 2:
        return True
    if category == "OTHER":
        return False
    if any(s.source_class == "OFFICIAL" for s in sigs):
        return True
    return category in SINGLE_SOURCE_CATEGORIES and any(
        assess(f"{s.title}. {s.text or ''}").is_important() for s in sigs)


def event_place(sigs: list[Signal]) -> Signal | None:
    """Sinal que representa o lugar do evento: o estado MAIORITÁRIO (ponderado pela confiança da geo).
    Se os sinais se espalham por vários estados (pauta nacional), o evento fica sem lugar, e não em um
    estado arbitrário."""
    located = [s for s in sigs if s.state]
    if not located:
        return next((s for s in sigs if s.latitude is not None), None)
    weight: Counter[str] = Counter()
    for s in located:
        weight[s.state] += s.geo_confidence or 30  # type: ignore[index]
    top, w = weight.most_common(1)[0]
    if len(weight) >= 4 or w / sum(weight.values()) < 0.6:
        return None
    # Em um grupo de 4+ sinais, o lugar só vale se uma parte relevante deles o tem: um único sinal que cita um estado
    # (ou um estado herdado da fonte regional) em meio a vários sem lugar não faz de uma pauta nacional um evento local.
    # Grupos pequenos (1-3 sinais) são o caso comum de notícia local e podem ser definidos por um sinal só.
    if len(sigs) >= 4 and len(located) / len(sigs) < 0.4:
        return None
    candidates = [s for s in located if s.state == top]
    return max(candidates, key=lambda s: (s.latitude is not None, s.geo_confidence or 0))


def build_event(cluster: Cluster, now: datetime, anomaly: float = 0.0, event_id: str | None = None) -> dict:
    sigs = sorted(cluster.signals, key=lambda s: s.timestamp)
    stats = stats_for(sigs, now, anomaly)
    conf = confidence(stats)
    score, breakdown = pulse_score(stats)
    level = alert_level(score, conf, stats)
    located = event_place(sigs)
    first = sigs[0]
    # Id estável: reaproveita o de um evento já gravado; só gera novo se for uma história nova.
    event_id = event_id or "ev-" + hashlib.sha1(first.hash.encode()).hexdigest()[:12]
    best = max(sigs, key=lambda s: (s.source_class == "OFFICIAL", s.reliability, -s.timestamp.timestamp()))
    for s in cluster.signals:
        object.__setattr__(s, "event_id", event_id)
    return {
        "event_id": event_id,
        "title": best.title,
        "summary": best.text,
        "category": dominant_category(sigs),
        "status": status_for(stats),
        "latitude": located.latitude if located else None,
        "longitude": located.longitude if located else None,
        "geo_precision": located.geo_precision if located else None,
        "geo_confidence": located.geo_confidence if located else None,
        "state": located.state if located else None,
        "city": located.city if located else None,
        "severity": stats.severity,
        "confidence": conf,
        "pulse": score,
        "alert_level": level,
        "score_breakdown": breakdown,
        "signal_count": len(sigs),
        "source_count": stats.independent_sources,
        "detected_at": iso(first.timestamp),
        "updated_at": iso(max(s.timestamp for s in sigs)),
    }
