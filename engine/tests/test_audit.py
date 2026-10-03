from datetime import datetime, timezone

from pulso_engine.audit import audit, render

NOW = datetime(2026, 10, 3, 3, 0, tzinfo=timezone.utc)


def rss(*items):
    body = "".join(f"<item><title>{t}</title><link>https://x/{abs(hash(t))}</link><pubDate>{d}</pubDate></item>" for t, d in items)
    return f"<rss><channel>{body}</channel></rss>".encode()


def src(i):
    return {"id": i, "name": i, "domain": "x.com", "state": None, "adapter": "rss", "source_class": "NEWS_HIGH", "url": f"https://{i}/feed"}


def test_audit_classifies_ok_stopped_empty_and_broken_feeds():
    feeds = {
        "https://ok/feed": rss(("Enchente deixa mortos em Porto Alegre", "Sat, 03 Oct 2026 02:30:00 GMT")),
        "https://parado/feed": rss(("Notícia antiga de chuva forte", "Mon, 28 Sep 2026 10:00:00 GMT")),
        "https://vazio/feed": rss(),
    }

    def fetch(url):
        if "quebrado" in url:
            raise OSError("fora do ar")
        return feeds[url]

    rows = {r["id"]: r for r in audit([src("ok"), src("parado"), src("vazio"), src("quebrado")], fetch, NOW)}
    assert rows["ok"]["status"] == "OK" and rows["ok"]["fresh"] == 1 and rows["ok"]["with_state"] == 1
    assert rows["ok"]["newest_h"] == 0.5 and "WEATHER" in rows["ok"]["categories"]
    assert rows["parado"]["status"] == "PARADO" and rows["parado"]["fresh"] == 0 and rows["parado"]["items"] == 1
    assert rows["vazio"]["status"] == "VAZIO"
    assert rows["quebrado"]["status"] == "ERRO" and "fora do ar" in rows["quebrado"]["error"]


def test_render_has_a_summary_line():
    rows = audit([src("ok")], lambda u: rss(("Enchente deixa mortos", "Sat, 03 Oct 2026 02:30:00 GMT")), NOW)
    text = render(rows)
    assert "resumo: OK 1 (de 1)" in text and "ok" in text
