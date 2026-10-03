"""Achados da TERCEIRA revisão independente (nível máximo, 2026-10-03): cada um vira um teste que falha sem a correção."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from pulso_engine.collectors.news.rss import RssAdapter, _sanitize_xml
from pulso_engine.collectors.official.usgs import UsgsAdapter
from pulso_engine.forecast_surge import make_surge_forecasts
from pulso_engine.processing.geo import locate
from pulso_engine.processing.keyword_engine import KeywordEngine

NOW = datetime(2026, 10, 3, 12, 2, tzinfo=timezone.utc)


# ---- geografia: Mato Grosso do Sul, siglas, empresas, clubes ---------------------------------------------------------
@pytest.mark.parametrize("text,uf", [
    ("Chuva forte atinge Mato Grosso do Sul", "MS"),
    ("Governo do Mato Grosso do Sul decreta emergência", "MS"),
    ("Chuva forte atinge Mato Grosso e deixa desabrigados", "MT"),
    ("Cuiabá, capital de Mato Grosso", "MT"),
])
def test_mato_grosso_do_sul_is_not_mato_grosso(text, uf):
    assert locate(text).uf == uf


@pytest.mark.parametrize("text", [
    "Economia alemã encolhe no trimestre",                 # "alema" (Assembleia do MA) é o dobrado de "alemã"
    "Ministério da Saúde (MS) amplia vacinação",           # MS = Ministério da Saúde
    "Barreiras comerciais pressionam o dólar",
    "Porto Seguro lucra R$ 1 bilhão no trimestre",         # empresa
    "Campeonato Paulista tem rodada neste fim de semana",  # torneio
    "Atlético Mineiro vence o clássico",                   # clube
    "A prefeitura abre as Santa Maria festas",             # nome comum, sem contexto
])
def test_words_companies_and_clubs_do_not_become_places(text):
    assert locate(text) is None, text


def test_real_places_with_context_still_work():
    assert locate("temporal em Barreiras derruba árvores").uf == "BA"
    assert locate("prefeitura de Porto Seguro decreta emergência").uf == "BA"
    assert locate("Assembleia Legislativa e Alema aprovam projeto, diz governo maranhense").uf == "MA"
    assert locate("governo paulista anuncia obras").uf == "SP"
    assert locate("Campo Grande, MS registra chuva").uf == "MS"


# ---- XML: nada de "&amp;" dentro de CDATA ---------------------------------------------------------------------------------
def test_cdata_is_kept_literal_while_text_outside_is_sanitised():
    raw = (b"<item><link><![CDATA[https://x.com/a?utm_source=t&id=7&utm_medium=m]]></link>"
           b"<title>A & B &nbsp;C</title></item>")
    out = _sanitize_xml(raw)
    assert b"<![CDATA[https://x.com/a?utm_source=t&id=7&utm_medium=m]]>" in out  # literal, intacto
    assert b"<title>A &amp; B \xc2\xa0C</title>" in out  # fora do CDATA: '&' escapado e &nbsp; resolvido


def test_url_with_ampersand_in_cdata_keeps_its_real_id_and_loses_tracking():
    xml = ("<rss><channel><item><title>Enchente deixa mortos em Porto Alegre</title>"
           "<link><![CDATA[https://x.com/n?id=7&utm_source=t&utm_medium=m]]></link>"
           "<pubDate>Sat, 03 Oct 2026 11:50:00 GMT</pubDate></item></channel></rss>")
    src = {"id": "t", "source_class": "NEWS_HIGH", "url": "https://x"}
    (s,) = RssAdapter(src, None, lambda u: xml.encode(), lambda: NOW).run()
    assert s.canonical_url == "https://x.com/n?id=7"  # antes: '...?id=7&amp;utm_source=t...' (rastreio não removido)
    assert "&amp;" not in s.url


# ---- vocabulário: "irã" dobrava para "ira" (raiva) ------------------------------------------------------------------------
def test_anger_is_not_iran():
    assert KeywordEngine().classify("A ira dos torcedores contra o técnico cresce") is None


# ---- USGS: só vale o país que o USGS declara ------------------------------------------------------------------------------
def test_usgs_quakes_in_neighbouring_countries_are_not_placed_in_brazil():
    def quake(title, lon, lat):
        return {"properties": {"title": title, "url": "https://usgs/" + title, "time": 1790990000000}, "geometry": {"coordinates": [lon, lat, 10]}}
    body = {"features": [quake("M 6.0 - 20 km S of Iquique, Chile", -70.1, -20.3), quake("M 5.8 - 10 km N of La Paz, Bolivia", -68.1, -16.5),
                         quake("M 5.1 - 30 km E of Cruzeiro do Sul, Brazil", -72.0, -7.6)]}
    src = {"id": "u", "adapter": "usgs", "source_class": "OFFICIAL", "url": "https://x"}
    sigs = {s.title: s for s in UsgsAdapter(src, None, lambda u: json.dumps(body).encode(), lambda: NOW).run()}
    assert sigs["Terremoto: M 6.0 - 20 km S of Iquique, Chile"].latitude is None
    assert sigs["Terremoto: M 5.8 - 10 km N of La Paz, Bolivia"].latitude is None
    assert sigs["Terremoto: M 5.1 - 30 km E of Cruzeiro do Sul, Brazil"].latitude == -7.6


# ---- previsões de volume: id estável dentro da hora -------------------------------------------------------------------------
def test_volume_forecast_ids_do_not_change_when_the_current_volume_changes_within_the_hour():
    def rows(extra):
        out = []
        for h in range(40):  # 40 h de histórico
            for b in range(12):
                out.append({"scope": "BR", "category": "WEATHER", "bucket": (NOW.replace(minute=0) - timedelta(hours=40 - h, minutes=-5 * b)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "signals": 1 + (h % 3), "sources": 1})
        # volume da hora corrente muda de um ciclo para o outro
        for b in range(1, 1 + extra):
            out.append({"scope": "BR", "category": "WEATHER", "bucket": (NOW.replace(minute=0) - timedelta(minutes=5 * b)).strftime("%Y-%m-%dT%H:%M:%SZ"), "signals": 6, "sources": 1})
        return out
    a = {f["forecast_id"] for f in make_surge_forecasts(rows(2), NOW)}
    b = {f["forecast_id"] for f in make_surge_forecasts(rows(4), NOW + timedelta(minutes=5))}
    assert a and a == b  # antes, o limiar (e portanto o id) mudava a cada ciclo e as previsões se acumulavam
    assert all(len(i) <= 105 for i in a)
