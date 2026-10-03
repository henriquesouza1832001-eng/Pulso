"""Precisão da categoria pelo caminho completo do coletor (título -> categoria final), com manchetes reais de 2026-10-02/03."""
from datetime import datetime, timezone

import pytest

from pulso_engine.collectors.news.rss import RssAdapter

NOW = datetime(2026, 10, 3, 4, 0, tzinfo=timezone.utc)


def category_of(title: str, state=None) -> str:
    xml = (f"<rss><channel><item><title>{title}</title><link>https://x/{abs(hash(title))}</link>"
           "<pubDate>Sat, 03 Oct 2026 03:00:00 GMT</pubDate></item></channel></rss>")
    src = {"id": "t", "source_class": "NEWS_HIGH", "url": "https://x", "state": state}
    sigs = RssAdapter(src, None, lambda u: xml.encode(), lambda: NOW).run()
    return sigs[0].category if sigs else "DROPPED"


@pytest.mark.parametrize("title", [
    "Ataques russos atingem pontes na Ucrânia e causam congestionamento caótico",
    "Surto de dengue na Flórida é o maior registrado nos Estados Unidos continentais",
    "Protestos estudantis na França deixam 40 diretores feridos",
    "Incêndio de grandes proporções atinge refinaria nos Estados Unidos e deixa feridos",
])
def test_physical_events_abroad_count_as_international(title):
    assert category_of(title) == "INTERNATIONAL"


@pytest.mark.parametrize("title,expected", [
    ("Acidente envolvendo três caminhões mata motorista e bloqueia BR-282, na Grande Florianópolis", "TRAFFIC"),
    ("Dois incêndios em pasto e casa abandonada mobilizam Bombeiros em Colatina", "EMERGENCY"),
    ("Incêndio atinge prédio e bombeiros fazem resgate de moradores", "EMERGENCY"),
    ("Temporal destelha imóveis e derruba mais de 20 árvores em São José do Calçado", "WEATHER"),
    ("Casal é assassinado a tiros dentro de casa e em cima da cama no Pará", "SECURITY"),
    ("Enchente atinge Porto Alegre e deixa mortos", "WEATHER"),
])
def test_brazilian_physical_events_keep_their_category(title, expected):
    assert category_of(title) == expected


@pytest.mark.parametrize("title,expected", [
    ("Lula e Flávio evitam escolher lado, mas China está no bastidor da eleição", "POLITICS"),
    ("Lula pede ao TSE que suspensão de serviços da embaixada dos EUA seja incluída em investigação", "POLITICS"),
    ("Dólar sobe com tensão nos EUA e pressiona o Banco Central", "ECONOMY"),
])
def test_politics_and_economy_are_not_flipped_by_foreign_mentions(title, expected):
    assert category_of(title) == expected


@pytest.mark.parametrize("title", [
    "Vasco tem aval dos Bombeiros para jogar em São Januário contra Boca Juniors",
    "Supremo mantém norma nacional sobre estrutura das PMs e dos bombeiros",
])
def test_generic_firefighter_mentions_are_not_emergencies(title):
    assert category_of(title) not in ("EMERGENCY",)


def test_metaphors_and_roundups_do_not_become_traffic_or_emergency():
    assert category_of("Na canetada contra as bets, Lula atropela o combate à ludopatia") != "TRAFFIC"
    assert category_of("Saldo de apostadores em bets cai 31% desde 26 de setembro; R$ 1,45 bilhão ainda aguarda resgate") != "EMERGENCY"
