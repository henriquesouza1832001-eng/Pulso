from datetime import datetime, timezone

from pulso_engine.collectors.news.rss import RssAdapter
from pulso_engine.processing.normalizer import is_broadcast_listing

NOW = datetime(2026, 10, 3, 3, 0, tzinfo=timezone.utc)


def test_tv_bulletin_listings_are_recognized():
    for t in [
        "Assista ao JRO2 desta sexta-feira, 2",
        "VÍDEOS: Jornal Anhanguera 2ª Edição de sexta-feira, 02 de outubro de 2026",
        "VÍDEO: AB2 de sexta-feira, 2 de outubro de 2026",
        "Vídeos: MA1 de quinta-feira, 1º de outubro",
        "Assista ao JPB1 desta quarta-feira",
    ]:
        assert is_broadcast_listing(t), t


def test_real_news_in_video_form_is_not_treated_as_listing():
    for t in [
        "Vídeo: Veja os horários de votação nas Eleições 2026",
        "Áudio: Eleitor vai votar duas vezes para senador",
        "Assista: bombeiros resgatam famílias durante enchente em Porto Alegre",
        "VÍDEO mostra deslizamento de terra em Petrópolis",
    ]:
        assert not is_broadcast_listing(t), t


def test_adapter_drops_listings_and_keeps_news():
    xml = ("<rss><channel>"
           "<item><title>Assista ao JRO2 desta sexta-feira, 2</title><link>https://x/1</link><pubDate>Fri, 02 Oct 2026 23:00:00 GMT</pubDate></item>"
           "<item><title>Enchente deixa mortos em Porto Alegre</title><link>https://x/2</link><pubDate>Fri, 02 Oct 2026 23:10:00 GMT</pubDate></item>"
           "</channel></rss>")
    src = {"id": "g1-ro", "source_class": "NEWS_REGIONAL", "url": "https://x", "state": "RO"}
    sigs = RssAdapter(src, None, lambda u: xml.encode(), lambda: NOW).run()
    assert [s.url for s in sigs] == ["https://x/2"]
