"""Escalada de evento: P(o evento atingir nível superior dentro do horizonte), EXPERIMENTAL e em SHADOW.

Estatística empírica, sem LLM: usa o histórico de trajetórias de nível (nível observado em t e o máximo atingido até t+h)
dos eventos já vistos, agrupado por (categoria, nível atual). Probabilidade com Laplace (nunca 0 nem 1) e intervalo de Wilson.
Sem amostras suficientes no grupo, devolve `INSUFFICIENT_DATA`: não se inventa probabilidade. Nunca vira alerta sozinho
(alerta 4-5 não vem de previsão; AGENTS.md) e nasce atrás da flag `EVENT_ESCALATION`.
"""
from __future__ import annotations

from ..forecast import wilson

MIN_SAMPLES = 30
LABEL = "EXPERIMENTAL"


def build_history(trajectories: list[dict]) -> dict[tuple[str, int], list[int]]:
    """`trajectories`: {category, level_at_t, max_level_by_horizon}. Agrupa o desfecho (1 = subiu) por (categoria, nível)."""
    out: dict[tuple[str, int], list[int]] = {}
    for t in trajectories:
        out.setdefault((t["category"], int(t["level_at_t"])), []).append(int(t["max_level_by_horizon"] > t["level_at_t"]))
    return out


def p_escalation(history: dict[tuple[str, int], list[int]], category: str, level: int, min_samples: int = MIN_SAMPLES) -> dict:
    if level >= 5:
        return {"status": "NOT_APPLICABLE", "reason": "nível máximo", "label": LABEL}
    outcomes = history.get((category, level), [])
    n = len(outcomes)
    if n < min_samples:
        return {"status": "INSUFFICIENT_DATA", "samples": n, "label": LABEL, "probability": None}
    k = sum(outcomes)
    p = (k + 1) / (n + 2)
    lo, hi = wilson(k, n)
    return {"status": "OK", "probability": round(p, 4), "interval_low": round(min(lo, p), 4), "interval_high": round(max(hi, p), 4),
            "samples": n, "hits": k, "label": LABEL, "note": "taxa histórica de subida de nível; previsão, não fato"}
