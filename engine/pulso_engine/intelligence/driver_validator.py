"""Validador de drivers: um indicador antecedente só afeta previsão se melhorar o Brier (e só com amostra suficiente).

`drivers.py` já mede correlação defasada e a usa como EVIDÊNCIA. Este módulo decide se um driver pode virar PARTE do
cálculo: compara o Brier da previsão COM e SEM o driver, rejeita correlação alta de amostra pequena (o "driver falso") e
mantém o estado no registro: CANDIDATE -> TESTING -> ACTIVE; ACTIVE -> DEGRADED quando piora; DISABLED é manual e vence tudo.
Correlação não é causa: o registro guarda a evidência estatística, não uma afirmação de causalidade.
"""
from __future__ import annotations

import math

from ..validation.metrics import brier

STATES = ("CANDIDATE", "TESTING", "ACTIVE", "DEGRADED", "DISABLED")
MIN_PAIRS_FOR_CORRELATION = 48  # horas distintas (mesmo piso de drivers.MIN_HOURS_WITH_DATA)
MIN_SAMPLES_TO_ACTIVATE = 100  # previsões resolvidas com e sem o driver
MIN_BRIER_GAIN = 0.05  # 5% de ganho
Z_CRIT = 2.576  # ~99% bilateral


def correlation_is_credible(r: float, n: int) -> bool:
    """Rejeita correlação sem sustentação: n pequeno ou |r| indistinguível de ruído (teste de Fisher z a ~99%)."""
    if n < MIN_PAIRS_FOR_CORRELATION or abs(r) >= 1.0:
        return abs(r) >= 1.0 and n >= MIN_PAIRS_FOR_CORRELATION
    z = math.atanh(abs(r)) * math.sqrt(n - 3)
    return z >= Z_CRIT


def evaluate(samples: list[tuple[float, float, int]]) -> dict:
    """`samples`: (p sem o driver, p com o driver, desfecho). Devolve Brier de cada lado, ganho relativo e n."""
    without = [(a, o) for a, _, o in samples]
    with_ = [(b, o) for _, b, o in samples]
    bw, bd = brier(without), brier(with_)
    return {"samples": len(samples), "brier_without": bw, "brier_with": bd,
            "gain": round(1 - bd / bw, 4) if bw else None}


def next_state(current: str, ev: dict, credible: bool) -> tuple[str, str]:
    """(novo estado, motivo). DISABLED nunca muda sozinho."""
    if current == "DISABLED":
        return "DISABLED", "desativado manualmente"
    if not credible:
        return ("DEGRADED" if current == "ACTIVE" else "CANDIDATE"), "correlação sem sustentação estatística"
    if ev["samples"] < MIN_SAMPLES_TO_ACTIVATE:
        return ("TESTING" if current in ("CANDIDATE", "TESTING") else current), f"amostras insuficientes ({ev['samples']} < {MIN_SAMPLES_TO_ACTIVATE})"
    gain = ev["gain"]
    if gain is not None and gain >= MIN_BRIER_GAIN:
        return "ACTIVE", f"Brier melhorou {gain:.1%} com o driver"
    if current == "ACTIVE":
        return "DEGRADED", f"ganho de Brier caiu para {gain}"
    return "TESTING", f"ganho de Brier insuficiente ({gain})"


def affects_forecast(state: str) -> bool:
    """Só um driver ACTIVE pode alterar a probabilidade; nos demais estados é, no máximo, evidência."""
    return state == "ACTIVE"


def registry_row(driver: str, target: str, scope: str, lag_hours: int, correlation: float, pairs: int,
                 samples: list[tuple[float, float, int]], current: str = "CANDIDATE") -> dict:
    """Linha do registro (migration 0010 `driver_registry`)."""
    ev = evaluate(samples)
    state, reason = next_state(current, ev, correlation_is_credible(correlation, pairs))
    return {"driver": driver, "target": target, "scope": scope, "lag_hours": lag_hours, "correlation": round(correlation, 3),
            "pairs": pairs, "samples": ev["samples"], "brier_without": ev["brier_without"], "brier_with": ev["brier_with"],
            "state": state, "reason": reason}
