from datetime import datetime, timedelta, timezone

import pytest

from pulso_engine.events import is_publishable
from pulso_engine.models import Signal
from pulso_engine.processing.clustering import Cluster
from pulso_engine.processing.importance import (
    EDITORIAL_ONLY, OPERATIONAL_SIGNAL, POTENTIAL_INCIDENT, SCHEDULED_CONTEXT, assess,
)

NOW = datetime(2026, 10, 3, 18, 0, tzinfo=timezone.utc)


def sig(i, title, *, source=None, category="OTHER"):
    return Signal(signal_id=f"editorial-{i}", source_id=source or f"outlet-{i}", source_class="NEWS_HIGH",
                  timestamp=NOW - timedelta(minutes=i), collected_at=NOW, title=title,
                  category=category, hash=f"hash-{i}")


def cluster(signals):
    c = Cluster()
    for signal in signals:
        c.add(signal, frozenset())
    return c


@pytest.mark.parametrize("title", [
    "Brasil x Índia: onde assistir, horário e escalações",
    "Brasileirão Feminino: São Paulo recebe Corinthians; veja onde assistir",
    "Apostas do campeonato: odds e palpite para o jogo de hoje",
    "Resultado do jogo e classificação do campeonato ao vivo",
])
def test_sports_editorial_is_not_operational(title):
    assert assess(title).role == EDITORIAL_ONLY


def test_scheduled_context_is_not_an_incident():
    assert assess("Show e partida marcados para sábado, ingressos à venda").role == SCHEDULED_CONTEXT


@pytest.mark.parametrize("title, role", [
    ("Jogo interrompido após apagão no estádio", POTENTIAL_INCIDENT),
    ("Torcedores evacuam estádio após princípio de incêndio", POTENTIAL_INCIDENT),
    ("Estádio interditado por risco estrutural antes da partida", OPERATIONAL_SIGNAL),
])
def test_operational_sports_context_survives(title, role):
    assert assess(title).role == role


@pytest.mark.parametrize("volume", [10, 50, 100, 500, 1000])
def test_editorial_volume_alone_never_publishes(volume):
    signals = [sig(i, "Brasil x Índia: onde assistir e horário do jogo") for i in range(volume)]
    assert not is_publishable(cluster(signals))


@pytest.mark.parametrize("title, category", [
    ("Metrô para após falha elétrica e passageiros são retirados", "INFRASTRUCTURE"),
    ("Evacuação do estádio após princípio de incêndio", "SECURITY"),
    ("Apagão deixa bairros sem energia durante o jogo", "INFRASTRUCTURE"),
    ("Show cancelado após falha no transporte e evacuação", "TRAFFIC"),
])
def test_independent_operational_signals_are_publishable(title, category):
    signals = [sig(i, title, category=category) for i in range(3)]
    assert is_publishable(cluster(signals))


def test_editorial_paraphrases_and_tracking_noise_stay_blocked():
    titles = [
        "Brasil x Índia: saiba onde assistir ao jogo (utm_source=a)",
        "Jogo Brasil Índia: veja horário e transmissão exclusiva",
        "Onde ver Brasil contra Índia hoje; escalação provável",
    ]
    assert not is_publishable(cluster([sig(i, title) for i, title in enumerate(titles)]))
