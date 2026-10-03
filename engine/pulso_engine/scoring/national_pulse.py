"""Pulso nacional V2: dispersão geográfica, número de estados, diversidade e persistência, explicável.

O V1 (`pipeline.aggregate`) é uma média ponderada dos 10 maiores eventos: um único evento muito forte e localizado pesa
igual a uma crise espalhada. O V2 pergunta também "quantos estados?", "quão distribuído?" e "quantos tipos de fonte?".
Entrada: eventos publicados (dicts com pulse, state, source_count, category, alert_level) ; saída com pontos (soma = score).
Atrás da flag `NATIONAL_PULSE_V2`; o V1 não é alterado.
"""
from __future__ import annotations

import math

WEIGHTS = (("intensity", "Intensidade dos eventos mais fortes", 50), ("states", "Número de estados afetados", 20),
           ("dispersion", "Dispersão entre estados (não concentrado em um)", 10), ("diversity", "Diversidade de categorias", 10),
           ("breadth", "Eventos relevantes (nível 2+)", 10))
assert sum(w for _, _, w in WEIGHTS) == 100
STATES_SATURATION = 8  # 8 estados com evento relevante = máximo
CATEGORIES_SATURATION = 4
BREADTH_SATURATION = 12


def _entropy_ratio(counts: list[int]) -> float:
    """Entropia normalizada (0 = tudo em um estado, 1 = uniforme)."""
    total = sum(counts)
    if total == 0 or len(counts) < 2:
        return 0.0
    ent = -sum(c / total * math.log(c / total) for c in counts if c)
    return ent / math.log(len(counts))


def national_pulse_v2(events: list[dict]) -> tuple[int, list[dict]]:
    relevant = [e for e in events if e.get("pulse", 0) >= 30]
    if not events:
        return 0, []
    top = sorted((e["pulse"] for e in events), reverse=True)[:10]
    weights = [len(top) - i for i in range(len(top))]
    intensity = sum(p * w for p, w in zip(top, weights)) / sum(weights) / 100
    per_state: dict[str, int] = {}
    for e in relevant:
        if e.get("state"):
            per_state[e["state"]] = per_state.get(e["state"], 0) + 1
    comp = {
        "intensity": min(1.0, intensity),
        "states": min(1.0, len(per_state) / STATES_SATURATION),
        "dispersion": _entropy_ratio(list(per_state.values())),
        "diversity": min(1.0, len({e.get("category") for e in relevant if e.get("category")}) / CATEGORIES_SATURATION),
        "breadth": min(1.0, len(relevant) / BREADTH_SATURATION),
    }
    points = [{"key": k, "label": label, "points": round(comp[k] * w)} for k, label, w in WEIGHTS]
    points = [p for p in points if p["points"] > 0]
    points.sort(key=lambda p: -p["points"])
    return min(100, sum(p["points"] for p in points)), points
