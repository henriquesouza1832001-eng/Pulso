"""Achados da revisão focada em processing/ (nível máximo, 2026-10-03)."""
import pytest

from pulso_engine.processing.geo import locate
from pulso_engine.processing.importance import assess
from pulso_engine.processing.normalizer import is_broadcast_listing


@pytest.mark.parametrize("text", [
    "WASHINGTON (AP) — Trump diz que a medida é temporária",
    "CIDADE DO MÉXICO (AP) — Tremor sacode a capital",
    "a informação foi divulgada pela AP nesta sexta",
    "segundo a AP, o acordo está perto",
])
def test_associated_press_is_not_amapa(text):
    assert locate(text) is None


def test_real_amapa_mentions_still_work():
    assert locate("Macapá (AP) registra chuva forte").uf == "AP"
    assert locate("Prefeito de Santana (AP) decreta emergência").uf == "AP"
    assert locate("tempestade deixa desabrigados no Amapá").uf == "AP"


@pytest.mark.parametrize("title", ["Assista ao jogo desta noite", "Assista ao show desta sexta-feira", "Assista ao debate desta quinta"])
def test_invitations_to_watch_something_are_not_tv_listings(title):
    assert not is_broadcast_listing(title)


@pytest.mark.parametrize("title", ["Assista ao JRO2 desta sexta-feira, 2", "Assista ao JPB1 desta quarta", "VÍDEO: AB2 de sexta-feira, 2 de outubro",
                                   "Vídeos: MA1 de quinta-feira, 1º de outubro"])
def test_tv_bulletin_codes_are_still_listings(title):
    assert is_broadcast_listing(title)


def test_a_real_disaster_with_an_entertainment_word_is_not_dropped_but_gossip_still_is():
    assert assess("Atentado em casamento deixa 20 mortos").is_important()
    assert assess("Explosão em festa de casamento deixa feridos e mortos").is_important()
    assert not assess("Ator morreu? famosos no casamento comentam a fofoca").is_important()
    assert not assess("Ronaldinho casou e famosos foram ao casamento").is_important()


def test_a_portuguese_santarem_is_not_para():
    assert locate("Santarém, em Portugal, tem festa de rua") is None
    assert locate("Câmara de Santarém, no Ribatejo, aprova obras") is None
    assert locate("chuva forte atinge Santarém e deixa desabrigados").uf == "PA"
