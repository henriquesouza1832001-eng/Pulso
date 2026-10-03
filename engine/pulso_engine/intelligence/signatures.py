"""Assinaturas de evento e grafo de sensores (config/event_signatures.json).

`sensor_of` traduz um sinal para um TIPO de sensor; `match_signature` diz, para um tipo de evento, quais estágios
(leading, concurrent, confirming) já foram observados e em que ordem. É correlação/assinatura, nunca causalidade: o
resultado entra como evidência no "POR QUE O PULSO DETECTOU ISSO?", não altera sozinho severidade nem confiança.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..models import Signal

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "event_signatures.json"
STAGES = ("leading", "concurrent", "confirming")

_CIVIL_DEFENSE_IDS = ("defesa-civil", "idap", "cemaden")


@lru_cache(maxsize=2)
def load_signatures(path: Path = DEFAULT_PATH) -> dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8"))["types"]


def sensor_of(s: Signal) -> str:
    """Tipo de sensor de um sinal (heurística transparente por classe, fonte e categoria)."""
    sid = s.source_id.lower()
    if s.source_class in ("SOCIAL", "SOCIAL_VERIFIED"):
        return "social"
    if any(k in sid for k in _CIVIL_DEFENSE_IDS):
        return "civil_defense"
    if s.source_class == "OFFICIAL":
        if "inpe" in sid and "queim" in sid:
            return "fire_detection"
        if "usgs" in sid:
            return "seismic"
        if "ons" in sid:
            return "energy_utility"
        if "inmet" in sid:
            return "rainfall" if s.category == "WEATHER" else "official"
        return "official"
    if s.source_class == "TRAFFIC_PROVIDER":
        return "traffic"
    return "news"


def match_signature(event_type: str, observed: list[tuple[str, float]]) -> dict:
    """`observed`: pares (tipo de sensor, instante em segundos) já vistos. Devolve estágios cobertos, o que falta e se a
    ordem esperada (leading antes de confirming) se verificou. Sem nada observado: cobertura 0, ordem desconhecida."""
    sig = load_signatures()[event_type]
    first: dict[str, float] = {}
    for sensor, t in observed:
        first[sensor] = min(t, first.get(sensor, t))
    seen = {st: sorted(x for x in sig[st] if x in first) for st in STAGES}
    missing = {st: sorted(x for x in sig[st] if x not in first) for st in STAGES}
    total = sum(len(sig[st]) for st in STAGES)
    lead_t = min((first[x] for x in seen["leading"]), default=None)
    conf_t = min((first[x] for x in seen["confirming"]), default=None)
    ordered = None if lead_t is None or conf_t is None else lead_t < conf_t
    return {"event_type": event_type, "coverage": round(sum(len(v) for v in seen.values()) / total, 3), "seen": seen,
            "missing": missing, "leading_before_confirming": ordered,
            "lead_seconds": None if not ordered else conf_t - lead_t}


def best_signature(observed: list[tuple[str, float]], category: str | None = None) -> dict | None:
    """Assinatura de maior cobertura (opcionalmente restrita à categoria). None se nada casar."""
    cands = [match_signature(t, observed) for t, sig in load_signatures().items() if category in (None, sig["category"])]
    cands = [c for c in cands if c["coverage"] > 0]
    return max(cands, key=lambda c: (c["coverage"], c["event_type"]), default=None)


def sensor_graph(path: Path = DEFAULT_PATH) -> dict[str, dict[str, int]]:
    """Arestas sensor -> sensor (leading -> concurrent -> confirming) com o número de assinaturas que as sustentam."""
    edges: dict[str, dict[str, int]] = {}
    for sig in load_signatures(path).values():
        for a_stage, b_stage in (("leading", "concurrent"), ("concurrent", "confirming"), ("leading", "confirming")):
            for a in sig[a_stage]:
                for b in sig[b_stage]:
                    edges.setdefault(a, {}).setdefault(b, 0)
                    edges[a][b] += 1
    return edges
