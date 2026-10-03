from datetime import datetime, timedelta, timezone

import pytest

from pulso_engine.collectors.news.rss import RssAdapter
from pulso_engine.pipeline import chunks, run_once
from pulso_engine.processing.geo import locate
from pulso_engine.processing.normalizer import canonical_url, content_hash

NOW = datetime(2026, 10, 2, 20, 0, tzinfo=timezone.utc)


def rss(*items: tuple[str, str, int]) -> bytes:
    body = "".join(
        f"<item><title>{t}</title><link>{l}</link><description>d</description>"
        f"<pubDate>{(NOW - timedelta(minutes=m)).strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate></item>"
        for t, l, m in items
    )
    return f"<?xml version='1.0'?><rss><channel>{body}</channel></rss>".encode()


def src(i: str, cls: str = "NEWS_HIGH") -> dict:
    return {"id": i, "name": i, "domain": f"{i}.com", "adapter": "rss", "source_class": cls, "url": f"https://{i}.com/rss", "state": None}


def test_canonical_url_strips_tracking():
    assert canonical_url("HTTPS://Site.com/a/?utm_source=x&id=3#frag") == "https://site.com/a?id=3"
    assert canonical_url("javascript:alert(1)") is None
    assert content_hash(canonical_url("https://s.com/a?utm_x=1"), "t") == content_hash("https://s.com/a", "outro")


def test_geo_is_conservative():
    assert locate("Acidente grave em Belo Horizonte").uf == "MG"
    assert locate("Chuva forte atinge Minas Gerais").precision == "STATE"
    assert locate("Natal de luz atrai turistas") is None  # festa, não a cidade
    assert locate("Tarifa de energia sobe") is None


def test_same_story_in_three_sources_becomes_one_event():
    feeds = {
        "https://a.com/rss": rss(("Temporal causa alagamento em Belo Horizonte e deixa feridos", "https://a.com/1", 30)),
        "https://b.com/rss": rss(("Alagamento em Belo Horizonte após temporal deixa feridos", "https://b.com/9", 20)),
        "https://c.com/rss": rss(("Temporal e alagamento em Belo Horizonte: feridos", "https://c.com/x", 10),
                                 ("Receita de bolo de cenoura", "https://c.com/bolo", 5)),
    }
    batch = run_once([src("a"), src("b"), src("c")], lambda u: feeds[u], NOW)
    assert len(batch["events"]) == 1  # a receita (OTHER, 1 fonte) não vira evento
    ev = batch["events"][0]
    assert ev["source_count"] == 3 and ev["signal_count"] == 3
    assert ev["category"] == "WEATHER" and ev["state"] == "MG" and ev["status"] == "CONFIRMED"
    assert all(s["event_id"] == ev["event_id"] for s in batch["signals"])
    assert batch["pulses"][0]["scope"] == "BR" and batch["pulses"][0]["score"] > 0


def test_duplicate_url_counts_once():
    feeds = {"https://a.com/rss": rss(("Acidente na rodovia", "https://a.com/1?utm_source=x", 5), ("Acidente na rodovia", "https://a.com/1", 4))}
    assert len(run_once([src("a")], lambda u: feeds[u], NOW)["signals"]) == 1


def test_failing_source_does_not_stop_the_cycle():
    def fetch(u: str) -> bytes:
        if "bad" in u:
            raise TimeoutError("boom")
        return rss(("Protesto bloqueia avenida em São Paulo", "https://ok.com/1", 3))
    batch = run_once([src("bad"), src("ok")], fetch, NOW)
    health = {h["source_id"]: h["status"] for h in batch["source_health"]}
    assert health == {"bad": "OFFLINE", "ok": "ONLINE"}
    assert len(batch["events"]) == 1


def test_unregistered_adapter_is_reported_not_silently_skipped():
    s = {**src("novo"), "adapter": "inexistente"}
    batch = run_once([s], lambda u: b"", NOW)
    h = batch["source_health"][0]
    assert h["status"] == "OFFLINE" and "não registrado" in h["detail"]


def test_latin1_feed_without_declaration_is_decoded():
    raw = "<rss><channel><item><title>Incêndio em Manaus</title><link>https://l.com/1</link></item></channel></rss>".encode("latin-1")
    sigs = RssAdapter(src("l"), fetcher=lambda u: raw, now=lambda: NOW).run()
    assert sigs[0].title == "Incêndio em Manaus" and sigs[0].state == "AM"


def test_entity_bomb_is_refused():
    bomb = b"<?xml version='1.0'?><!DOCTYPE x [<!ENTITY a 'aaaa'>]><rss><channel/></rss>"
    with pytest.raises(ValueError):
        RssAdapter(src("x"), fetcher=lambda u: bomb).fetch()


def test_future_dates_are_clamped_and_chunks_respect_limits():
    feeds = {"https://a.com/rss": rss(("Incêndio atinge prédio no Rio de Janeiro", "https://a.com/1", -600))}
    batch = run_once([src("a")], lambda u: feeds[u], NOW)
    assert batch["signals"][0]["timestamp"] == "2026-10-02T20:00:00Z"
    parts = chunks(batch, max_events=1)
    assert parts[-1]["pulses"] and all(len(p["events"]) <= 1 for p in parts)
