"""Forecast V2, P0-P5: snapshot reproduzível de features com correção temporal, ausência explícita e cobertura de sensores.

Pipeline alvo (FORECAST_V2_BRIEF): EVENT STATE -> FEATURE SNAPSHOT -> FEATURE QUALITY/MISSINGNESS -> (modelo, calibrador, incerteza,
abstenção: passos seguintes). Este módulo é PURO e determinístico: mesmo cutoff + mesmos dados + mesma `feature_version` = mesmo
snapshot (mesmo hash). Regras que ele impõe:

- P0 correção temporal: nada com `timestamp` ou `collected_at` depois do `data_cutoff` entra (o que o replay do Codex verifica);
- P1 snapshot: só features existentes naquele instante, com versões e hash;
- P2 ausência nunca vira zero em silêncio: VALUE, VALUE_ZERO, MISSING, STALE, UNAVAILABLE, NOT_APPLICABLE;
- P3 cobertura de sensores: esperados x disponíveis x ausentes x parados (por tipo de evento, de `event_signatures.json`);
- P4 origem independente, não número de publishers (cópias = 1 origem);
- P5 concordância entre FAMÍLIAS independentes (físico, oficial, imprensa, social); discordância aumenta a INCERTEZA, não a probabilidade.

Sem modelo aqui: o snapshot só descreve o estado. Nada disto é causalidade.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from .anomaly_v2_bridge import window_anomaly_state
from .intelligence.signatures import load_signatures, sensor_of
from .intelligence.trends import persistence_min, window_metrics
from .models import Signal
from .research.validator import _origins

FEATURE_VERSION = "1"
VALUE, VALUE_ZERO, MISSING, STALE, UNAVAILABLE, NOT_APPLICABLE = "VALUE", "VALUE_ZERO", "MISSING", "STALE", "UNAVAILABLE", "NOT_APPLICABLE"
STALE_AFTER_MIN = 120  # um sensor sem sinal há mais que isto está PARADO (stale), não "zero"
SENSOR_WINDOW_MIN = 6 * 60

# família de sensor -> tipos de sensor (de signatures.sensor_of / event_signatures.json)
FAMILIES = {
    "physical": frozenset({"rainfall", "radar", "river_level", "traffic", "energy_utility", "seismic", "fire_detection", "airport", "internet_monitor", "cameras"}),
    "official": frozenset({"official", "civil_defense"}),
    "news": frozenset({"news"}),
    "social": frozenset({"social"}),
}


@dataclass(frozen=True)
class Feature:
    name: str
    value: float | None
    state: str
    age_min: float | None = None
    note: str | None = None

    def as_dict(self) -> dict:
        return {"name": self.name, "value": self.value, "state": self.state, "age_min": self.age_min, "note": self.note}


@dataclass(frozen=True)
class Snapshot:
    scope: str
    category: str
    event_type: str | None
    data_cutoff: str
    feature_version: str
    features: dict[str, Feature]
    coverage: dict
    agreement: dict
    excluded_future: int  # sinais descartados por serem posteriores ao cutoff (P0): visível, nunca silencioso

    def content(self) -> dict:
        return {"scope": self.scope, "category": self.category, "event_type": self.event_type, "data_cutoff": self.data_cutoff,
                "feature_version": self.feature_version, "features": {k: f.as_dict() for k, f in sorted(self.features.items())},
                "coverage": self.coverage, "agreement": self.agreement, "excluded_future": self.excluded_future}

    @property
    def hash(self) -> str:
        return hashlib.sha256(json.dumps(self.content(), sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def visible_signals(signals: list[Signal], cutoff: datetime) -> tuple[list[Signal], int]:
    """P0: só o que já existia E já tinha sido coletado no cutoff. Devolve (visíveis, quantos foram excluídos)."""
    seen = [s for s in signals if s.timestamp <= cutoff and s.collected_at <= cutoff]
    return seen, len(signals) - len(seen)


def _count_feature(name: str, n: int, have_coverage: bool) -> Feature:
    if not have_coverage:
        return Feature(name, None, UNAVAILABLE, note="sem cobertura da fonte/escopo")
    return Feature(name, float(n), VALUE if n else VALUE_ZERO)


def _scope_signals(signals: list[Signal], scope: str, category: str) -> list[Signal]:
    return [s for s in signals if s.category == category and (scope == "BR" or s.state == scope.removeprefix("UF:"))]


def sensor_coverage(signals: list[Signal], cutoff: datetime, event_type: str | None) -> dict:
    """P3: tipos de sensor esperados para o tipo de evento x o que apareceu (fresco), parou (stale) ou nunca apareceu."""
    if event_type is None or event_type not in load_signatures():
        return {"event_type": event_type, "expected": [], "available": [], "stale": [], "missing": [], "ratio": None,
                "status": NOT_APPLICABLE}
    sig = load_signatures()[event_type]
    expected = sorted({x for stage in ("leading", "concurrent", "confirming") for x in sig[stage]})
    last: dict[str, datetime] = {}
    for s in signals:
        if cutoff - s.timestamp <= timedelta(minutes=SENSOR_WINDOW_MIN):
            t = sensor_of(s)
            last[t] = max(last.get(t, s.timestamp), s.timestamp)
    avail = sorted(x for x in expected if x in last and cutoff - last[x] <= timedelta(minutes=STALE_AFTER_MIN))
    stale = sorted(x for x in expected if x in last and x not in avail)
    missing = sorted(x for x in expected if x not in last)
    return {"event_type": event_type, "expected": expected, "available": avail, "stale": stale, "missing": missing,
            "ratio": round(len(avail) / len(expected), 3), "status": VALUE}


def family_agreement(signals: list[Signal], cutoff: datetime, window_min: int = 60) -> dict:
    """P5: quais FAMÍLIAS independentes têm atividade recente. Concordância = >= 2 famílias; discordância = social ativo
    sem NENHUM sinal físico nem oficial (sobe a incerteza, não a probabilidade)."""
    recent = [s for s in signals if cutoff - s.timestamp <= timedelta(minutes=window_min)]
    active = {fam for fam, types in FAMILIES.items() if any(sensor_of(s) in types for s in recent)}
    return {"active_families": sorted(active), "n_families": len(active), "concordant": len(active) >= 2,
            "discordant": "social" in active and not (active & {"physical", "official"}),
            "uncertainty_hint": "SOCIAL_ONLY" if active == {"social"} else "SOCIAL_WITHOUT_PHYSICAL_OR_OFFICIAL" if "social" in active and not (active & {"physical", "official"}) else None}


def build_snapshot(signals: list[Signal], cutoff: datetime, scope: str, category: str, obs_rows: list[dict] | None = None,
                   event_type: str | None = None, duplicates_by_hash: dict[str, int] | None = None) -> Snapshot:
    seen, excluded = visible_signals(signals, cutoff)
    mine = _scope_signals(seen, scope, category)
    have = bool(seen)  # sem NENHUM sinal visível: contagens não são zero, são indisponíveis
    feats: dict[str, Feature] = {}
    for m in (5, 15, 60):
        w = window_metrics(mine, cutoff, m, duplicates_by_hash)
        feats[f"signals_{m}m"] = _count_feature(f"signals_{m}m", w.signal_count, have)
    w15, w60 = window_metrics(mine, cutoff, 15, duplicates_by_hash), window_metrics(mine, cutoff, 60, duplicates_by_hash)
    feats["acceleration_60m"] = Feature("acceleration_60m", w60.acceleration, VALUE if w60.acceleration else VALUE_ZERO) if have else Feature("acceleration_60m", None, UNAVAILABLE)
    feats["persistence_min"] = Feature("persistence_min", persistence_min(mine, cutoff), VALUE) if mine else Feature("persistence_min", None, MISSING, note="sem sinais do tema no escopo")
    # anomalia: sem baseline válido é MISSING (nunca 0): zero seria afirmar "normal" sem saber o que é normal
    an = window_anomaly_state(w15.signal_count, 15, obs_rows or [], scope, category, cutoff) if have else None
    if an is None or an["status"] == "BASELINE INSUFICIENTE":
        feats["anomaly_15m"] = Feature("anomaly_15m", None, MISSING, note="BASELINE INSUFICIENTE")
    else:
        feats["anomaly_15m"] = Feature("anomaly_15m", an["score"], VALUE if an["score"] else VALUE_ZERO, note=f"base {an['basis']}")
    # P4: origens independentes, não publishers
    recent = [s for s in mine if cutoff - s.timestamp <= timedelta(minutes=60)]
    groups = _origins(recent) if recent else []
    origins = len({s.source_id for g in groups for s in g[:1]})
    feats["independent_origins_60m"] = Feature("independent_origins_60m", float(origins), VALUE if origins else VALUE_ZERO) if have else Feature("independent_origins_60m", None, UNAVAILABLE)
    feats["copy_ratio_60m"] = Feature("copy_ratio_60m", round(1 - len(groups) / len(recent), 3) if recent else None, VALUE if recent else MISSING)
    feats["official_signal_60m"] = Feature("official_signal_60m", float(any(s.source_class == "OFFICIAL" for s in recent)), VALUE if have else UNAVAILABLE)
    last_age = (cutoff - max(s.timestamp for s in mine)).total_seconds() / 60 if mine else None
    feats["evidence_age_min"] = Feature("evidence_age_min", round(last_age, 1) if last_age is not None else None,
                                        (STALE if last_age is not None and last_age > STALE_AFTER_MIN else VALUE) if mine else MISSING, last_age)
    return Snapshot(scope, category, event_type, _iso(cutoff), FEATURE_VERSION, feats, sensor_coverage(seen, cutoff, event_type),
                    family_agreement(mine, cutoff), excluded)
