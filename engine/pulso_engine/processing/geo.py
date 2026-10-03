"""Geolocalização por gazetteer (capitais e estados). Não inventa precisão: só CITY ou STATE.

Ruas, bairros e pontos exigem geocodificador próprio (fase seguinte).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .normalizer import fold


@dataclass(frozen=True)
class Place:
    uf: str
    city: str | None
    lat: float
    lon: float
    precision: str  # CITY | STATE
    confidence: int


# (UF, estado, capital, lat, lon da capital)
_STATES = [
    ("AC", "Acre", "Rio Branco", -9.97, -67.81), ("AL", "Alagoas", "Maceió", -9.67, -35.74),
    ("AP", "Amapá", "Macapá", 0.03, -51.07), ("AM", "Amazonas", "Manaus", -3.12, -60.02),
    ("BA", "Bahia", "Salvador", -12.97, -38.50), ("CE", "Ceará", "Fortaleza", -3.73, -38.52),
    ("DF", "Distrito Federal", "Brasília", -15.79, -47.88), ("ES", "Espírito Santo", "Vitória", -20.32, -40.34),
    ("GO", "Goiás", "Goiânia", -16.68, -49.25), ("MA", "Maranhão", "São Luís", -2.53, -44.30),
    ("MT", "Mato Grosso", "Cuiabá", -15.60, -56.10), ("MS", "Mato Grosso do Sul", "Campo Grande", -20.47, -54.62),
    ("MG", "Minas Gerais", "Belo Horizonte", -19.92, -43.94), ("PA", "Pará", "Belém", -1.46, -48.50),
    ("PB", "Paraíba", "João Pessoa", -7.12, -34.86), ("PR", "Paraná", "Curitiba", -25.43, -49.27),
    ("PE", "Pernambuco", "Recife", -8.05, -34.88), ("PI", "Piauí", "Teresina", -5.09, -42.80),
    ("RJ", "Rio de Janeiro", "Rio de Janeiro", -22.91, -43.17), ("RN", "Rio Grande do Norte", "Natal", -5.79, -35.21),
    ("RS", "Rio Grande do Sul", "Porto Alegre", -30.03, -51.23), ("RO", "Rondônia", "Porto Velho", -8.76, -63.90),
    ("RR", "Roraima", "Boa Vista", 2.82, -60.67), ("SC", "Santa Catarina", "Florianópolis", -27.59, -48.55),
    ("SP", "São Paulo", "São Paulo", -23.55, -46.63), ("SE", "Sergipe", "Aracaju", -10.91, -37.07),
    ("TO", "Tocantins", "Palmas", -10.18, -48.33),
]

# Nomes que coincidem com palavras comuns exigem contexto ("em Natal" casa; "natal" festa não).
_AMBIGUOUS_CITY = {"Natal", "Palmas", "Vitória", "Salvador", "Recife"}

# Estados cujo nome, sem acento e minúsculo, vira palavra comum. Regras próprias (padrão, aplicado ao
# texto ORIGINAL, e se é sensível a maiúsculas/acento):
#   Pará  -> "para" (preposição): só casa "Pará" com acento e maiúscula;
#   Acre  -> "acre" (unidade de área, adjetivo): só com contexto ("no Acre", "governo do Acre");
#   Espírito Santo -> termo religioso: só com contexto geográfico.
_CONTEXT = r"(?:no|na|do|da|ao|em|pelo|pelos|estado d[oe]|governo d[oe]|capital d[oe]|prefeitura d[oe]|policia d[oe])"
_SPECIAL_STATES: dict[str, tuple[str, int]] = {
    "PA": (r"\bPará\b", 0),  # sensível a maiúsculas e ao acento
    "AC": (rf"\b{_CONTEXT}\s+Acre\b", re.IGNORECASE),
    # "do/da Espírito Santo" é quase sempre religioso (missa, igreja): só contextos geográficos inequívocos.
    "ES": (r"\b(?:no|ao|em|pelo|estado d[oe]|governo d[oe]|prefeitura d[oe]|policia d[oe])\s+Espírito\s+Santo\b", re.IGNORECASE),
}
# Cidade cujo nome homônimo existe fora do Brasil: ignorada se o texto indicar o outro contexto.
_CITY_EXCLUDE: dict[str, re.Pattern[str]] = {
    "Belém": re.compile(r"cisjord|israel|palestin|gaza|jesus|presepio|natividade"),
}

# (padrão, lugar, aplica ao texto original?)
_PATTERNS: list[tuple[re.Pattern[str], Place, bool]] = []
for _uf, _state, _capital, _lat, _lon in _STATES:
    _pat = re.escape(fold(_capital))
    if _capital in _AMBIGUOUS_CITY:
        _pat = rf"(?:em|de|no|na|do|da|cidade de|capital)\s+{_pat}"
    _PATTERNS.append((re.compile(rf"\b{_pat}\b"), Place(_uf, _capital, _lat, _lon, "CITY", 70), False))
for _uf, _state, _capital, _lat, _lon in _STATES:
    _place = Place(_uf, None, _lat, _lon, "STATE", 60)
    if _uf in _SPECIAL_STATES:
        _rx, _flags = _SPECIAL_STATES[_uf]
        _PATTERNS.append((re.compile(_rx, _flags), _place, True))
    else:
        _PATTERNS.append((re.compile(rf"\b{re.escape(fold(_state))}\b"), _place, False))


def locate(text: str) -> Place | None:
    """Primeira menção geográfica (cidade tem prioridade sobre estado). Conservadora: prefere não localizar."""
    folded = fold(text)
    for pat, place, on_original in _PATTERNS:
        if not pat.search(text if on_original else folded):
            continue
        exclude = _CITY_EXCLUDE.get(place.city or "")
        if exclude and exclude.search(folded):
            continue
        return place
    return None


# Marcadores de política estadual, de prioridade MENOR que nomes de cidade/estado (vêm depois na lista):
# gentílicos ("governo paulista"), assembleias legislativas ("Alesp") e tribunais eleitorais ("TRE-MG").
# De fora por ambiguidade: "fluminense" (clube), "brasiliense" (jornal nacional), "Alba" (nome próprio).
_COORDS = {uf: (capital, lat, lon) for uf, _s, capital, lat, lon in _STATES}
_CITY_GENTILICS = {"SP": r"paulistan[oa]s?", "RJ": r"cariocas?"}
_STATE_MARKERS = {
    "SP": r"paulistas?|alesp", "MG": r"mineir[oa]s?|almg", "RS": r"gauch[oa]s?", "BA": r"baian[oa]s?",
    "PE": r"pernambucan[oa]s?|alepe", "CE": r"cearenses?|alece", "PR": r"paranaenses?|alep",
    "SC": r"catarinenses?|alesc", "GO": r"goian[oa]s?|alego", "ES": r"capixabas?", "AM": r"amazonenses?|aleam",
    "PA": r"paraenses?|alepa", "MA": r"maranhenses?|alema", "RN": r"potiguar(?:es)?", "PB": r"paraiban[oa]s?",
    "AL": r"alagoan[oa]s?", "SE": r"sergipan[oa]s?", "PI": r"piauienses?|alepi", "TO": r"tocantinenses?",
    "RO": r"rondonienses?", "RR": r"roraimenses?", "AC": r"acrean[oa]s?|acrian[oa]s?", "AP": r"amapaenses?",
    "MS": r"sul-mato-grossenses?", "MT": r"(?<!sul-)mato-grossenses?", "RJ": r"alerj", "DF": r"cldf",
}
for _uf, _rx in _CITY_GENTILICS.items():
    _capital, _lat, _lon = _COORDS[_uf]
    _PATTERNS.append((re.compile(rf"\b(?:{_rx})\b"), Place(_uf, _capital, _lat, _lon, "CITY", 60), False))
for _uf, (_capital, _lat, _lon) in _COORDS.items():
    _rx = rf"tre-{_uf.lower()}" + (f"|{_STATE_MARKERS[_uf]}" if _uf in _STATE_MARKERS else "")
    _PATTERNS.append((re.compile(rf"\b(?:{_rx})\b"), Place(_uf, None, _lat, _lon, "STATE", 50), False))


def state_place(uf: str, confidence: int = 40) -> Place | None:
    """Lugar no nível de estado para uma UF conhecida (ex.: comunidade regional de rede social)."""
    if uf not in _COORDS:
        return None
    _capital, lat, lon = _COORDS[uf]
    return Place(uf, None, lat, lon, "STATE", confidence)


_UF_BY_STATE_NAME = {fold(state): uf for uf, state, *_ in _STATES}


def uf_from_state_name(name: str) -> str | None:
    """'Ceará' / 'ceara' -> 'CE' (nome oficial completo do estado, como vem de APIs oficiais)."""
    return _UF_BY_STATE_NAME.get(fold(name.strip()))
