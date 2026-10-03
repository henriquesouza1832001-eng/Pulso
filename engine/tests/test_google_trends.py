from datetime import datetime, timezone

from pulso_engine.collectors.social.google_trends import GoogleTrendsAdapter, _traffic

SRC = {"id": "google-trends-br", "adapter": "google_trends", "source_class": "SOCIAL", "url": "https://trends/rss", "min_importance": 45}
NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def item(term, headline, url="https://g1.globo.com/x/noticia.ghtml", traffic="5 mil+"):
    return (f'<item><title>{term}</title><ht:approx_traffic>{traffic}</ht:approx_traffic><pubDate>Sat, 3 Oct 2026 08:00:00 -0700</pubDate>'
            f'<ht:news_item><ht:news_item_title>{headline}</ht:news_item_title><ht:news_item_url>{url}</ht:news_item_url></ht:news_item></item>')


def run(*items):
    xml = ('<rss xmlns:ht="https://trends.google.com/trending/rss"><channel>' + "".join(items) + "</channel></rss>").encode()
    return GoogleTrendsAdapter(SRC, None, lambda u: xml, lambda: NOW).run()


def test_traffic_parsing():
    assert [_traffic(x) for x in ("500+", "2 mil+", "1 mi+", "", None)] == [500, 2000, 1_000_000, 0, 0]


def test_impactful_trend_becomes_social_signal_and_celebrity_is_dropped():
    sigs = run(item("enchente", "Enchente deixa mortos e desabrigados em Recife, diz Defesa Civil"),
               item("ben affleck", "Ben Affleck quebra o silêncio sobre vida amorosa", url="https://x.com/a/b"))
    assert len(sigs) == 1
    s = sigs[0]
    assert s.source_class == "SOCIAL" and "5.000 buscas" in s.text and s.title.startswith("Enchente")
    assert s.state == "PE"


def test_item_without_news_is_ignored():
    assert run('<item><title>enchente</title><ht:approx_traffic>1 mi+</ht:approx_traffic></item>') == []
