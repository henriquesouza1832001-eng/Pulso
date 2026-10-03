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
    "evacuam", "evacuado", "evacuados", "falha eletrica", "principio de incendio",
)
TIER_C = (  # contexto que sozinho não basta
    "chuva forte", "acidente", "interdicao", "interditado", "interrompido", "risco estrutural", "bloqueio", "greve", "dengue", "congestionamento",
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

# Papel semântico do sinal.  O papel é deliberadamente separado do assunto:
# uma partida pode ser contexto editorial, enquanto uma evacuação no estádio é
# um incidente operacional.
EDITORIAL_ONLY = "EDITORIAL_ONLY"
SCHEDULED_CONTEXT = "SCHEDULED_CONTEXT"
OPERATIONAL_SIGNAL = "OPERATIONAL_SIGNAL"
POTENTIAL_INCIDENT = "POTENTIAL_INCIDENT"

EDITORIAL_PATTERNS = (
    "onde assistir", "onde ver", "horario do jogo", "hora do jogo", "que horas joga",
    "escalacao", "resultado do jogo", "tabela do", "classificacao do", "palpite",
    "apostas", "odds", "mercado da bola", "transferencia", "brasileirao", "campeonato",
    "jogo entre", "partida entre", "sao paulo recebe", "corinthians recebe",
)
SCHEDULED_PATTERNS = (
    "partida", "jogo", "show", "festival", "concerto", "evento marcado", "ingressos",
)
@dataclass(frozen=True)
class Importance:
    score: int
    high_impact: tuple[str, ...]
    noise: tuple[str, ...]
    routine: bool = False  # agenda de campanha/rotina eleitoral SEM sinal de violência: pesa pouco
    role: str = OPERATIONAL_SIGNAL

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
_EDITORIAL = _compile(EDITORIAL_PATTERNS)
_SCHEDULED = _compile(SCHEDULED_PATTERNS)


def assess(text: str) -> Importance:
    folded = _fold(text)
    hits: dict[str, list[str]] = {t: [term for term, pat in pats if pat.search(folded)] for t, pats in _TIERS.items()}
    noise = tuple(term for term, pat in _NOISE if pat.search(folded))
    routine = (any(pat.search(folded) for _, pat in _ROUTINE) and not any(hits.values())
               and not any(pat.search(folded) for _, pat in _DISRUPTION))
    matched = [term for tier in ("A", "B", "C") for term in hits[tier]]
    editorial = any(pat.search(folded) for _, pat in _EDITORIAL)
    scheduled = any(pat.search(folded) for _, pat in _SCHEDULED)
    has_disruption = any(pat.search(folded) for _, pat in _DISRUPTION)
    if not matched:
        role = EDITORIAL_ONLY if editorial else (SCHEDULED_CONTEXT if scheduled else OPERATIONAL_SIGNAL)
        return Importance(0, (), noise, routine, role)
    top = next(t for t in ("A", "B", "C") if hits[t])
    score = BASE[top] + EXTRA_PER_HIT * (len(matched) - 1)
    if noise:
        # Com 2+ sinais do nível mais alto ("atentado" + "mortos") a palavra de entretenimento é ruído do texto, não do
        # fato: "Atentado em casamento deixa 20 mortos" é notícia. Com 1 só ("morreu" + "famosos no casamento"), é fofoca.
        score -= NOISE_PENALTY // 3 if len(hits["A"]) >= 2 else NOISE_PENALTY
    role = POTENTIAL_INCIDENT if has_disruption or hits["A"] or hits["B"] else OPERATIONAL_SIGNAL
    # Editorial sports language never masks physical impact: "jogo interrompido
    # por apagão" remains operational.
    return Importance(max(0, min(100, score)), tuple(matched), noise, False, role)
