"""Forecast V2, P6-P9: taxa-base com prior sazonal hierárquico, probabilidade bruta, calibrador versionado, incerteza e abstenção.

Camada EXPERIMENTAL e em SHADOW, separada do `forecast_v2.py` (previsor do Pulso condicionado à hora). Consome o `Snapshot`
de `forecast_v2_features.py` e devolve probabilidade + incerteza + cobertura + status. Sem LLM, sem deep learning, sem modelo
treinado escondido: a probabilidade bruta é prior (taxa-base) + evidência com PESOS DE CONFIGURAÇÃO versionados (`MODEL_VERSION`).

- P6 taxa-base: evento raro não vira probabilidade alta só porque há sinais; prior com fallback hierárquico registrado
  (cidade/categoria/hora -> estado/categoria/hora -> nacional/categoria/hora -> nacional/categoria -> global);
- P7 calibração: `raw_probability` e `calibrated_probability` SEPARADAS; calibrador é artefato versionado (Platt, 1-D, regularizado),
  ajustado só com amostras anteriores ao corte, e só com >= MIN_CALIBRATION_SAMPLES (sem isotônica em amostra pequena);
- P8 incerteza: sobe com sensor ausente/parado, discordância, prior de pouca amostra e cobertura baixa;
- P9 abstenção `INSUFFICIENT_DATA` quando não há base para prever (nunca se fabrica probabilidade).
Probabilidade nunca 0 nem 1.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .forecast_v2_features import MISSING, STALE, UNAVAILABLE, Snapshot

MODEL_VERSION = "heuristic-1"
CONTEXT_VERSION = "none"
MIN_PRIOR_SAMPLES = 30
MIN_CALIBRATION_SAMPLES = 200
P_MIN, P_MAX = 0.02, 0.98
MIN_COVERAGE = 0.25
GLOBAL_RATE = 0.05  # último recurso: eventos relevantes são raros; nunca 0,5 de "não sei"

# pesos de evidência em log-odds (configuração versionada; NÃO aprendidos). Cada um é uma hipótese a medir por ablation.
WEIGHTS = {"anomaly_15m": 1.6, "acceleration_60m": 0.8, "independent_origins_60m": 0.7, "official_signal_60m": 1.2, "concordance": 0.9}


def _logit(p: float) -> float:
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def _clamp(p: float) -> float:
    return min(P_MAX, max(P_MIN, p))


@dataclass(frozen=True)
class Prior:
    rate: float
    level: str
    samples: int


def hierarchical_prior(outcomes_by_level: list[tuple[str, list[int]]], min_samples: int = MIN_PRIOR_SAMPLES) -> Prior:
    """`outcomes_by_level`: do mais específico ao mais geral (rótulo, desfechos 0/1). Usa o primeiro nível com amostra
    suficiente (suavização de Laplace) e REGISTRA qual; sem nenhum, taxa global fixa com nível `global`."""
    for label, outcomes in outcomes_by_level:
        if len(outcomes) >= min_samples:
            return Prior(round((sum(outcomes) + 1) / (len(outcomes) + 2), 4), label, len(outcomes))
    return Prior(GLOBAL_RATE, "global", 0)


def _evidence(s: Snapshot) -> dict[str, float]:
    f = s.features
    def val(name: str) -> float:
        return 0.0 if f[name].value is None else float(f[name].value)
    return {"anomaly_15m": min(1.0, val("anomaly_15m")), "acceleration_60m": max(0.0, min(1.0, val("acceleration_60m") / 15)),
            "independent_origins_60m": min(1.0, max(0.0, val("independent_origins_60m") - 1) / 4),
            "official_signal_60m": val("official_signal_60m"), "concordance": 1.0 if s.agreement["concordant"] else 0.0}


@dataclass(frozen=True)
class Calibrator:
    version: str
    method: str  # "platt"
    a: float
    b: float
    samples: int
    fit_until: str  # corte dos dados de ajuste (nunca depois do que se prevê)


def fit_platt(pairs: list[tuple[float, int]], fit_until: str, version: str, l2: float = 1.0, iters: int = 200) -> Calibrator | None:
    """Platt 1-D regularizado (Newton) sobre (probabilidade bruta, desfecho). None com amostra insuficiente: NÃO se calibra."""
    if len(pairs) < MIN_CALIBRATION_SAMPLES or len({o for _, o in pairs}) < 2:
        return None
    xs = [_logit(_clamp(p)) for p, _ in pairs]
    ys = [o for _, o in pairs]
    a, b = 1.0, 0.0
    for _ in range(iters):
        ps = [_sigmoid(a * x + b) for x in xs]
        ga = sum((p - y) * x for p, y, x in zip(ps, ys, xs)) + l2 * (a - 1.0)
        gb = sum(p - y for p, y in zip(ps, ys))
        haa = sum(p * (1 - p) * x * x for p, x in zip(ps, xs)) + l2
        hab = sum(p * (1 - p) * x for p, x in zip(ps, xs))
        hbb = sum(p * (1 - p) for p in ps) + 1e-6
        det = haa * hbb - hab * hab
        if abs(det) < 1e-12:
            break
        da, db = (hbb * ga - hab * gb) / det, (haa * gb - hab * ga) / det
        a, b = a - da, b - db
        if abs(da) + abs(db) < 1e-8:
            break
    return Calibrator(version, "platt", round(a, 6), round(b, 6), len(pairs), fit_until)


def apply_calibrator(raw: float, cal: Calibrator | None) -> float | None:
    return None if cal is None else _clamp(_sigmoid(cal.a * _logit(_clamp(raw)) + cal.b))


def uncertainty(s: Snapshot, prior: Prior) -> tuple[float, list[str]]:
    """0-1 e os motivos. Cada fator é aditivo e limitado; a soma satura em 1."""
    reasons, u = [], 0.0
    cov = s.coverage["ratio"]
    if cov is not None:
        u += 0.3 * (1 - cov)
        if cov < 0.5:
            reasons.append("cobertura de sensores baixa")
    if s.coverage["stale"]:
        u += 0.1
        reasons.append("sensor parado: " + ",".join(s.coverage["stale"]))
    if s.agreement["discordant"]:
        u += 0.2
        reasons.append("discordância: social sem sinal físico nem oficial")
    if prior.samples < MIN_PRIOR_SAMPLES:
        u += 0.2
        reasons.append("taxa-base sem amostra suficiente")
    missing = [n for n, f in s.features.items() if f.state in (MISSING, UNAVAILABLE)]
    if missing:
        u += min(0.2, 0.05 * len(missing))
        reasons.append("features ausentes: " + ",".join(sorted(missing)))
    if any(f.state == STALE for f in s.features.values()):
        u += 0.1
        reasons.append("evidência antiga")
    return round(min(1.0, u), 3), reasons


def abstention(s: Snapshot) -> str | None:
    """Motivo para NÃO prever, ou None. Sem fabricar probabilidade."""
    f = s.features
    if f["signals_60m"].state == UNAVAILABLE:
        return "snapshot sem dados visíveis no corte"
    if s.coverage["ratio"] is not None and s.coverage["ratio"] < MIN_COVERAGE:
        return f"cobertura de sensores {s.coverage['ratio']} < {MIN_COVERAGE}"
    if f["evidence_age_min"].state == STALE and f["signals_60m"].value == 0:
        return "dado parado: nenhuma evidência recente"
    if s.scope != "BR" and not s.scope.startswith("UF:"):
        return "escopo geográfico não suportado"
    return None


def missing_evidence_priorities(s: Snapshot) -> dict[str, str]:
    """O que mais reduziria a incerteza (sem inventar dado): sensores esperados ausentes/parados por prioridade."""
    out: dict[str, str] = {}
    for t in s.coverage["missing"] + s.coverage["stale"]:
        fam = "official" if t in ("official", "civil_defense") else "news" if t == "news" else "social" if t == "social" else t
        out[fam.upper()] = "HIGH" if t in s.coverage["missing"] and t not in ("news", "social") else "MEDIUM"
    if not s.features["official_signal_60m"].value:
        out.setdefault("OFFICIAL", "HIGH")
    out.setdefault("MORE_NEWS", "LOW")
    return out


def forecast(s: Snapshot, prior: Prior, calibrator: Calibrator | None = None) -> dict:
    reason = abstention(s)
    base = {"model_version": MODEL_VERSION, "feature_version": s.feature_version, "context_version": CONTEXT_VERSION,
            "calibrator_version": calibrator.version if calibrator else None, "prior_level": prior.level, "prior_rate": prior.rate,
            "prior_samples": prior.samples, "coverage": s.coverage["ratio"], "data_cutoff": s.data_cutoff, "snapshot_hash": s.hash}
    if reason is not None:
        return {**base, "status": "INSUFFICIENT_DATA", "probability": None, "raw_probability": None, "calibrated_probability": None,
                "uncertainty": None, "abstention_reason": reason, "contributions": [], "missing_evidence_priorities": missing_evidence_priorities(s)}
    ev = _evidence(s)
    contrib = {k: round(WEIGHTS[k] * v, 4) for k, v in ev.items()}
    raw = _clamp(_sigmoid(_logit(_clamp(prior.rate)) + sum(contrib.values())))
    cal = apply_calibrator(raw, calibrator)
    u, reasons = uncertainty(s, prior)
    p = cal if cal is not None else raw
    half = round(0.5 * u * min(p, 1 - p) * 2, 4)  # intervalo: mais largo com incerteza, e nunca cruza 0 nem 1
    status = "OK_CALIBRATED" if cal is not None else "UNCALIBRATED_EXPERIMENTAL"
    return {**base, "status": status, "probability": round(p, 4), "raw_probability": round(raw, 4),
            "calibrated_probability": None if cal is None else round(cal, 4), "uncertainty": u, "uncertainty_reasons": reasons,
            "interval_low": round(max(P_MIN, p - half), 4), "interval_high": round(min(P_MAX, p + half), 4), "abstention_reason": None,
            "contributions": sorted(({"group": k, "log_odds": v} for k, v in contrib.items() if v), key=lambda c: -c["log_odds"]),
            "missing_evidence_priorities": missing_evidence_priorities(s), "label": "EXPERIMENTAL"}
