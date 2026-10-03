"""Espelho Python dos contratos de packages/shared/src/contracts.ts.

Mudou aqui? Mude lá (e docs/api/API.md) no mesmo PR.

O lote de ingestão (IngestBatch) é montado como dict em pipeline.run_once; campo opcional
`catalog_complete`: true quando `sources` é o catálogo completo de fontes ativas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

Category = Literal[
    "SECURITY", "TRAFFIC", "WEATHER", "INFRASTRUCTURE", "PROTEST", "POLITICS",
    "ECONOMY", "HEALTH", "INTERNATIONAL", "TECH", "EVENT", "EMERGENCY", "OTHER",
]
SourceClass = Literal[
    "OFFICIAL", "NEWS_HIGH", "NEWS_REGIONAL", "TRAFFIC_PROVIDER",
    "SOCIAL_VERIFIED", "SOCIAL", "UNKNOWN",
]
EventStatus = Literal[
    "DETECTED", "DEVELOPING", "CONFIRMED", "STABLE", "RESOLVING", "RESOLVED", "DISPUTED",
]
GeoPrecision = Literal["COUNTRY", "STATE", "CITY", "NEIGHBORHOOD", "STREET", "POINT"]

SOCIAL_CLASSES: frozenset[str] = frozenset({"SOCIAL", "SOCIAL_VERIFIED"})


@dataclass(frozen=True)
class Signal:
    """Um sinal normalizado: o 'asteroide'."""

    signal_id: str
    source_id: str
    source_class: SourceClass
    timestamp: datetime  # sempre timezone-aware (UTC)
    collected_at: datetime
    title: str
    category: Category = "OTHER"
    text: str | None = None
    url: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    geo_precision: GeoPrecision | None = None
    geo_confidence: int | None = None
    reliability: int = 50
    event_id: str | None = None
    hash: str = ""
    canonical_url: str | None = None
    author: str | None = None
    state: str | None = None
    city: str | None = None


@dataclass
class EventStats:
    """Medidas de um evento (cluster de sinais) que alimentam confiança e Pulso."""

    severity: int  # 0-100
    signal_count: int
    independent_sources: int  # fontes distintas, já descontadas as cópias (dedup)
    source_classes: frozenset[str]
    newest_age_min: float
    persistence_min: float
    velocity_per_hour: float
    anomaly: float = 0.0  # 0-1 vs. baseline
    geo_reach: float = 0.0  # 0-1
    official_confirmation: bool = False
    geo_consistency: float = 0.5  # 0-1
    temporal_consistency: float = 0.5  # 0-1
    contradiction: float = 0.0  # 0-1
    duplicate_ratio: float = 0.0  # 0-1
    half_life_min: float = 90.0  # meia-vida do frescor (depende da categoria; ver scoring/pulse.py)
    extra: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class CameraPreview:
    """Espelho de `CameraPreview` em packages/shared/src/contracts.ts: prévia servida pelo PRÓPRIO provedor."""
    type: str  # "iframe" | "hls"
    url: str


@dataclass(frozen=True)
class CameraFeed:
    """Espelho de `CameraFeed` (GET /api/cameras). `preview=None` = só cartão-placeholder com o link de origem."""
    id: str
    label: str
    city: str
    state: str  # UF, ou "BR" para painéis nacionais
    provider: str
    attribution: str
    page_url: str
    preview: CameraPreview | None = None
    lat: float | None = None
    lon: float | None = None
