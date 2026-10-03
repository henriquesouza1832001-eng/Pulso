"""QA adversarial do pipeline inteiro (docs/reliability/BACKEND_ADVERSARIAL_QA.md).

Roda `run_once` de ponta a ponta com feeds RSS fabricados: COLLECT → NORMALIZE → CLASSIFY → GEO → DEDUP → CLUSTER →
EVENT → SCORE. Procura casos em que cada módulo funciona isolado, mas o resultado integrado parece certo e está errado.

- Testes normais: invariantes que HOJE valem e não podem regredir.
- `xfail(strict=True)`: defeitos reproduzidos e ainda não corrigidos (QA-xxx no relatório). Não são testes enfraquecidos:
  quando o dono corrigir, o teste passa a passar, o strict quebra a suíte e o marcador tem de ser removido.
"""
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape

import pytest

from pulso_engine.flags import FLAGS
from pulso_engine.pipeline import run_once

NOW = datetime(2026, 10, 2, 20, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _default_flags(monkeypatch):
    # Mede o comportamento de PRODUÇÃO (flags no padrão), mesmo que o ambiente do desenvolvedor ligue alguma V2.
    for name in FLAGS:
        monkeypatch.delenv(f"PULSO_FLAG_{name}", raising=False)


def rss(items, desc: str = "d") -> bytes:
    body = "".join(
        f"<item><title>{escape(t)}</title><link>{escape(link)}</link><description>{escape(desc)}</description>"
        f"<pubDate>{(NOW - timedelta(minutes=m)).strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate></item>"
        for t, link, m in items
    )
    return f"<?xml version='1.0'?><rss><channel>{body}</channel></rss>".encode()


def src(i: str, cls: str = "NEWS_HIGH") -> dict:
    return {"id": i, "name": i, "domain": f"{i}.com", "adapter": "rss", "source_class": cls,
            "url": f"https://{i}.com/rss", "state": None}


def run(feeds: dict[str, bytes], srcs: list[dict] | None = None, now: datetime = NOW) -> dict:
    srcs = srcs or [src(k) for k in feeds]
    return run_once(srcs, lambda u: feeds[u.split("//")[1].split(".")[0]], now)


def same_story(title: str, n: int, slug: str = "x") -> dict[str, bytes]:
    """A mesma manchete publicada por `n` veículos diferentes."""
    return {f"s{i}": rss([(title, f"https://s{i}.com/{slug}", 10 + i)]) for i in range(n)}


def top_level(batch: dict) -> int:
    """Maior nível publicado; 0 = nem virou evento (o melhor desfecho para ruído)."""
    return max((e["alert_level"] for e in batch["events"]), default=0)


def only_event(batch: dict) -> dict:
    assert len(batch["events"]) == 1, [e["title"] for e in batch["events"]]
    return batch["events"][0]


NOISE = {
    "futebol": "Flamengo vence o Palmeiras por 2 a 1 no Maracanã e assume liderança",
    "onde_assistir": "Flamengo x Palmeiras: onde assistir ao vivo e escalações",
    "show": "Show da Anitta reúne 80 mil pessoas no Rio de Janeiro",
    "feriado": "Feriado de 12 de outubro: veja o que abre e fecha em São Paulo",
}
INCIDENTS_UNDERRATED = {
    "metro": "Linha 3-Vermelha do metrô de São Paulo tem circulação interrompida",
    "telecom": "Falha em operadora deixa clientes sem internet e celular em Recife",
    "bloqueio": "Caminhoneiros bloqueiam rodovia BR-116 em Curitiba",
    "tumulto_show": "Tumulto em show deixa feridos e público é evacuado em São Paulo",
}


# ---------------------------------------------------------------- invariantes que valem hoje (regressão)

@pytest.mark.parametrize("name", list(NOISE))
def test_noise_from_a_single_outlet_never_becomes_event(name):
    assert run(same_story(NOISE[name], 1))["events"] == []


@pytest.mark.parametrize("title", [
    "Apagão deixa bairros de São Paulo sem energia elétrica",
    "Prédio é evacuado após incêndio no centro de Belo Horizonte",
    "Enchente deixa desalojados em Porto Alegre após chuva forte",
])
def test_physical_incidents_with_four_outlets_reach_n2(title):
    # Quatro redações independentes; republicações do mesmo título não são
    # usadas como confirmação após o gate de proveniência.
    feeds = {f"s{i}": rss([(f"{title} — relato independente {i}", f"https://s{i}.com/{i}", 10 + i)]) for i in range(4)}
    ev = only_event(run(feeds))
    assert ev["alert_level"] >= 2 and ev["status"] == "CONFIRMED"


def test_thousand_copies_from_one_outlet_stay_one_independent_source():
    title = "Incêndio atinge galpão em Campinas e mobiliza bombeiros"
    ev = only_event(run({"a": rss([(title, f"https://a.com/n{i}", 5 + i % 50) for i in range(1000)])}))
    assert ev["source_count"] == 1 and ev["status"] != "CONFIRMED"
    assert ev["confidence"] <= 10  # volume de cópia derruba a confiança, não a sobe


def test_same_url_repeated_is_deduplicated():
    b = run({"a": rss([("Incêndio atinge galpão em Campinas", "https://a.com/n?utm_source=x", 5)] * 50)})
    assert len(b["signals"]) == 1


def test_syndicated_identical_title_has_lower_confidence_than_independent_reporting():
    variants = [
        "Incêndio atinge galpão em Campinas e mobiliza bombeiros", "Bombeiros combatem incêndio em galpão de Campinas",
        "Galpão pega fogo em Campinas; bombeiros no local", "Incêndio de grandes proporções em galpão de Campinas",
        "Campinas: fogo em galpão mobiliza equipes dos bombeiros", "Incêndio em galpão em Campinas tem fumaça visível de longe",
    ]
    syndicated = only_event(run(same_story(variants[0], 6)))
    independent = only_event(run({f"s{i}": rss([(t, f"https://s{i}.com/x", 10)]) for i, t in enumerate(variants)}))
    assert syndicated["confidence"] < independent["confidence"]


def test_same_topic_in_different_states_is_not_merged():
    feeds = {
        "a": rss([("Temporal causa alagamentos e deixa feridos em São Paulo", "https://a.com/1", 10)]),
        "b": rss([("Temporal causa alagamentos e deixa feridos em São Paulo", "https://b.com/1", 12)]),
        "c": rss([("Temporal causa alagamentos e deixa feridos em Belo Horizonte", "https://c.com/1", 11)]),
        "d": rss([("Temporal causa alagamentos e deixa feridos em Belo Horizonte", "https://d.com/1", 13)]),
    }
    assert sorted(e["state"] for e in run(feeds)["events"]) == ["MG", "SP"]


def test_source_order_does_not_change_the_result():
    titles = ["mobiliza bombeiros", "deixa feridos", "fumaça tomou o bairro", "é controlado"]
    feeds = {f"s{i}": rss([(f"Incêndio em fábrica de Joinville {t}", f"https://s{i}.com/{i}", 10 + i)])
             for i, t in enumerate(titles)}
    results = set()
    for order in ([0, 1, 2, 3], [3, 2, 1, 0], [2, 0, 3, 1], [1, 3, 0, 2]):
        b = run(feeds, [src(f"s{i}") for i in order])
        results.add(tuple(sorted((e["event_id"], e["alert_level"], e["pulse"], e["signal_count"]) for e in b["events"])))
    assert len(results) == 1


def raw_feed(title: str, pub: str | None) -> bytes:
    date = f"<pubDate>{pub}</pubDate>" if pub else ""
    return f"<rss><channel><item><title>{escape(title)}</title><link>https://x.com/1</link>{date}</item></channel></rss>".encode()


@pytest.mark.parametrize("pub", ["Mon, 05 Oct 2026 20:00:00 +0000", "Fri, 31 Dec 9999 23:59:59 +0000"])
def test_future_timestamp_is_clamped_to_now(pub):
    b = run({"s0": raw_feed("Enchente deixa desalojados em Porto Alegre", pub)})
    assert b["signals"] and all(s["timestamp"] <= "2026-10-02T20:00:00Z" for s in b["signals"])


def test_old_republished_article_is_not_new_state():
    b = run(same_story("Enchente deixa desalojados em Porto Alegre", 3) | {
        "old": raw_feed("Enchente histórica deixa mortos em Porto Alegre", "Mon, 01 Jul 2019 10:00:00 +0000")})
    assert all("histórica" not in s["title"] for s in b["signals"])


@pytest.mark.parametrize("title", ["", "   "])
def test_empty_title_is_dropped(title):
    assert run({"s0": raw_feed(title, "Fri, 02 Oct 2026 19:30:00 +0000")})["signals"] == []


def test_huge_title_is_bounded():
    b = run({"s0": raw_feed("Enchente " + "a" * 200_000, "Fri, 02 Oct 2026 19:30:00 +0000")})
    assert all(len(s["title"]) <= 300 for s in b["signals"])


def test_http_200_with_html_is_degraded_not_online():
    h = run({"s0": b"<html><body>Em manutencao</body></html>"})["source_health"][0]
    assert h["status"] == "DEGRADED"  # HTTP 200 != dado


# ---------------------------------------------------------------- defeitos reproduzidos (QA-xxx), ainda abertos

QA001_OPEN = pytest.mark.xfail(strict=True, reason="QA-001: volume de veículos sozinho leva ruído a N2")


# O gate editorial/agenda também cobre futebol e feriado; o marcador só permanece
# nos casos ainda não resolvidos pela classificação operacional.
@pytest.mark.parametrize("name", [
    "futebol", "onde_assistir", "show", "feriado"])
def test_noise_does_not_reach_n2_by_outlet_volume(name):
    assert top_level(run(same_story(NOISE[name], 6))) < 2


@pytest.mark.xfail(strict=True, reason="QA-002: incidente operacional sem termo do classificador fica N1 com 4 veículos")
@pytest.mark.parametrize("name", list(INCIDENTS_UNDERRATED))
def test_operational_incidents_with_four_outlets_reach_n2(name):
    ev = only_event(run(same_story(INCIDENTS_UNDERRATED[name], 4)))
    assert ev["alert_level"] >= 2


def test_incident_with_injured_outranks_football_at_equal_volume():
    football = top_level(run(same_story(NOISE["futebol"], 6)))
    tumult = only_event(run(same_story(INCIDENTS_UNDERRATED["tumulto_show"], 6)))
    assert tumult["alert_level"] > football


def test_identical_social_reposts_do_not_confirm_a_single_story():
    title = "Incêndio atinge galpão em Campinas e mobiliza bombeiros"
    feeds = {"a": rss([(title, "https://a.com/1", 10)]),
             **{f"r{i}": rss([(title, f"https://r{i}.com/p", 9)]) for i in range(9)}}
    ev = only_event(run(feeds, [src("a")] + [src(f"r{i}", "SOCIAL") for i in range(9)]))
    assert ev["status"] != "CONFIRMED"


def test_duplicate_volume_from_one_outlet_does_not_inflate_pulse():
    title = "Incêndio atinge galpão em Campinas e mobiliza bombeiros"
    one = only_event(run({"a": rss([(title, "https://a.com/n0", 5)])}))
    many = only_event(run({"a": rss([(title, f"https://a.com/n{i}", 5 + i % 50) for i in range(1000)])}))
    assert many["pulse"] <= one["pulse"] + 5


def test_paraphrased_coverage_of_one_story_is_one_event():
    titles = ["Deslizamento de terra atinge casas em Petrópolis", "Petrópolis: chuva provoca deslizamento e soterra imóveis",
              "Defesa Civil confirma deslizamento em Petrópolis após temporal",
              "Moradores de Petrópolis são retirados após deslizamento"]
    b = run({f"s{i}": rss([(t, f"https://s{i}.com/x", 10 + i)]) for i, t in enumerate(titles)})
    assert len(b["events"]) == 1 and b["events"][0]["source_count"] == 4


@pytest.mark.xfail(strict=True, reason="QA-006: resposta vazia com transporte ok vira OFFLINE (conta como falha de rede)")
def test_empty_body_is_content_problem_not_transport_failure():
    h = run({"s0": b""})["source_health"][0]
    assert h["status"] == "DEGRADED"


# ---------------------------------------------------------------- correção em SHADOW: flag NOISE_GATE (padrão desligada)
# Os mesmos ataques acima, com a flag ligada: provam a correção de QA-001..004 sem mudar a produção até o Reliability Gate.

@pytest.fixture
def noise_gate(monkeypatch):
    monkeypatch.setenv("PULSO_FLAG_NOISE_GATE", "1")


@pytest.mark.usefixtures("noise_gate")
@pytest.mark.parametrize("name", list(NOISE))
@pytest.mark.parametrize("outlets", [6, 10])
def test_gate_noise_stays_n1_at_any_volume(name, outlets):
    b = run(same_story(NOISE[name], outlets))
    assert top_level(b) <= 1  # nem evento (PR #89) ou teto N1 (NOISE_GATE)
    for ev in b["events"]:
        assert any(x["key"] == "noise_gate" for x in ev["score_breakdown"])  # o teto aparece no "POR QUE?"


@pytest.mark.usefixtures("noise_gate")
@pytest.mark.parametrize("name", list(INCIDENTS_UNDERRATED))
def test_gate_operational_incidents_reach_n2(name):
    assert only_event(run(same_story(INCIDENTS_UNDERRATED[name], 4)))["alert_level"] >= 2


@pytest.mark.usefixtures("noise_gate")
@pytest.mark.parametrize("title", [
    "Apagão deixa bairros de São Paulo sem energia elétrica",
    "Prédio é evacuado após incêndio no centro de Belo Horizonte",
    "Enchente deixa desalojados em Porto Alegre após chuva forte",
    "Show termina em tumulto e deixa feridos em São Paulo",  # palavra de agenda + incidente: o incidente prevalece
    "Feriado tem acidente com mortos na rodovia em Minas Gerais",
])
def test_gate_keeps_recall_of_real_incidents(title):
    assert only_event(run(same_story(title, 4)))["alert_level"] >= 2


@pytest.mark.usefixtures("noise_gate")
def test_gate_incident_with_injured_outranks_football():
    football = top_level(run(same_story(NOISE["futebol"], 6)))
    tumult = only_event(run(same_story(INCIDENTS_UNDERRATED["tumulto_show"], 6)))
    assert tumult["alert_level"] > football


@pytest.mark.usefixtures("noise_gate")
def test_gate_identical_social_reposts_do_not_add_independence():
    title = "Incêndio atinge galpão em Campinas e mobiliza bombeiros"
    feeds = {"a": rss([(title, "https://a.com/1", 10)]),
             **{f"r{i}": rss([(title, f"https://r{i}.com/p", 9)]) for i in range(9)}}
    ev = only_event(run(feeds, [src("a")] + [src(f"r{i}", "SOCIAL") for i in range(9)]))
    assert ev["source_count"] == 1 and ev["status"] != "CONFIRMED"


@pytest.mark.usefixtures("noise_gate")
def test_gate_social_reports_with_their_own_words_still_count():
    feeds = {"a": rss([("Incêndio atinge galpão em Campinas e mobiliza bombeiros", "https://a.com/1", 10)]),
             "r1": rss([("Incêndio atinge galpão em Campinas, bombeiros no local agora", "https://r1.com/p", 9)]),
             "r2": rss([("Bombeiros chegando no incêndio do galpão em Campinas", "https://r2.com/p", 8)])}
    ev = only_event(run(feeds, [src("a"), src("r1", "SOCIAL"), src("r2", "SOCIAL")]))
    assert ev["source_count"] == 3  # relato próprio continua sendo evidência


@pytest.mark.usefixtures("noise_gate")
def test_gate_duplicate_volume_does_not_inflate_pulse():
    title = "Incêndio atinge galpão em Campinas e mobiliza bombeiros"
    one = only_event(run({"a": rss([(title, "https://a.com/n0", 5)])}))
    many = only_event(run({"a": rss([(title, f"https://a.com/n{i}", 5 + i % 50) for i in range(1000)])}))
    assert many["pulse"] <= one["pulse"] + 5


@pytest.mark.usefixtures("noise_gate")
def test_gate_reduced_coverage_never_raises_confidence():
    titles = ["Incêndio atinge galpão em Campinas e mobiliza bombeiros", "Bombeiros combatem incêndio em galpão de Campinas",
              "Galpão pega fogo em Campinas; bombeiros no local", "Incêndio de grandes proporções em galpão de Campinas"]
    confs = [only_event(run({f"s{i}": rss([(t, f"https://s{i}.com/x", 10)]) for i, t in enumerate(titles[:k])}))["confidence"]
             for k in (4, 3, 2)]
    assert confs == sorted(confs, reverse=True)
