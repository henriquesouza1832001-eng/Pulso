"""Importância de um texto: separa fato de impacto (desastre, vítimas, emergência) de ruído (fofoca).

Heurística transparente e auditável, sem modelo opaco. O score serve para decidir se um sinal de
rede social entra no motor: o PULSO mede o que afeta pessoas, não o que está em alta por curiosidade.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .keyword_engine import _fold

# Termos por nível de impacto. O nível mais alto casado define a base do score.
TIER_A = (  # perda de vidas, colapso, catástrofe
    "mortos", "mortes", "morreu", "morreram", "vitimas", "desabamento", "rompimento", "tornado",
    "terremoto", "tsunami", "calamidade", "estado de emergencia", "desaparecidos", "atentado", "chacina",
)
TIER_B = (  # evento físico relevante ou risco imediato
    "enchente", "alagamento", "inundacao", "deslizamento", "ciclone", "temporal", "tempestade",
    "incendio", "queimada", "apagao", "surto", "epidemia", "evacuacao", "resgate", "explosao",
    "tiroteio", "defesa civil", "onda de calor", "estiagem", "granizo", "feridos", "alerta de",
)
TIER_C = (  # contexto que sozinho não basta
    "chuva forte", "acidente", "interdicao", "bloqueio", "greve", "dengue", "congestionamento",
)
# Ruído de entretenimento e vida privada de famosos.
NOISE = (
    "casou", "casamento", "noivado", "namoro", "affair", "separacao", "fofoca", "famosos", "celebridade",
    "bbb", "novela", "reality", "tretou", "treta", "lacrou", "influencer", "ex-jogador", "gol de",
)

# Agenda de campanha e rotina eleitoral: eventos AGENDADOS e esperados, que não mudam a vida de ninguém por si sós.
ROUTINE = (
    "comicio", "carreata", "motociata", "caminhada", "ato de campanha", "evento de campanha", "agenda de campanha",
    "cumpre agenda", "palanque", "sabatina", "horario eleitoral", "propaganda eleitoral", "santinho", "debate",
    "reuniao com apoiadores", "pesquisa eleitoral", "datafolha", "quaest", "ipec", "discursa", "visita a",
)
# Se vier junto, o evento deixa de ser rotina: comício que termina em tumulto, ataque ou vítimas é notícia de impacto.
DISRUPTION = (
    "tumulto", "confusao", "briga", "agressao", "agredido", "agredida", "ataque", "atirador", "tiros", "bomba",
    "ferido", "feridos", "explosao", "atentado", "invasao", "ameaca", "pancadaria", "depredacao",
)

BASE = {"A": 60, "B": 45, "C": 25}
EXTRA_PER_HIT = 8
NOISE_PENALTY = 30
DEFAULT_THRESHOLD = 45


@dataclass(frozen=True)
class Importance:
    score: int
    high_impact: tuple[str, ...]
    noise: tuple[str, ...]
    routine: bool = False  # agenda de campanha/rotina eleitoral SEM sinal de violência: pesa pouco

    def is_important(self, threshold: int = DEFAULT_THRESHOLD) -> bool:
        return self.score >= threshold


BR_HINTS = re.compile(r"(?<![a-z0-9])(?:brasil|brasileir[oa]s?|pais inteiro|todo o pais)(?![a-z0-9])")
# Países e regiões que, citados sem nenhum lugar do Brasil, indicam notícia de fora do escopo.
FOREIGN = (
    "india", "nepal", "paquistao", "bangladesh", "china", "japao", "filipinas", "indonesia", "eua",
    "estados unidos", "mexico", "argentina", "chile", "colombia", "venezuela", "portugal", "angola",
    "mocambique", "europa", "italia", "espanha", "alemanha", "russia", "ucrania", "israel", "gaza",
    "turquia", "africa", "australia", "canada",
    # Ambíguos em português ("a ira", "o peru", "Franca/SP"): só com a preposição que indica o país.
    "no ira", "do ira", "no peru", "peruano", "peruana", "na franca", "da franca",
)
_FOREIGN = re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(t) for t in FOREIGN) + r")(?![a-z0-9])")


def brazil_relevant(text: str, has_place: bool) -> bool:
    """Descarta só o que claramente é de outro país: cita país estrangeiro e nenhum lugar/menção ao Brasil.

    Não exigimos lugar conhecido: o dicionário geográfico não cobre todas as cidades e perderíamos eventos reais.
    """
    folded = _fold(text)
    if has_place or BR_HINTS.search(folded):
        return True
    return not _FOREIGN.search(folded)


def _compile(terms: tuple[str, ...]) -> list[tuple[str, re.Pattern[str]]]:
    return [(t, re.compile(rf"\b{re.escape(t)}\b")) for t in terms]


_TIERS = {"A": _compile(TIER_A), "B": _compile(TIER_B), "C": _compile(TIER_C)}
_NOISE = _compile(NOISE)
_ROUTINE = _compile(ROUTINE)
_DISRUPTION = _compile(DISRUPTION)


def assess(text: str) -> Importance:
    folded = _fold(text)
    hits: dict[str, list[str]] = {t: [term for term, pat in pats if pat.search(folded)] for t, pats in _TIERS.items()}
    noise = tuple(term for term, pat in _NOISE if pat.search(folded))
    routine = (any(pat.search(folded) for _, pat in _ROUTINE) and not any(hits.values())
               and not any(pat.search(folded) for _, pat in _DISRUPTION))
    matched = [term for tier in ("A", "B", "C") for term in hits[tier]]
    if not matched:
        return Importance(0, (), noise, routine)
    top = next(t for t in ("A", "B", "C") if hits[t])
    score = BASE[top] + EXTRA_PER_HIT * (len(matched) - 1)
    if noise:
        # Com 2+ sinais do nível mais alto ("atentado" + "mortos") a palavra de entretenimento é ruído do texto, não do
        # fato: "Atentado em casamento deixa 20 mortos" é notícia. Com 1 só ("morreu" + "famosos no casamento"), é fofoca.
        score -= NOISE_PENALTY // 3 if len(hits["A"]) >= 2 else NOISE_PENALTY
    return Importance(max(0, min(100, score)), tuple(matched), noise, False)


# ---------------------------------------------------------------- NOISE_GATE (QA-001/002), só lido com a flag ligada
# Agenda, esporte, entretenimento e serviço: muitos veículos noticiam, mas sozinho não é incidente operacional.
SCHEDULED = (
    "onde assistir", "assistir ao vivo", "escalacao", "escalacoes", "vence o", "vence a", "venceu", "empata", "empatou",
    "goleia", "goleada", "rodada", "brasileirao", "libertadores", "copa do brasil", "amistoso", "classico",
    "show", "festival", "ingressos", "turne", "feriado", "o que abre e fecha", "abre e fecha", "horario de funcionamento",
    "loteria", "mega-sena", "sorteio", "programacao", "veja como", "saiba como",  # "bets/apostas" é tema, não agenda
)
# Incidente operacional que o vocabulário de impacto (substantivos) não pegava: verbos/particípios e telecom.
OPERATIONAL = (
    "circulacao interrompida", "interrompida", "interrompido", "paralisada", "paralisado", "paralisacao",
    "sem internet", "sem sinal", "sem energia", "fora do ar", "pane", "bloqueiam", "bloqueada", "bloqueado",
    "interditada", "interditado", "evacuado", "evacuada", "evacuados", "tumulto", "feridos", "ferido",
)
_SCHEDULED = _compile(SCHEDULED)
_OPERATIONAL = _compile(OPERATIONAL)


@dataclass(frozen=True)
class Context:
    scheduled: bool  # agenda/esporte/serviço SEM nenhum sinal de impacto, ruptura ou incidente operacional
    operational: tuple[str, ...]  # termos de incidente operacional encontrados


def context(text: str) -> Context:
    folded = _fold(text)
    operational = tuple(term for term, pat in _OPERATIONAL if pat.search(folded))
    impact = any(pat.search(folded) for pats in _TIERS.values() for _, pat in pats)
    disruption = any(pat.search(folded) for _, pat in _DISRUPTION)
    scheduled = any(pat.search(folded) for _, pat in _SCHEDULED) and not (impact or disruption or operational)
    return Context(scheduled, operational)
