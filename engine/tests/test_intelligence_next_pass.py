from datetime import datetime, timedelta, timezone

import pytest

from pulso_engine.events import is_publishable, stats_for, status_for
from pulso_engine.models import Signal
from pulso_engine.processing.clustering import Cluster, cluster_signals
from pulso_engine.processing.importance import EDITORIAL_ONLY, POTENTIAL_INCIDENT, SCHEDULED_CONTEXT, assess

NOW = datetime(2026, 10, 3, 18, 0, tzinfo=timezone.utc)


def sig(i, title, *, source=None, category="OTHER", state=None, minutes=10, cls="NEWS_HIGH"):
    return Signal(signal_id=f"next-{i}", source_id=source or f"outlet-{i}", source_class=cls,
                  timestamp=NOW - timedelta(minutes=minutes), collected_at=NOW, title=title,
                  category=category, state=state, geo_confidence=90 if state else None, hash=f"hash-{i}")


def cluster(signals):
    c = Cluster()
    for s in signals:
        c.add(s, frozenset())
    return c


EDITORIAL = [
    "Flamengo vence Palmeiras e assume liderança do campeonato",
    "Flamengo x Palmeiras: onde assistir e escalações",
    "Apostas e odds para o clássico deste domingo",
    "Show da Anitta reúne público no Rio; veja ingressos",
    "Feriado de 12 de outubro: veja o que abre e fecha",
]


@pytest.mark.parametrize("volume", [1, 10, 50, 100, 500, 1000])
@pytest.mark.parametrize("title", EDITORIAL)
def test_editorial_and_scheduled_bursts_never_publish(volume, title):
    assert assess(title).role in (EDITORIAL_ONLY, SCHEDULED_CONTEXT)
    assert not is_publishable(cluster([sig(i, title) for i in range(volume)]))


@pytest.mark.parametrize("title, category", [
    ("Linha 3 do metrô interrompida após falha elétrica", "TRAFFIC"),
    ("Torcedores evacuados após incêndio no estádio", "SECURITY"),
    ("Apagão deixa bairros sem energia durante a partida", "INFRASTRUCTURE"),
    ("Show cancelado: falha no transporte deixa passageiros retidos", "TRAFFIC"),
])
def test_sport_and_concert_context_does_not_hide_real_incident(title, category):
    assert assess(title).role == POTENTIAL_INCIDENT
    assert is_publishable(cluster([sig(i, title, category=category) for i in range(3)]))


def test_republication_volume_is_one_origin_for_event_statistics():
    signals = [sig(i, "Incêndio atinge galpão em Campinas", source=f"publisher-{i}") for i in range(1000)]
    stats = stats_for(signals, NOW)
    assert stats.independent_sources == 1
    assert stats.velocity_per_hour == 1


def test_social_reposts_do_not_confirm_one_story():
    signals = [sig(0, "Incêndio atinge galpão em Campinas", source="news", cls="NEWS_HIGH")]
    signals += [sig(i, "Incêndio atinge galpão em Campinas", source=f"social-{i}", cls="SOCIAL") for i in range(1, 10)]
    stats = stats_for(signals, NOW)
    assert stats.independent_sources == 1 and status_for(stats) == "DETECTED"


def test_contradiction_is_first_class_and_not_four_confirmations():
    stats = stats_for([sig(0, "Interrupção confirmada", source="a"), sig(1, "Serviço normalizado", source="official", cls="OFFICIAL")], NOW, contradiction=1.0)
    assert status_for(stats) == "DISPUTED"


def test_paraphrases_of_same_incident_cluster_without_merging_cities():
    same_city = [
        sig(0, "Deslizamento de terra atinge casas em Petrópolis", state="RJ"),
        sig(1, "Petrópolis: chuva provoca deslizamento e soterra imóveis", source="b", state="RJ"),
        sig(2, "Defesa Civil confirma deslizamento em Petrópolis após temporal", source="c", state="RJ"),
        sig(3, "Moradores de Petrópolis são retirados após deslizamento", source="d", state="RJ"),
    ]
    assert len(cluster_signals(same_city)) == 1
    different_city = [same_city[0], sig(4, "Deslizamento atinge casas em Guarulhos", source="e", state="SP")]
    assert len(cluster_signals(different_city)) == 2


def test_ingestion_order_is_stable_for_adversarial_cluster():
    signals = [sig(i, title, source=f"s{i}") for i, title in enumerate([
        "Deslizamento em Petrópolis após temporal", "Petrópolis tem casas atingidas por deslizamento",
        "Defesa Civil confirma deslizamento em Petrópolis",
    ])]
    shapes = {tuple(sorted(tuple(c.member_tokens[i]) for i in range(len(c.member_tokens)))) for c in cluster_signals(signals)}
    reverse = {tuple(sorted(tuple(c.member_tokens[i]) for i in range(len(c.member_tokens)))) for c in cluster_signals(list(reversed(signals)))}
    assert shapes == reverse
