from datetime import datetime, timezone

from pulso_engine.pipeline import changed_events, changed_series, select_health


def ev(i, pulse=40, level=2, status="DETECTED", signals=3, sources=2):
    return {"event_id": f"ev-{i}", "pulse": pulse, "alert_level": level, "status": status,
            "signal_count": signals, "source_count": sources}


def known(*events):
    return [{k: e[k] for k in ("event_id", "pulse", "alert_level", "status", "signal_count", "source_count")} for e in events]


def test_unchanged_events_are_not_resent_but_relevant_changes_are():
    old = [ev(1), ev(2), ev(3), ev(4), ev(5), ev(6)]
    now = [ev(1), ev(2, pulse=41), ev(3, pulse=49), ev(4, level=3), ev(5, signals=6), ev(6, signals=4), ev(7)]
    sent = {e["event_id"] for e in changed_events(now, known(*old))}
    # ev-1 igual; ev-2 variou 1 ponto; ev-6 ganhou só +1 sinal; ev-3 variou 9 pontos; ev-5 saltou de 3 para 6 sinais; ev-7 é novo
    assert sent == {"ev-3", "ev-4", "ev-5", "ev-7"}


def test_without_digest_everything_is_sent_safely():
    now = [ev(1), ev(2)]
    assert changed_events(now, []) == now and changed_events(now, None) == now


def row(scope, cat, bucket, n):
    return {"scope": scope, "category": cat, "bucket": bucket, "signals": n, "sources": 1}


def test_series_only_new_or_larger_windows_are_sent():
    stored = [row("BR", "WEATHER", "2026-10-03T10:00:00Z", 5), row("BR", "WEATHER", "2026-10-03T10:05:00Z", 3)]
    now = [row("BR", "WEATHER", "2026-10-03T10:00:00Z", 5),   # igual
           row("BR", "WEATHER", "2026-10-03T10:05:00Z", 2),   # menor: o Worker guarda o maior
           row("BR", "WEATHER", "2026-10-03T10:10:00Z", 1),   # nova
           row("BR", "TRAFFIC", "2026-10-03T10:00:00Z", 4)]   # nova categoria
    assert [(r["category"], r["bucket"][-9:-1]) for r in changed_series(now, stored)] == [("WEATHER", "10:10:00"), ("TRAFFIC", "10:00:00")]
    assert changed_series(now, []) == now


def test_health_sends_only_problems_between_full_slots():
    health = [{"source_id": "a", "status": "ONLINE"}, {"source_id": "b", "status": "OFFLINE"}, {"source_id": "c", "status": "DEGRADED"}]
    mid = datetime(2026, 10, 3, 12, 17, tzinfo=timezone.utc)
    assert [h["source_id"] for h in select_health(health, mid)] == ["b", "c"]
    slot = datetime(2026, 10, 3, 12, 31, tzinfo=timezone.utc)
    assert select_health(health, slot) == health
    assert select_health(health, datetime(2026, 10, 3, 13, 2, tzinfo=timezone.utc)) == health


def _batch():
    from pulso_engine.pipeline import chunks
    sources = [{"id": f"s{i}", "name": "n", "domain": "d", "adapter": "rss", "source_class": "NEWS_HIGH", "url": "https://x", "state": None}
               for i in range(5)]
    events = [{"event_id": f"ev-{i}", "title": "t"} for i in range(4)]
    signals = [{"event_id": f"ev-{i}", "source_id": f"s{i % 2}", "hash": f"h{i}"} for i in range(4)]
    return {"batch_id": "b", "sources": sources, "catalog_complete": True, "events": events, "signals": signals,
            "pulses": [], "source_health": [], "series": [], "forecasts": []}, chunks


def test_sources_go_only_in_the_first_part_of_a_split_batch():
    batch, chunks = _batch()
    parts = chunks(batch, max_events=2)
    assert len(parts) == 2
    assert len(parts[0]["sources"]) == 5 and parts[0]["catalog_complete"] is True
    assert parts[1]["sources"] == [] and parts[1]["catalog_complete"] is False


def test_full_catalog_only_in_the_review_slot():
    from pulso_engine.pipeline import select_sources
    batch, _ = _batch()
    select_sources(batch, datetime(2026, 10, 3, 12, 31, tzinfo=timezone.utc))  # slot de revisão
    assert len(batch["sources"]) == 5 and batch["catalog_complete"] is True
    batch, _ = _batch()
    select_sources(batch, datetime(2026, 10, 3, 12, 17, tzinfo=timezone.utc))  # ciclo comum
    assert {s["id"] for s in batch["sources"]} == {"s0", "s1"} and batch["catalog_complete"] is False


def test_stale_feed_items_are_not_collected_again_as_new_data():
    from pulso_engine.pipeline import run_once

    def feed(url):
        return ("<rss><channel>"
                "<item><title>Enchente deixa mortos e desabrigados em Porto Alegre</title><link>https://x/novo</link>"
                "<pubDate>Fri, 02 Oct 2026 17:30:00 GMT</pubDate></item>"
                "<item><title>Deslizamento deixa mortos em Petrópolis</title><link>https://x/velho</link>"
                "<pubDate>Mon, 28 Sep 2026 10:00:00 GMT</pubDate></item></channel></rss>").encode()

    src = {"id": "s", "name": "S", "domain": "x.com", "state": None, "adapter": "rss", "source_class": "NEWS_HIGH", "url": "https://x"}
    batch = run_once([src], fetcher=feed, now=datetime(2026, 10, 2, 18, 0, tzinfo=timezone.utc))
    urls = {g["url"] for g in batch["signals"]}
    assert urls == {"https://x/novo"}  # a de 4 dias atrás nem entra
    assert all("Petrópolis" not in e["title"] for e in batch["events"])
