import threading
import time
from datetime import datetime, timezone

from pulso_engine.pipeline import run_once

NOW = datetime(2026, 10, 2, 18, 0, tzinfo=timezone.utc)


def feed(title):
    return (f"<rss><channel><item><title>{title}</title><link>https://x/{abs(hash(title))}</link>"
            "<pubDate>Fri, 02 Oct 2026 17:50:00 GMT</pubDate></item></channel></rss>").encode()


def sources(n):
    return [{"id": f"s{i}", "name": f"Fonte {i}", "domain": "x.com", "state": None, "adapter": "rss", "source_class": "NEWS_HIGH", "url": f"https://f/{i}"} for i in range(n)]


def test_sources_run_in_parallel_and_keep_order():
    seen = set()

    def slow(url):
        seen.add(threading.get_ident())
        time.sleep(0.2)
        return feed(f"Enchente em cidade {url[-1]}")

    start = time.time()
    batch = run_once(sources(8), fetcher=slow, now=NOW)
    assert time.time() - start < 1.0, "8 fontes de 0,2 s em série levariam 1,6 s"
    assert len(seen) > 1
    assert [h["source_id"] for h in batch["source_health"]] == [f"s{i}" for i in range(8)]


def test_one_failing_source_does_not_break_the_cycle():
    def fetch(url):
        if url.endswith("/1"):
            raise OSError("fora do ar")
        return feed("Alagamento forte em Porto Alegre")

    batch = run_once(sources(3), fetcher=fetch, now=NOW)
    status = {h["source_id"]: h["status"] for h in batch["source_health"]}
    assert status["s1"] == "OFFLINE" and status["s0"] == "ONLINE" and status["s2"] == "ONLINE"
