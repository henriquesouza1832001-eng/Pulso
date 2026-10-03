"""Geolocalização V2 por gazetteer: localiza o MUNICÍPIO certo entre os 5.571 do IBGE (engine/data/br_municipalities.json).

Complementa `geo.py` (V1, que continua em produção e cobre ~150 cidades do interior): este módulo resolve QUALQUER município e
devolve `geo_precision`, `geo_confidence` e `geo_evidence`. Regras do prompt do dono: não inventar precisão, nunca posicionar
um município no centro da capital só porque é do mesmo estado, e preferir "não sei" a um chute. Atrás da flag GEO_V2.

Um nome só vira município quando há contexto de lugar (para não confundir "Serra", "Natal" ou "Bonito" com palavra comum):
- UF logo depois ("Itaúna, MG", "Itaúna (MG)", "Itaúna - MG", "Itaúna/MG"): contexto forte;
- preposição de lugar antes ("em", "na", "no", "de", "da", "do", "para", "a") e inicial MAIÚSCULA no texto original;
- nome com 2 ou mais palavras ("Ribeirão das Neves"): aceito com inicial maiúscula.
Nome que existe em vários estados ("Bom Jesus") só resolve com UF no texto, ou com a UF da fonte (jornal regional); sem isso,
só se um deles tiver pelo menos 5x a população do segundo E 100 mil habitantes, e com confiança menor.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .keyword_engine import _fold

DATA = Path(__file__).resolve().parents[2] / "data" / "br_municipalities.json"
PREPOSITIONS = frozenset({"em", "na", "no", "nas", "nos", "de", "da", "do", "das", "dos", "para", "pra", "a", "ao", "a", "ate"})
UFS = frozenset("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())
MAX_WORDS = 5
DOMINANCE = 5.0
DOMINANCE_MIN_POP = 100_000


@dataclass(frozen=True)
class GeoResolution:
    ibge_id: str
    city: str
    uf: str
    latitude: float
    longitude: float
    geo_precision: str  # sempre "CITY"
    geo_confidence: int  # 0-100
    geo_evidence: tuple[str, ...]
    ambiguous: bool = False  # a escolha dependeu só da população


@lru_cache(maxsize=1)
def _index(path: Path = DATA) -> dict[str, list[dict]]:
    """nome normalizado (e apelidos) -> municípios com esse nome."""
    idx: dict[str, list[dict]] = {}
    for row in json.loads(path.read_text(encoding="utf-8")):
        idx.setdefault(row["normalized_name"], []).append(row)
        for alias in row.get("aliases") or []:
            idx.setdefault(_fold(alias), []).append(row)
    return idx


_WORD = re.compile(r"[A-Za-zÀ-ÿ0-9']+")


def _tokens(text: str) -> list[tuple[str, str, int, int]]:
    """(original, dobrado, início, fim) de cada palavra."""
    return [(m.group(0), _fold(m.group(0)), m.start(), m.end()) for m in _WORD.finditer(text)]


def _uf_after(text: str, end: int) -> str | None:
    m = re.match(r"\s*(?:,|\(|/|-|–)\s*\(?([A-Z]{2})\b", text[end:end + 12])
    return m.group(1) if m and m.group(1) in UFS else None


def _capitalized(original: str) -> bool:
    return original[:1].isupper()


def resolve(text: str, source_state: str | None = None) -> GeoResolution | None:
    """Melhor município citado no texto, ou None. `source_state`: UF do veículo regional (fallback de desambiguação)."""
    if not text:
        return None
    toks = _tokens(text)
    idx = _index()
    all_caps = text.isupper()
    found: list[tuple[int, list[dict], int, str | None, bool]] = []  # (nº de palavras, entradas, início, UF no texto, tem preposição)
    for i in range(len(toks)):
        for n in range(min(MAX_WORDS, len(toks) - i), 0, -1):
            span = toks[i:i + n]
            entries = idx.get(" ".join(t[1] for t in span))
            if not entries:
                continue
            if not (all_caps or _capitalized(span[0][0])):
                continue  # nome de lugar com inicial minúscula é palavra comum ("a serra", "o natal")
            uf_ctx = _uf_after(text, span[-1][3])
            prep = i > 0 and toks[i - 1][1] in PREPOSITIONS
            if uf_ctx or prep or n >= 2:
                found.append((n, entries, span[0][2], uf_ctx, prep))
            break  # a janela mais longa que casou vence; não testa as menores a partir deste ponto
    if not found:
        return None
    # prefere: UF explícita, depois o nome mais longo, depois o que aparece primeiro
    found.sort(key=lambda f: (f[3] is None, -f[0], f[2]))
    n, entries, _, uf_ctx, prep = found[0]
    evidence = [f"município '{entries[0]['name']}' no texto" + (" com UF explícita" if uf_ctx else " com preposição de lugar" if prep else " (nome composto)")]
    pick, ambiguous = None, False
    if uf_ctx:
        same = [e for e in entries if e["uf"] == uf_ctx]
        pick = same[0] if same else None
        if pick:
            evidence.append(f"UF {uf_ctx} citada junto ao nome")
    if pick is None and len(entries) == 1:
        pick = entries[0]
    if pick is None and source_state:
        same = [e for e in entries if e["uf"] == source_state]
        if len(same) == 1:
            pick = same[0]
            evidence.append(f"UF da fonte regional ({source_state}) desambigua")
    if pick is None:
        ranked = sorted(entries, key=lambda e: -(e.get("population") or 0))
        top, second = ranked[0], ranked[1] if len(ranked) > 1 else None
        if second is not None and (top.get("population") or 0) >= DOMINANCE_MIN_POP and (top.get("population") or 0) >= DOMINANCE * max(1, second.get("population") or 0):
            pick, ambiguous = top, True
            evidence.append(f"homônimos em {len(entries)} estados; escolhido o de maior população ({top['uf']})")
        else:
            return None  # ambíguo de verdade: não chuta
    conf = 50
    conf += 25 if uf_ctx else 15 if prep else 10
    if source_state and pick["uf"] == source_state:
        conf += 10
        if "UF da fonte" not in " ".join(evidence):
            evidence.append(f"UF da fonte regional ({source_state}) confirma")
    if (pick.get("population") or 0) >= DOMINANCE_MIN_POP:
        conf += 5
    if ambiguous:
        conf -= 25
    if pick.get("coord_quality") != "centroid":
        conf -= 10
        evidence.append("coordenada aproximada (município sem malha no IBGE)")
    return GeoResolution(pick["ibge_id"], pick["name"], pick["uf"], pick["latitude"], pick["longitude"], "CITY",
                         max(5, min(95, conf)), tuple(evidence), ambiguous)
