"""Constrói eventos (e seus scores) a partir de clusters de sinais."""
from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime

from .models import EventStats, Signal, SOCIAL_CLASSES
from .processing.clustering import Cluster
from . import flags
from .processing.importance import assess, context
from .processing.normalizer import normalized_title
from .scoring.confidence import confidence
from .scoring.pulse import HALF_LIFE_BY_CATEGORY, HALF_LIFE_MIN, alert_level, pulse_score

ROUTINE_SEVERITY_CAP = 20  # teto de severidade de um evento cujos textos são todos rotina de campanha (importance.ROUTINE)
IMPACT_WEIGHT = 0.3  # pontos de severidade por ponto de importância do texto (importance.assess: 0-100)
# NOISE_GATE: incidente operacional (metrô parado, sem internet, bloqueio, tumulto) pesa como um evento físico de nível B.
OPERATIONAL_BASE = 45
OPERATIONAL_IMPACT = 45
NOISE_GATE_MAX_LEVEL = 1  # teto de nível de agenda/esporte/serviço e de OTHER sem nenhum termo de impacto

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


def stats_for(signals: list[Signal], now: datetime, anomaly: float = 0.0, contradiction: float = 0.0) -> EventStats:
    category = dominant_category(signals)
    gate = flags.enabled("NOISE_GATE")
    sources = {s.source_id for s in signals}
    times = [s.timestamp for s in signals]
    titles = Counter(normalized_title(s.title) for s in signals)
    duplicates = sum(c - 1 for c in titles.values())
    last_hour = sum(1 for t in times if (now - t).total_seconds() <= 3600)
    prev_hour = sum(1 for t in times if 3600 < (now - t).total_seconds() <= 7200)
    independent = len(sources)
    if gate:
        # QA-003: repost social com o MESMO título não é evidência independente. Conta cada veículo não social, mais um
        # por título social distinto que não repete nenhuma manchete não social.
        non_social = {s.source_id for s in signals if s.source_class not in SOCIAL_CLASSES}
        news_titles = {normalized_title(s.title) for s in signals if s.source_class not in SOCIAL_CLASSES}
        social_titles = {normalized_title(s.title) for s in signals if s.source_class in SOCIAL_CLASSES} - news_titles
        independent = len(non_social) + len(social_titles)
        # QA-004: velocidade conta relatos distintos (veículo + manchete), não cópias da mesma fonte.
        def distinct(lo: float, hi: float) -> int:
            return len({(s.source_id, normalized_title(s.title)) for s in signals
                        if lo < (now - s.timestamp).total_seconds() <= hi})
        last_hour, prev_hour = distinct(-1, 3600), distinct(3600, 7200)
    # Severidade = base da categoria + corroboração (fontes) + IMPACTO DO TEXTO (mortes, desabamento... pesam mais
    # que um relato de rotina da mesma categoria). Ruído de entretenimento já vem com importância baixa.
    assessed = [assess(f"{s.title}. {s.text or ''}") for s in signals]
    impact = max(a.score for a in assessed)
    base = BASE_SEVERITY.get(category, 15)
    if gate and any(context(f"{s.title}. {s.text or ''}").operational for s in signals):
        base, impact = max(base, OPERATIONAL_BASE), max(impact, OPERATIONAL_IMPACT)  # QA-002
    severity = base + min(20, 4 * (independent - 1)) + round(IMPACT_WEIGHT * impact)
    if all(a.routine for a in assessed):  # comício, carreata, agenda de candidato: esperado e agendado, não é impacto
        severity = min(severity, ROUTINE_SEVERITY_CAP)
    return EventStats(
        severity=min(100, severity),
        signal_count=len(signals),
        independent_sources=independent,
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
        contradiction=max(0.0, min(1.0, contradiction)),  # 0-1, vem da validação do Sentinela (0 = nenhuma registrada)
        extra={"acceleration": float(last_hour - prev_hour)},
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


def is_noise(sigs: list[Signal]) -> bool:
    """NOISE_GATE (QA-001): agenda/esporte/serviço em TODOS os relatos, ou OTHER sem nenhum termo de impacto nem de
    incidente operacional. Volume de veículos sozinho não transforma isso em alerta."""
    texts = [f"{s.title}. {s.text or ''}" for s in sigs]
    ctx = [context(t) for t in texts]
    if all(c.scheduled for c in ctx):
        return True
    return (dominant_category(sigs) == "OTHER" and not any(c.operational for c in ctx)
            and max(assess(t).score for t in texts) == 0)


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


OFFICIAL_ALERT_FLOOR = 3  # piso do nível PULSO quando o órgão oficial declara risco EXTREMO


def build_event(cluster: Cluster, now: datetime, anomaly: float = 0.0, event_id: str | None = None,
                alert_sources: frozenset[str] = frozenset(), contradiction: float = 0.0) -> dict:
    sigs = sorted(cluster.signals, key=lambda s: s.timestamp)
    stats = stats_for(sigs, now, anomaly, contradiction)
    conf = confidence(stats)
    score, breakdown = pulse_score(stats)
    if stats.contradiction > 0:  # explícito no "POR QUE?": a divergência já está descontada da confiança, não do score
        breakdown = [*breakdown, {"key": "contradiction", "label": "Fontes divergem (reduz a confiança)", "points": 0}]
    level = alert_level(score, conf, stats)
    if flags.enabled("NOISE_GATE") and level > NOISE_GATE_MAX_LEVEL and is_noise(sigs):  # QA-001
        level = NOISE_GATE_MAX_LEVEL
        breakdown = [*breakdown, {"key": "noise_gate", "label": "Agenda/serviço sem impacto (teto nível 1)", "points": 0}]
    # Alerta OFICIAL de risco extremo (INMET "Grande Perigo", Defesa Civil "Extreme": o adaptador os classifica como
    # EMERGENCY) nunca fica abaixo de "Elevado": o próprio órgão já declarou o perigo, e o score ainda não enxerga isso
    # (anomalia só existe com 12 h de histórico). O piso é explícito no "POR QUE?" (0 pontos) e não altera o score.
    official_extreme = any(s.source_id in alert_sources and s.category == "EMERGENCY" for s in sigs)
    if official_extreme and level < OFFICIAL_ALERT_FLOOR:
        level = OFFICIAL_ALERT_FLOOR
        breakdown = [*breakdown, {"key": "official_alert", "label": "Alerta oficial de risco extremo (piso nível 3)", "points": 0}]
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
