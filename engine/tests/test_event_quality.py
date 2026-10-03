"""Qualidade dos eventos: sem encadeamento de matérias, estado por maioria, publicação criteriosa."""
from datetime import datetime, timedelta, timezone

from pulso_engine.events import event_place, is_publishable
from pulso_engine.models import Signal
from pulso_engine.processing.clustering import cluster_signals

NOW = datetime(2026, 10, 2, 18, 0, tzinfo=timezone.utc)


def sig(i, title, source="a", cls="NEWS_HIGH", cat="POLITICS", state=None, conf=None, minutes=10, text=None):
    return Signal(
        signal_id=f"s{i}", source_id=source, source_class=cls, timestamp=NOW - timedelta(minutes=minutes),
        collected_at=NOW, title=title, category=cat, text=text, hash=f"h{i}", state=state, geo_confidence=conf,
        latitude=-10.0 if state else None, longitude=-50.0 if state else None,
    )


def test_broad_topic_does_not_chain_into_one_giant_event():
    # Pauta ampla: cada título compartilha termos com o vizinho, mas são matérias diferentes.
    titles = [
        "Eleições 2026 horários de votação domingo candidatos presidente",
        "Eleições 2026 candidatos presidente debate último domingo campanha",
        "Eleições 2026 campanha governador candidatos debate pesquisa Datafolha",
        "Eleições 2026 pesquisa Datafolha governador candidatos empate técnico São Paulo",
        "Eleições 2026 empate técnico São Paulo senado candidatos pesquisa Quaest",
        "Eleições 2026 pesquisa Quaest senado Minas candidatos apuração urnas",
        "Eleições 2026 apuração urnas Minas segundo turno resultado oficial TSE",
        "Eleições 2026 resultado oficial TSE segundo turno ministro Moraes decisão",
    ]
    clusters = cluster_signals([sig(i, t, source=f"s{i}", minutes=60 - i) for i, t in enumerate(titles)])
    assert max(len(c.signals) for c in clusters) < len(titles)


def test_same_story_from_many_outlets_still_groups():
    titles = ["Enchente atinge Porto Alegre e deixa desabrigados", "Enchente em Porto Alegre deixa milhares de desabrigados",
              "Porto Alegre enchente: desabrigados passam de mil", "Desabrigados da enchente em Porto Alegre chegam a mil"]
    clusters = cluster_signals([sig(i, t, source=f"s{i}", cat="WEATHER") for i, t in enumerate(titles)])
    assert len(clusters) == 1 and len(clusters[0].signals) == 4


def test_confidently_different_states_do_not_merge():
    a = sig(1, "Deslizamento deixa mortos e desabrigados na cidade", source="a", cat="WEATHER", state="RJ", conf=90)
    b = sig(2, "Deslizamento deixa mortos e desabrigados na cidade", source="b", cat="WEATHER", state="SP", conf=90)
    assert len(cluster_signals([a, b])) == 2


def test_event_state_is_the_majority_or_none_for_national_topics():
    rs = [sig(i, "x", source=f"s{i}", state="RS", conf=80) for i in range(3)] + [sig(9, "x", source="z", state="SC", conf=35)]
    assert event_place(rs).state == "RS"
    spread = [sig(i, "x", source=f"s{i}", state=uf, conf=35) for i, uf in enumerate(["AC", "AL", "AM", "AP", "MA"])]
    assert event_place(spread) is None  # pauta nacional não vira um estado arbitrário


def test_publishability_policy():
    from pulso_engine.processing.clustering import Cluster

    def cl(*signals):
        c = Cluster()
        for s in signals:
            c.add(s, frozenset())
        return c

    assert not is_publishable(cl(sig(1, "Câmara aprova projeto sobre eleições", cat="POLITICS")))  # isolada
    assert is_publishable(cl(sig(1, "Câmara aprova projeto", source="a"), sig(2, "Câmara aprova projeto", source="b")))
    assert is_publishable(cl(sig(1, "Aviso INMET: tempestade", cls="OFFICIAL", cat="WEATHER")))
    assert is_publishable(cl(sig(1, "Deslizamento deixa 3 mortos", cat="WEATHER")))
    assert not is_publishable(cl(sig(1, "Chuva forte molha a cidade", cat="WEATHER")))  # sem impacto no texto
    assert not is_publishable(cl(sig(1, "Algo qualquer", cat="OTHER")))


def test_inherited_source_state_does_not_place_a_national_story():
    sigs = [sig(i, "x", source=f"s{i}") for i in range(5)] + [sig(9, "x", source="rn", state="RN", conf=35)]
    assert event_place(sigs) is None
    assert event_place([sig(1, "x", source="a"), sig(9, "x", source="rn", state="RN", conf=90)]).state == "RN"  # notícia local pequena
    # pauta nacional (7 fontes) em que UM sinal cita o Amazonas: não vira evento do AM
    national = [sig(i, "x", source=f"s{i}") for i in range(6)] + [sig(9, "x", source="am", state="AM", conf=90)]
    assert event_place(national) is None
    # mas quando uma parte relevante dos sinais cita o estado, ele vale
    local = [sig(i, "x", source=f"s{i}", state="AM", conf=90) for i in range(3)] + [sig(9, "x", source="z"), sig(10, "x", source="y")]
    assert event_place(local).state == "AM"


def test_title_decides_the_category_before_the_summary():
    from pulso_engine.collectors.news.rss import RssAdapter
    xml = ("<rss><channel><item><title>AGU pede ao STF que declare leis das bets inconstitucionais</title>"
           "<link>https://x/d</link><description>Em ato no tribunal, o advogado-geral falou do bloqueio.</description>"
           "<pubDate>Fri, 02 Oct 2026 17:00:00 GMT</pubDate></item></channel></rss>")
    src = {"id": "t", "source_class": "NEWS_HIGH", "url": "https://x"}
    (s,) = RssAdapter(src, None, lambda u: xml.encode(), lambda: NOW).run()
    assert s.category == "POLITICS"


def test_text_impact_raises_severity_within_the_same_category():
    from pulso_engine.events import stats_for
    routine = [sig(1, "Chuva forte molha a cidade nesta sexta-feira", cat="WEATHER")]
    deadly = [sig(2, "Enchente deixa 3 mortos e desabrigados na cidade", cat="WEATHER")]
    gossip = [sig(3, "Famosos comentam o casamento da novela e a fofoca do BBB", cat="WEATHER")]
    r, d, g = (stats_for(x, NOW).severity for x in (routine, deadly, gossip))
    assert d >= r + 10  # mortes pesam bem mais que o relato de rotina
    assert g <= r       # entretenimento nunca sobe a severidade
    assert d <= 100
