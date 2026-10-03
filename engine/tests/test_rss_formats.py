import gzip
import io
from datetime import datetime, timezone

import pytest

from pulso_engine.collectors.news import rss
from pulso_engine.collectors.news.rss import RssAdapter

NOW = datetime(2026, 10, 2, 18, 0, tzinfo=timezone.utc)

RDF = """<?xml version="1.0" encoding="utf-8" ?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/elements/1.1/"
         xmlns="http://purl.org/rss/1.0/">
  <channel rdf:about="https://www.gov.br/mdr/pt-br/RSS"><title>MDR</title></channel>
  <item rdf:about="https://www.gov.br/mdr/pt-br/noticias/preparacao-chuvas">
    <title>Começa preparação para fortes chuvas no Sul e Sudeste</title>
    <link>https://www.gov.br/mdr/pt-br/noticias/preparacao-chuvas</link>
    <description>Defesa Civil monitora risco de deslizamento.</description>
    <dc:date>2026-10-02T15:10:00Z</dc:date>
  </item>
</rdf:RDF>""".encode()


def test_rss1_rdf_items_are_read():
    src = {"id": "mdr", "source_class": "OFFICIAL", "url": "https://x"}
    (sig,) = RssAdapter(src, None, lambda u: RDF, lambda: NOW).run()
    assert sig.title.startswith("Começa preparação") and sig.source_class == "OFFICIAL"
    assert sig.timestamp == datetime(2026, 10, 2, 15, 10, tzinfo=timezone.utc)


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch(monkeypatch, payload: bytes):
    monkeypatch.setattr(rss.urllib.request, "urlopen", lambda req, timeout=0: _Resp(payload))


def test_http_fetch_decompresses_gzip(monkeypatch):
    _patch(monkeypatch, gzip.compress(b"<rss><channel/></rss>"))
    assert rss.http_fetch("https://x") == b"<rss><channel/></rss>"


def test_http_fetch_refuses_decompression_bomb(monkeypatch):
    monkeypatch.setattr(rss, "MAX_BYTES", 1000)
    _patch(monkeypatch, gzip.compress(b"A" * 100_000))  # pequeno comprimido, grande descomprimido
    with pytest.raises(ValueError, match="descomprimido"):
        rss.http_fetch("https://x")


def _items(xml: str):
    src = {"id": "t", "source_class": "NEWS_HIGH", "url": "https://x"}
    return RssAdapter(src, None, lambda u: xml.encode(), lambda: NOW).run()


def test_tolerates_bare_ampersand_and_html_entities():
    xml = ("<rss><channel><item><title>Chuva forte&nbsp;e alagamento em S&atilde;o Paulo & regi&#227;o</title>"
           "<link>https://x/a</link><pubDate>Fri, 02 Oct 2026 17:00:00 GMT</pubDate></item></channel></rss>")
    (sig,) = _items(xml)
    assert "alagamento" in sig.title and "&" in sig.title and "São Paulo" in sig.title


def test_entity_declarations_are_still_refused():
    xml = '<!DOCTYPE r [<!ENTITY x "boom">]><rss><channel><item><title>&x;</title></item></channel></rss>'
    with pytest.raises(ValueError, match="ENTITY"):
        _items(xml)


def test_regional_feed_gives_state_to_items_without_a_place():
    xml = ("<rss><channel><item><title>Obras de drenagem avançam e chuva forte preocupa moradores</title>"
           "<link>https://x/b</link><pubDate>Fri, 02 Oct 2026 17:00:00 GMT</pubDate></item></channel></rss>")
    src = {"id": "g1-rs", "source_class": "NEWS_REGIONAL", "url": "https://x", "state": "RS"}
    (sig,) = RssAdapter(src, None, lambda u: xml.encode(), lambda: NOW).run()
    assert sig.state == "RS" and sig.geo_precision == "STATE" and sig.geo_confidence == 35
    national = {**src, "state": None}
    (sig2,) = RssAdapter(national, None, lambda u: xml.encode(), lambda: NOW).run()
    assert sig2.state is None


def test_place_in_text_wins_over_source_state():
    xml = ("<rss><channel><item><title>Enchente atinge Porto Alegre</title><link>https://x/c</link>"
           "<pubDate>Fri, 02 Oct 2026 17:00:00 GMT</pubDate></item></channel></rss>")
    src = {"id": "g1-sc", "source_class": "NEWS_REGIONAL", "url": "https://x", "state": "SC"}
    (sig,) = RssAdapter(src, None, lambda u: xml.encode(), lambda: NOW).run()
    assert sig.state == "RS" and sig.city is not None


def test_uppercase_markup_entities_cannot_inject_xml_elements():
    xml = ("<rss><channel><item><title>Alerta &LT;item&GT;&LT;title&GT;FALSO&LT;/title&GT;&LT;/item&GT; de chuva forte</title>"
           "<link>https://x/e</link><pubDate>Fri, 02 Oct 2026 17:00:00 GMT</pubDate></item></channel></rss>")
    sigs = _items(xml)
    assert len(sigs) == 1  # nenhum <item> falso nasceu do texto
    assert "<item>" in sigs[0].title or "FALSO" in sigs[0].title  # virou texto
