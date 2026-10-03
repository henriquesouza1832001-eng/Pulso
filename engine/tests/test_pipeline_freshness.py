from datetime import datetime, timedelta, timezone

from pulso_engine.pipeline import run_once

NOW = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)


def rss(items):
    body = "".join(f"<item><title>{t}</title><link>https://x/{i}</link><pubDate>{d}</pubDate></item>" for i, (t, d) in enumerate(items))
    return f"<rss><channel>{body}</channel></rss>".encode()


def date(minutes_ago):
    return (NOW - timedelta(minutes=minutes_ago)).strftime("%a, %d %b %Y %H:%M:%S +0000")


def src(sid, **kw):
    return {"id": sid, "name": sid, "domain": f"{sid}.com", "adapter": "rss", "source_class": "NEWS_HIGH", "url": f"https://{sid}.com/rss",
            "state": None, "enabled": True, **kw}


def feed(mapping):
    def fetcher(url):
        v = mapping[url.split("//")[1].split(".")[0]]
        if isinstance(v, Exception):
            raise v
        return v
    return fetcher


def by_id(batch):
    return {a["source_id"]: a for a in batch["source_freshness"]}


def test_200_fresh_200_stale_200_empty_and_offline_are_four_different_things(monkeypatch):
    monkeypatch.delenv("PULSO_FLAG_SOURCE_FRESHNESS", raising=False)
    fetcher = feed({"fresh": rss([("Acidente grave em Betim deixa feridos", date(10))]),
                    "stale": rss([("Notícia antiga de ontem sobre obra", date(3000))]),
                    "empty": rss([]), "down": OSError("connection reset")})
    batch = run_once([src("fresh"), src("stale"), src("empty"), src("down")], fetcher=fetcher, now=NOW)
    a = by_id(batch)
    assert a["fresh"]["freshness"]["state"] == "FRESH" and a["fresh"]["transport"] == "ONLINE"
    assert a["stale"]["transport"] == "ONLINE" and a["stale"]["freshness"]["state"] == "STALE"  # HTTP 200 != dado novo
    assert a["empty"]["freshness"]["state"] == "EMPTY"
    assert a["down"]["transport"] == "OFFLINE" and a["down"]["freshness"]["state"] == "UNKNOWN"  # nunca vira zero


def test_quiet_threshold_source_is_quiet_not_empty(monkeypatch):
    batch = run_once([src("alerta", quiet_ok=True)], fetcher=feed({"alerta": rss([])}), now=NOW)
    assert by_id(batch)["alerta"]["freshness"]["state"] == "QUIET"


def test_repeated_content_is_detected_against_stored_hashes(monkeypatch):
    items = [("Notícia antiga de ontem sobre obra", date(3000))]
    first = run_once([src("stale")], fetcher=feed({"stale": rss(items)}), now=NOW)
    stored = first["signals"]  # o que já foi gravado
    again = run_once([src("stale")], fetcher=feed({"stale": rss(items)}), now=NOW, stored=stored)
    q = by_id(again)["stale"]
    assert q["quality"]["new_records"] == 0 and q["freshness"]["state"] == "STALE"


def test_flag_off_disables_it_and_changes_nothing_else(monkeypatch):
    monkeypatch.setenv("PULSO_FLAG_SOURCE_FRESHNESS", "0")
    fetcher = feed({"fresh": rss([("Acidente grave em Betim deixa feridos", date(10))])})
    off = run_once([src("fresh")], fetcher=fetcher, now=NOW)
    monkeypatch.setenv("PULSO_FLAG_SOURCE_FRESHNESS", "1")
    on = run_once([src("fresh")], fetcher=fetcher, now=NOW)
    assert off["source_freshness"] == [] and len(on["source_freshness"]) == 1
    strip = lambda b: {k: v for k, v in b.items() if k not in ("batch_id", "source_freshness", "source_runtime")}  # noqa: E731
    assert strip(off) == strip(on)  # eventos, sinais, pulsos, saúde de transporte: idênticos
