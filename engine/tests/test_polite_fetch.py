import io
import threading
import time
import urllib.error
from datetime import datetime, timezone

from pulso_engine.collectors.news import rss
from pulso_engine.pipeline import run_once


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_never_more_than_two_simultaneous_requests_to_the_same_host(monkeypatch):
    state = {"now": 0, "peak": 0}
    lock = threading.Lock()

    def slow_urlopen(req, timeout=0):
        with lock:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
        time.sleep(0.08)
        with lock:
            state["now"] -= 1
        return _Resp(b"<rss/>")

    monkeypatch.setattr(rss.urllib.request, "urlopen", slow_urlopen)
    threads = [threading.Thread(target=rss.http_fetch, args=(f"https://mesmo.host/feed{i}",)) for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert state["peak"] <= rss.PER_HOST_MAX


def test_different_hosts_are_not_throttled_against_each_other(monkeypatch):
    seen = {"peak": 0, "now": 0}
    lock = threading.Lock()

    def urlopen(req, timeout=0):
        with lock:
            seen["now"] += 1
            seen["peak"] = max(seen["peak"], seen["now"])
        time.sleep(0.08)
        with lock:
            seen["now"] -= 1
        return _Resp(b"<rss/>")

    monkeypatch.setattr(rss.urllib.request, "urlopen", urlopen)
    threads = [threading.Thread(target=rss.http_fetch, args=(f"https://host{i}.example/feed",)) for i in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert seen["peak"] > rss.PER_HOST_MAX  # hosts diferentes seguem em paralelo


def test_http_429_is_reported_as_rate_limited_and_other_errors_as_offline():
    def fetch(url):
        if "limitado" in url:
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)
        raise urllib.error.HTTPError(url, 500, "Erro", {}, None)

    base = {"name": "n", "domain": "d", "state": None, "adapter": "rss", "source_class": "NEWS_HIGH"}
    srcs = [{**base, "id": "a", "url": "https://limitado/feed"}, {**base, "id": "b", "url": "https://quebrado/feed"}]
    health = {h["source_id"]: h["status"] for h in run_once(srcs, fetcher=fetch, now=datetime(2026, 10, 3, 3, 0, tzinfo=timezone.utc))["source_health"]}
    assert health == {"a": "RATE_LIMITED", "b": "OFFLINE"}
