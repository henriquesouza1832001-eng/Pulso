"""Confiabilidade de sensor: desempenho OPERACIONAL de cada fonte por tipo de evento e geografia.

Mede o que a fonte fez no passado (precision: quantas detecções dela viraram evento confirmado; lead mediano: com quanta
antecedência ela apareceu; disponibilidade), não "verdade". Usa o limite INFERIOR de Wilson para precision: uma fonte com
3 acertos em 3 não vale mais que uma com 90 em 100. Com poucas observações o resultado é `INSUFFICIENT_DATA` e o peso neutro
(0,5): nunca se pune nem premia por amostra pequena. Entra como ajuste de peso de fonte (atrás de flag), nunca como filtro.
"""
from __future__ import annotations

import statistics

from ..forecast import wilson

MIN_OBSERVATIONS = 20
NEUTRAL = 0.5


def key(source_id: str, event_type: str, geography: str) -> tuple[str, str, str]:
    return (source_id, event_type, geography)


def summarize(observations: list[dict]) -> dict[tuple[str, str, str], dict]:
    """`observations`: {source_id, event_type, geography, confirmed (bool), lead_minutes (float|None), available (bool)}."""
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for o in observations:
        groups.setdefault(key(o["source_id"], o["event_type"], o["geography"]), []).append(o)
    out = {}
    for k, obs in sorted(groups.items()):
        n = len(obs)
        hits = sum(1 for o in obs if o["confirmed"])
        leads = [o["lead_minutes"] for o in obs if o["confirmed"] and o.get("lead_minutes") is not None]
        avail = sum(1 for o in obs if o.get("available", True)) / n
        enough = n >= MIN_OBSERVATIONS
        lo, _ = wilson(hits, n)
        out[k] = {"observations": n, "precision": round(hits / n, 4), "precision_lower": round(lo, 4) if enough else None,
                  "median_lead_min": round(statistics.median(leads), 1) if leads else None, "availability": round(avail, 4),
                  "status": "OK" if enough else "INSUFFICIENT_DATA", "weight": round(lo, 4) if enough else NEUTRAL}
    return out


def weight_for(summary: dict, source_id: str, event_type: str, geography: str) -> float:
    """Peso 0-1 de uma fonte para um tipo de evento/geografia; neutro (0,5) se desconhecida ou com pouca amostra."""
    return summary.get(key(source_id, event_type, geography), {}).get("weight", NEUTRAL)
