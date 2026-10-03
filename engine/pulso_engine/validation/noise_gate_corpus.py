"""Validação do NOISE_GATE (docs/reliability/NOISE_GATE_VALIDATION.md): o MESMO corpus, flag desligada x ligada.

Corpus determinístico e fabricado (feeds RSS em memória, `run_once` de ponta a ponta), em quatro grupos:
- HARD_NEGATIVE: volume editorial (futebol, apostas, show, feriado, chuva fraca, rush...) em 10..1000 itens: não é incidente;
- POSITIVE: incidente real, inclusive dentro de pauta esportiva/cultural (pane no metrô em dia de clássico): tem de chegar a N2+;
- PROVENANCE: 1 origem -> 5 publishers -> 50 sites -> 1000 reposts sociais: cópia não é confirmação;
- INTEGRITY / CONTRADICTION / COVERAGE: false merge/split, drift, ressurreição, negação oficial, sensores velhos/ausentes.

Não altera nada em produção: só liga flags dentro de `flags_env` (restaura o ambiente ao sair). Rodar:
    py -m pulso_engine.validation.noise_gate_corpus            # tabelas em Markdown
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterator
from xml.sax.saxutils import escape

from ..events import BASE_SEVERITY
from ..flags import FLAGS
from ..models import SOCIAL_CLASSES
from ..pipeline import run_once
from ..processing.normalizer import normalized_title

NOW = datetime(2026, 10, 2, 20, 0, tzinfo=timezone.utc)  # sexta, 17 h em Brasília
VOLUMES = (10, 50, 100, 500, 1000)
MAX_OUTLETS = 40
OBS_STATES = ("SP", "RJ", "MG", "RS", "PE", "PR", "SC")


# ---------------------------------------------------------------- feeds fabricados

@dataclass(frozen=True)
class Item:
    source: str
    title: str
    minutes_ago: float
    cls: str = "NEWS_HIGH"
    slug: str = "x"


def _rss(items: list[Item]) -> bytes:
    body = "".join(
        f"<item><title>{escape(i.title)}</title><link>https://{i.source}.com/{escape(i.slug)}</link><description>d</description>"
        f"<pubDate>{(NOW - timedelta(minutes=i.minutes_ago)).strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate></item>"
        for i in items)
    return f"<?xml version='1.0'?><rss><channel>{body}</channel></rss>".encode()


def burst(templates: list[str], n: int, cls: str = "NEWS_HIGH", prefix: str = "o") -> list[Item]:
    """`n` itens de até MAX_OUTLETS veículos, revezando as manchetes (paráfrases) e espalhados nas últimas 2 h."""
    outlets = min(n, MAX_OUTLETS)
    return [Item(f"{prefix}{i % outlets}", templates[i % len(templates)], 5 + (i * 7) % 110, cls, f"n{i}") for i in range(n)]


def obs_rows(per_hour: int = 2, days: int = 14) -> list[dict]:
    """Histórico plano (2 sinais/h com leve variação) por escopo x categoria: dá ao Sentinela um baseline VÁLIDO."""
    rows = []
    top = NOW.replace(minute=0, second=0, microsecond=0)
    for h in range(1, days * 24 + 1):
        hour = (top - timedelta(hours=h)).strftime("%Y-%m-%dT%H:00:00Z")
        for scope in ("BR", *(f"UF:{s}" for s in OBS_STATES)):
            for cat in BASE_SEVERITY:
                rows.append({"hour": hour, "scope": scope, "category": cat, "source_class": "NEWS_HIGH",
                             "signals": per_hour + (h % 3) - 1})
    return rows


_OBS = obs_rows()


@contextmanager
def flags_env(**on: bool) -> Iterator[None]:
    """Mede com as flags no PADRÃO de produção, exceto as passadas aqui (e o SENTINEL, ligado para contar investigações)."""
    saved = {k: v for k, v in os.environ.items() if k.startswith("PULSO_FLAG_")}
    try:
        for name in FLAGS:
            os.environ.pop(f"PULSO_FLAG_{name}", None)
        for name, value in {"SENTINEL": True, **on}.items():
            os.environ[f"PULSO_FLAG_{name}"] = "1" if value else "0"
        yield
    finally:
        for k in [k for k in os.environ if k.startswith("PULSO_FLAG_")]:
            del os.environ[k]
        os.environ.update(saved)


def execute(items: list[Item], dead: frozenset[str] = frozenset()) -> dict:
    """Roda o pipeline inteiro. Fontes em `dead` respondem com falha de rede (cobertura reduzida)."""
    by_source: dict[str, list[Item]] = {}
    for it in items:
        by_source.setdefault(it.source, []).append(it)
    srcs = [{"id": s, "name": s, "domain": f"{s}.com", "adapter": "rss", "source_class": its[0].cls,
             "url": f"https://{s}.com/rss", "state": None} for s, its in by_source.items()]
    feeds = {s: _rss(its) for s, its in by_source.items()}

    def fetch(url: str) -> bytes:
        name = url.split("//")[1].split(".")[0]
        if name in dead:
            raise TimeoutError("sensor fora do ar")
        return feeds[name]
    return run_once(srcs, fetch, NOW, obs_rows=_OBS, active_investigations=[])


# ---------------------------------------------------------------- métricas

def origins(signals: list[dict]) -> list[list[dict]]:
    """Mesma regra do validador do Sentinela (research/validator.py `_origins`): título quase idêntico = 1 origem."""
    from ..processing.clustering import tokens
    from ..research.validator import COPY_JACCARD
    groups: list[tuple[frozenset[str], list[dict]]] = []
    for s in sorted(signals, key=lambda x: x["timestamp"]):
        toks = tokens(s["title"])
        for gtoks, members in groups:
            union = len(toks | gtoks)
            if union and len(toks & gtoks) / union >= COPY_JACCARD:
                members.append(s)
                break
        else:
            groups.append((toks, [s]))
    return [m for _, m in groups]


def metrics(batch: dict) -> dict:
    events, signals = batch["events"], batch["signals"]
    groups = origins(signals)
    return {
        "events": len(events),
        "n2": sum(1 for e in events if e["alert_level"] >= 2),
        "top": max((e["alert_level"] for e in events), default=0),
        "status": sorted({e["status"] for e in events}),
        "max_conf": max((e["confidence"] for e in events), default=0),
        "max_pulse": max((e["pulse"] for e in events), default=0),
        "max_sources": max((e["source_count"] for e in events), default=0),  # o que o evento diz ter de fontes
        "signals": len(signals),
        "duplicate_count": len(signals) - len({(s["source_id"], normalized_title(s["title"])) for s in signals}),
        "publisher_count": len({s["source_id"] for s in signals if s["source_class"] not in SOCIAL_CLASSES}),
        "origin_count": len(groups),
        "independent_origin_count": len({g[0]["source_id"] for g in groups}),
        "sensor_family_count": len({s["source_class"] for s in signals}),
        "investigations": len(batch["investigations"]),
        "gate_in_why": any(b["key"] == "noise_gate" for e in events for b in e["score_breakdown"]),
    }


# ---------------------------------------------------------------- corpus

HARD_NEGATIVES: dict[str, tuple[list[str], str]] = {
    "SPORTS_NEWS_BURST": ([
        "Flamengo vence o Palmeiras por 2 a 1 no Maracanã e assume liderança",
        "Com gol no fim, Flamengo bate o Palmeiras e assume a liderança do Brasileirão",
        "Palmeiras perde para o Flamengo no Maracanã e cai para segundo",
        "Flamengo vence clássico contra o Palmeiras pela rodada do Brasileirão"], "NEWS_HIGH"),
    "BETTING_NEWS_BURST": ([
        "Bets: casas de apostas movimentam R$ 20 bilhões no Brasil em 2026",
        "Apostas esportivas crescem e bets batem recorde de usuários",
        "Mega-Sena acumula e prêmio vai a R$ 100 milhões no próximo sorteio",
        "Bets: veja as regras novas para as casas de apostas"], "NEWS_HIGH"),
    "TRANSFER_MARKET": ([
        "Corinthians anuncia contratação de atacante argentino até 2028",
        "Atacante deixa o Santos e acerta com clube da Arábia Saudita",
        "Palmeiras encaminha venda de meia para clube europeu",
        "Mercado da bola: Corinthians anuncia atacante argentino"], "NEWS_HIGH"),
    "WHERE_TO_WATCH": ([
        "Brasil x Argentina: onde assistir ao vivo e escalações",
        "Onde assistir Brasil x Argentina hoje, horário e escalação",
        "Brasil x Argentina ao vivo: saiba como assistir ao jogo",
        "Escalações de Brasil x Argentina e onde assistir"], "NEWS_HIGH"),
    "CONCERT_NORMAL": ([
        "Show da Anitta reúne 80 mil pessoas no Rio de Janeiro",
        "Festival de música em São Paulo tem ingressos esgotados",
        "Anitta faz show para 80 mil fãs em Copacabana",
        "Turnê de banda britânica passa por São Paulo neste sábado"], "NEWS_HIGH"),
    "TV_EVENT": ([
        "Final da novela bate recorde de audiência na TV",
        "Reality show: participante é eliminado com 60% dos votos",
        "Último capítulo da novela tem maior audiência do ano",
        "Eliminação no reality movimenta as redes sociais"], "NEWS_HIGH"),
    "HOLIDAY": ([
        "Feriado de 12 de outubro: veja o que abre e fecha em São Paulo",
        "Bancos fecham no feriado de Nossa Senhora Aparecida",
        "Feriado prolongado: saiba o que abre e fecha no Rio de Janeiro",
        "Shoppings e mercados têm horário especial no feriado"], "NEWS_HIGH"),
    "NORMAL_RAIN": ([
        "Previsão indica chuva fraca em São Paulo nesta sexta-feira",
        "Tempo fica nublado com garoa em Curitiba no fim de semana",
        "Frente fria traz chuva leve e queda de temperatura ao Sul",
        "Sexta-feira tem tempo instável e chuva fraca na capital paulista"], "NEWS_HIGH"),
    "RUSH_HOUR": ([
        "Trânsito lento na Marginal Pinheiros no fim da tarde",
        "São Paulo registra 80 km de lentidão no horário de pico",
        "Horário de pico tem trânsito intenso nas marginais",
        "Lentidão nas principais vias de São Paulo no fim do dia"], "NEWS_HIGH"),
    "SOCIAL_REPOST_STORM": ([
        "Vídeo de gato tocando piano viraliza nas redes",
        "Gato pianista viraliza e vira meme nas redes sociais",
        "Esse gato tocando piano é a melhor coisa que você vai ver hoje",
        "Vídeo do gato que toca piano já tem milhões de visualizações"], "SOCIAL"),
}

POSITIVES: dict[str, list[str]] = {
    "DERBY_METRO_FAILURE": [
        "Pane no metrô interrompe Linha 3-Vermelha antes do clássico em São Paulo",
        "Linha 3-Vermelha do metrô tem circulação interrompida em dia de clássico em São Paulo",
        "Torcedores ficam presos após pane na Linha 3-Vermelha do metrô de São Paulo",
        "Metrô de São Paulo: pane paralisa Linha 3-Vermelha antes do clássico"],
    "STADIUM_EVACUATION": [
        "Estádio do Maracanã é evacuado após ameaça de bomba durante jogo",
        "Ameaça de bomba: Maracanã é evacuado durante partida no Rio de Janeiro",
        "Torcedores são retirados do Maracanã após ameaça de bomba",
        "Maracanã evacuado após ameaça de bomba no Rio de Janeiro"],
    "SPORT_EVENT_BLACKOUT": [
        "Apagão interrompe jogo no Mineirão e deixa torcedores no escuro em Belo Horizonte",
        "Mineirão fica sem energia e jogo é interrompido em Belo Horizonte",
        "Falta de energia no Mineirão paralisa partida em Belo Horizonte",
        "Apagão no Mineirão: jogo interrompido e estádio sem luz em Belo Horizonte"],
    "SPORT_EVENT_SECURITY_INCIDENT": [
        "Briga entre torcidas deixa feridos após jogo em São Paulo",
        "Confronto entre torcedores deixa feridos perto do estádio em São Paulo",
        "Torcidas brigam após clássico e feridos são levados a hospital em São Paulo",
        "Briga de torcidas após jogo deixa feridos e presos em São Paulo"],
    "CONCERT_EVACUATION": [
        "Estrutura desaba em show e público é evacuado no Rio de Janeiro",
        "Show é interrompido e plateia evacuada após queda de estrutura no Rio de Janeiro",
        "Desabamento de estrutura em show deixa feridos no Rio de Janeiro",
        "Queda de estrutura interrompe show e público é retirado no Rio de Janeiro"],
    "CONCERT_TRANSPORT_FAILURE": [
        "Trens param e fãs ficam sem transporte após show em São Paulo",
        "Pane na CPTM deixa público de show sem transporte em São Paulo",
        "Circulação de trens interrompida após show em São Paulo; estação fechada",
        "Fãs ficam presos em estação após pane nos trens depois de show em São Paulo"],
    "CITY_BLACKOUT": [
        "Apagão deixa bairros de Porto Alegre sem energia elétrica",
        "Porto Alegre tem apagão e bairros ficam sem luz",
        "Falta de energia atinge bairros de Porto Alegre após apagão",
        "Apagão em Porto Alegre deixa milhares sem energia"],
    "TELECOM_FAILURE": [
        "Falha em operadora deixa clientes sem internet e celular em Recife",
        "Clientes ficam sem sinal de celular e sem internet em Recife",
        "Operadora tem pane e Recife fica sem internet móvel",
        "Pane em operadora deixa Recife sem internet e sem celular"],
    "ROAD_BLOCKAGE": [
        "Caminhoneiros bloqueiam rodovia BR-116 em Curitiba",
        "BR-116 é bloqueada por caminhoneiros em Curitiba",
        "Protesto de caminhoneiros interdita BR-116 em Curitiba",
        "Rodovia BR-116 bloqueada por caminhoneiros na região de Curitiba"],
    "FLOOD": [
        "Enchente deixa desalojados em Porto Alegre após chuva forte",
        "Chuva forte provoca enchente e desalojados em Porto Alegre",
        "Porto Alegre tem enchente e famílias desalojadas",
        "Enchente em Porto Alegre deixa famílias desalojadas após temporal"],
}


@dataclass
class Scenario:
    name: str
    group: str
    expected: str
    items: Callable[[], list[Item]]
    passes: Callable[[dict], bool]
    dead: frozenset[str] = frozenset()
    flags: dict[str, bool] = field(default_factory=dict)  # flags extras (além do NOISE_GATE) nos DOIS modos


def _no_incident(m: dict) -> bool:
    return m["n2"] == 0


def scenarios() -> list[Scenario]:
    out: list[Scenario] = []
    for name, (templates, cls) in HARD_NEGATIVES.items():
        for n in VOLUMES:
            out.append(Scenario(f"{name}@{n}", "HARD_NEGATIVE", "nenhum evento N2+",
                                lambda t=templates, n=n, c=cls: burst(t, n, c), _no_incident))
    for name, templates in POSITIVES.items():
        for n in (4, 12):
            out.append(Scenario(f"{name}@{n}", "POSITIVE", "algum evento N2+",
                                lambda t=templates, n=n: burst(t, n), lambda m: m["n2"] >= 1))
    # Incidente real no meio de uma enxurrada de pauta esportiva (recall sob ruído).
    out.append(Scenario("DERBY_METRO_FAILURE_IN_500_SPORTS", "POSITIVE", "o incidente segue N2+ no meio de 500 matérias de futebol",
                        lambda: burst(HARD_NEGATIVES["SPORTS_NEWS_BURST"][0], 500) + burst(POSITIVES["DERBY_METRO_FAILURE"], 8, prefix="m"),
                        lambda m: m["n2"] >= 1))
    out.extend(provenance_scenarios())
    out.extend(integrity_scenarios())
    out.extend(contradiction_scenarios())
    return out


# ---------------------------------------------------------------- proveniência: 1 -> 5 -> 50 -> 1000

CASCADE_ORIGIN = "Defesa Civil confirma desabamento de prédio no centro de Belo Horizonte"
CASCADE_PUBLISHERS = [
    "Prédio desaba no centro de Belo Horizonte, confirma Defesa Civil",
    "Desabamento de prédio no centro de Belo Horizonte mobiliza bombeiros",
    "Belo Horizonte: prédio desaba no centro e Defesa Civil isola a área",
    "Prédio desaba no centro de BH; Defesa Civil confirma",
    "Defesa Civil: desabamento atinge prédio no centro de Belo Horizonte"]


def cascade(sites: int = 50, reposts: int = 1000) -> list[Item]:
    items = [Item("defesacivil", CASCADE_ORIGIN, 30, "OFFICIAL")]
    items += [Item(f"pub{i}", t, 25 - i) for i, t in enumerate(CASCADE_PUBLISHERS)]
    # sites: copiam a manchete de um publisher (URL e sufixo diferentes)
    items += [Item(f"site{i}", f"{CASCADE_PUBLISHERS[i % 5]} | Portal {i}", 20 - (i % 15), "NEWS_REGIONAL", f"materia-{i}")
              for i in range(sites)]
    # redes: repost literal ou com "URGENTE:" / "RT"
    pre = ("", "URGENTE: ", "RT ")
    items += [Item(f"soc{i % 200}", f"{pre[i % 3]}{CASCADE_PUBLISHERS[i % 5]}", 15 - (i % 14), "SOCIAL", f"p{i}")
              for i in range(reposts)]
    return items


def provenance_scenarios() -> list[Scenario]:
    def ok(m: dict) -> bool:  # 1 fato: a contagem de independência do EVENTO não pode passar das origens reais (6)
        return m["max_sources"] <= 6 and m["independent_origin_count"] <= 6
    return [
        Scenario("CASCADE_1_5_50", "PROVENANCE", "fontes do evento <= 6 (1 origem + 5 paráfrases)", lambda: cascade(50, 0), ok),
        Scenario("CASCADE_1_5_50_1000", "PROVENANCE", "fontes do evento <= 6; 1000 reposts não somam", lambda: cascade(50, 1000), ok),
    ]


# ---------------------------------------------------------------- integridade de evento

def integrity_scenarios() -> list[Scenario]:
    same_topic_two_cities = [
        Item("a", "Temporal causa alagamentos e deixa feridos em São Paulo", 10),
        Item("b", "Temporal causa alagamentos e deixa feridos em São Paulo", 12),
        Item("c", "Temporal causa alagamentos e deixa feridos em Belo Horizonte", 11),
        Item("d", "Temporal causa alagamentos e deixa feridos em Belo Horizonte", 13)]
    petropolis = ["Deslizamento de terra atinge casas em Petrópolis", "Petrópolis: chuva provoca deslizamento e soterra imóveis",
                  "Defesa Civil confirma deslizamento em Petrópolis após temporal",
                  "Moradores de Petrópolis são retirados após deslizamento"]
    drift = ["Incêndio atinge fábrica de Joinville e mobiliza bombeiros", "Fábrica de Joinville atingida por incêndio anuncia demissões",
             "Demissões em fábrica de Joinville geram protesto de trabalhadores", "Protesto de trabalhadores em Joinville bloqueia avenida"]
    old = [Item(f"s{i}", "Enchente deixa mortos e desalojados em Porto Alegre", 60 * 72 + i) for i in range(5)]  # 3 dias atrás
    return [
        Scenario("FALSE_MERGE", "INTEGRITY", "2 eventos (SP e MG)", lambda: same_topic_two_cities, lambda m: m["events"] == 2),
        Scenario("FALSE_MERGE+CLUSTER_REFINE", "INTEGRITY", "2 eventos (SP e MG)", lambda: same_topic_two_cities,
                 lambda m: m["events"] == 2, flags={"CLUSTER_REFINE": True}),
        Scenario("FALSE_SPLIT", "INTEGRITY", "1 evento com 4 fontes",
                 lambda: [Item(f"s{i}", t, 10 + i) for i, t in enumerate(petropolis)],
                 lambda m: m["events"] == 1 and m["max_sources"] == 4),
        Scenario("FALSE_SPLIT+CLUSTER_REFINE", "INTEGRITY", "1 evento com 4 fontes",
                 lambda: [Item(f"s{i}", t, 10 + i) for i, t in enumerate(petropolis)],
                 lambda m: m["events"] == 1 and m["max_sources"] == 4, flags={"CLUSTER_REFINE": True}),
        Scenario("EVENT_DRIFT", "INTEGRITY", "a cadeia incêndio -> demissão -> protesto não vira 1 evento",
                 lambda: [Item(f"s{i}", t, 40 - 10 * i) for i, t in enumerate(drift)], lambda m: m["max_sources"] < 4),
        Scenario("EVENT_RESURRECTION", "INTEGRITY", "matéria de 3 dias atrás não cria evento",
                 lambda: old, lambda m: m["events"] == 0),
    ]


# ---------------------------------------------------------------- contradição e cobertura

FIRE = ["Incêndio em hospital de Campinas deixa feridos", "Incêndio atinge hospital de Campinas e deixa feridos",
        "Hospital de Campinas tem incêndio com feridos"]


def contradiction_scenarios() -> list[Scenario]:
    news = [Item(f"n{i}", t, 30 - i) for i, t in enumerate(FIRE)]
    denial = Item("bombeiros", "Bombeiros: incêndio em hospital de Campinas não deixou feridos", 5, "OFFICIAL")
    confirm = Item("bombeiros", "Bombeiros confirmam incêndio em hospital de Campinas com feridos", 5, "OFFICIAL")
    energy = [Item("a", "Apagão deixa bairros de Recife sem energia", 30), Item("b", "Recife tem apagão e bairros sem energia", 25),
              Item("c", "Energia restabelecida em bairros de Recife após apagão", 28),
              Item("d", "Recife: apagão deixa bairros sem luz", 10)]
    resolved = [Item("a", "Apagão deixa bairros de Recife sem energia", 60), Item("b", "Recife tem apagão e bairros sem energia", 50),
                Item("c", "Apagão em Recife: energia restabelecida nos bairros", 5)]
    stale = [*news, Item("bombeiros", "Bombeiros confirmam incêndio em hospital de Campinas com feridos", 60 * 14, "OFFICIAL")]
    out = [
        Scenario("OFFICIAL_CONFIRMATION", "CONTRADICTION", "CONFIRMED", lambda: [*news, confirm], lambda m: m["status"] == ["CONFIRMED"]),
        Scenario("OFFICIAL_DENIAL", "CONTRADICTION", "DISPUTED", lambda: [*news, denial], lambda m: m["status"] == ["DISPUTED"]),
        Scenario("OFFICIAL_DENIAL+EVENT_CONTRADICTION", "CONTRADICTION", "DISPUTED", lambda: [*news, denial],
                 lambda m: m["status"] == ["DISPUTED"], flags={"EVENT_CONTRADICTION": True}),
        Scenario("CONFLICTING_SENSORS", "CONTRADICTION", "DISPUTED (sem energia x restabelecida ao mesmo tempo)", lambda: energy,
                 lambda m: m["status"] == ["DISPUTED"]),
        Scenario("CONFLICTING_SENSORS+EVENT_CONTRADICTION", "CONTRADICTION", "DISPUTED (sem energia x restabelecida ao mesmo tempo)",
                 lambda: energy, lambda m: m["status"] == ["DISPUTED"], flags={"EVENT_CONTRADICTION": True}),
        Scenario("RESOLUTION_IS_NOT_DISPUTE+EVENT_CONTRADICTION", "CONTRADICTION", "não DISPUTED (restabelecida DEPOIS)",
                 lambda: resolved, lambda m: "DISPUTED" not in m["status"], flags={"EVENT_CONTRADICTION": True}),
        # O sensor velho fica no próprio evento (antigo); o relato de agora segue com as 3 fontes de agora.
        Scenario("STALE_SENSOR", "CONTRADICTION", "confirmação oficial de 14 h atrás não se soma ao relato de agora",
                 lambda: stale, lambda m: m["max_sources"] == 3),
    ]
    return out


COVERAGE_SENSORS = [
    Item("defesacivil", "Defesa Civil alerta para alagamento em bairros de Salvador", 20, "OFFICIAL"),
    Item("g1", "Alagamento atinge bairros de Salvador após chuva forte", 18),
    Item("regional", "Chuva forte causa alagamento em bairros de Salvador", 15, "NEWS_REGIONAL"),
    Item("transito", "Alagamento bloqueia vias em bairros de Salvador", 12, "TRAFFIC_PROVIDER"),
    Item("social", "Alagamento agora nos bairros de Salvador, rua toda tomada", 8, "SOCIAL"),
]
COVERAGE_LEVELS = (100, 80, 60, 40, 20, 0)


def coverage_curve() -> list[tuple[int, dict]]:
    """Derruba sensores de 5 em 5 (do menos ao mais confiável por último): menos observação nunca aumenta a confiança."""
    order = ["social", "transito", "regional", "g1", "defesacivil"]
    out = []
    for pct in COVERAGE_LEVELS:
        dead = frozenset(order[: (100 - pct) // 20])
        out.append((pct, metrics(execute(COVERAGE_SENSORS, dead))))
    return out


# ---------------------------------------------------------------- execução e relatório

def measure(s: Scenario, gate: bool) -> dict:
    with flags_env(NOISE_GATE=gate, **s.flags):
        return metrics(execute(s.items(), s.dead))


def run_all() -> list[tuple[Scenario, dict, dict]]:
    return [(s, measure(s, False), measure(s, True)) for s in scenarios()]


def _fmt(m: dict) -> str:
    st = "/".join(m["status"]) or "-"
    return (f"ev {m['events']} · N2+ {m['n2']} · top N{m['top']} · {st} · conf {m['max_conf']} · fontes {m['max_sources']}"
            f" · inv {m['investigations']}")


# Risco de regressão AO LIGAR o gate, por grupo (e exceções por cenário): o que pode dar errado em dado real.
GROUP_RISK = {
    "HARD_NEGATIVE": "baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula",
    "POSITIVE": "baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto",
    "PROVENANCE": "médio: relato social curto e parecido com a manchete deixa de somar (quase-cópia)",
    "INTEGRITY": "nenhum: o gate não toca o agrupamento",
    "CONTRADICTION": "nenhum para o gate; EVENT_CONTRADICTION depende de regex de negação (médio)",
}
SCENARIO_RISK = {
    "NORMAL_RAIN": "médio: 'chuva fraca'/'garoa' viram rotina; chuva perigosa precisa de 'chuva forte'/'temporal' no texto",
    "RUSH_HOUR": "médio: 'lentidão' vira rotina; lentidão por incidente precisa de 'acidente'/'congestionamento'/'bloqueio'",
    "CONCERT_TRANSPORT_FAILURE": "médio: 'ficam presos'/'trens param' podem publicar pauta de agenda ambígua",
    "SOCIAL_REPOST_STORM": "baixo: viral social já é teto 3 e DETECTED; o gate só tira volume da independência",
}


def risk(s: Scenario) -> str:
    return SCENARIO_RISK.get(s.name.split("@")[0], GROUP_RISK[s.group])


def markdown(rows: list[tuple[Scenario, dict, dict]]) -> str:
    out = ["| Cenário | OFF | ON | Esperado | OFF | ON | Risco de regressão |", "|---|---|---|---|---|---|---|"]
    for s, off, on in rows:
        out.append(f"| `{s.name}` | {_fmt(off)} | {_fmt(on)} | {s.expected} | "
                   f"{'PASS' if s.passes(off) else 'FAIL'} | {'PASS' if s.passes(on) else 'FAIL'} | {risk(s)} |")
    return "\n".join(out)


def summary(rows: list[tuple[Scenario, dict, dict]]) -> dict[str, dict[str, int]]:
    res: dict[str, dict[str, int]] = {}
    for s, off, on in rows:
        g = res.setdefault(s.group, {"total": 0, "off_pass": 0, "on_pass": 0, "off_n2": 0, "on_n2": 0, "off_events": 0,
                                     "on_events": 0, "off_inv": 0, "on_inv": 0})
        g["total"] += 1
        g["off_pass"] += s.passes(off)
        g["on_pass"] += s.passes(on)
        for k, m in (("off", off), ("on", on)):
            g[f"{k}_n2"] += m["n2"]
            g[f"{k}_events"] += m["events"]
            g[f"{k}_inv"] += m["investigations"]
    return res


if __name__ == "__main__":  # pragma: no cover - gerador do relatório
    import json
    import sys
    rows = run_all()
    print(markdown(rows))
    print()
    print(json.dumps(summary(rows), indent=1))
    for s, off, on in rows:
        if s.group == "PROVENANCE":
            print(s.name, json.dumps({k: (off[k], on[k]) for k in off if k not in ("status",)}), file=sys.stderr)
    for gate in (False, True):
        with flags_env(NOISE_GATE=gate):
            print("coverage gate=%s" % gate, [(p, m["max_conf"], m["top"], m["status"]) for p, m in coverage_curve()])
