"""Passo 1 do Sentinela no pipeline: contagem de duplicatas, janela de reenvio e o lote final."""
from datetime import datetime, timedelta, timezone

from pulso_engine.pipeline import OBS_MAX, chunks, run_once, select_observations

T = datetime(2026, 10, 3, 15, 2, tzinfo=timezone.utc)  # minuto 2: dentro da janela de envio


def rss(*items):
    body = "".join(f"<item><title>{t}</title><link>{u}</link><pubDate>{d}</pubDate></item>" for t, u, d in items)
    return f"<rss><channel>{body}</channel></rss>".encode()


def src(i):
    return {"id": f"s{i}", "name": f"S{i}", "domain": f"s{i}.com", "state": None, "adapter": "rss", "source_class": "NEWS_HIGH", "url": f"https://s{i}.com/rss"}


def pub(minutes_ago):
    return (T - timedelta(minutes=minutes_ago)).strftime("%a, %d %b %Y %H:%M:%S GMT")


def test_duplicate_copies_are_counted_and_closed_hours_are_reported():
    # a mesma matéria (mesma URL) chega por duas fontes: a cópia descartada vira duplicates=1 na hora FECHADA (13h UTC)
    same = ("Temporal causa alagamento e deixa feridos em Recife", "https://x.com/a", pub(95))  # 13:27
    feeds = {"https://s1.com/rss": rss(same), "https://s2.com/rss": rss(same)}
    batch = run_once([src(1), src(2)], fetcher=lambda u: feeds[u], now=T, history=[], pulse_points=[], open_forecasts=[], stored=[], known_events=[])
    obs = batch["observations"]
    assert obs, "a hora 13h já fechou e tem sinal"
    br = [o for o in obs if o["scope"] == "BR" and o["category"] == "WEATHER"]
    assert br and br[0]["signals"] == 1 and br[0]["duplicates"] == 1 and br[0]["hour"] == "2026-10-03T13:00:00Z"
    assert all(o["hour"] != "2026-10-03T15:00:00Z" for o in obs)  # a hora corrente nunca sai


def test_observations_only_in_the_two_slots_per_hour_and_last_two_closed_hours():
    rows = [{"scope": "BR", "category": "WEATHER", "source_class": "NEWS_HIGH", "hour": h, "signals": 1, "sources": 1, "duplicates": 0}
            for h in ("2026-10-03T10:00:00Z", "2026-10-03T13:00:00Z", "2026-10-03T14:00:00Z")]
    assert [o["hour"] for o in select_observations(rows, T)] == ["2026-10-03T13:00:00Z", "2026-10-03T14:00:00Z"]  # 10h já saiu da janela
    assert select_observations(rows, T.replace(minute=17)) == []  # fora do slot: nada é reenviado
    assert select_observations(rows, T.replace(minute=31)) != []  # segundo slot da hora


def test_national_first_and_capped():
    rows = [{"scope": f"UF:{c}", "category": "WEATHER", "source_class": "NEWS_HIGH", "hour": "2026-10-03T14:00:00Z", "signals": 1, "sources": 1, "duplicates": 0}
            for c in ["AC", "AL", "AM"]] + [{"scope": "BR", "category": "WEATHER", "source_class": "NEWS_HIGH", "hour": "2026-10-03T14:00:00Z", "signals": 3, "sources": 2, "duplicates": 0}]
    assert select_observations(rows, T)[0]["scope"] == "BR"  # o governador em economia só aceita BR
    many = [{**rows[0], "scope": "BR", "category": f"C{i}"} for i in range(OBS_MAX + 50)]
    assert len(select_observations(many, T)) == OBS_MAX


def test_chunks_send_observations_only_in_the_last_part():
    sig = lambda i: {"event_id": f"ev-{i}", "source_id": "s1", "hash": f"h{i}"}  # noqa: E731
    batch = {"batch_id": "b", "sources": [], "catalog_complete": False, "events": [{"event_id": f"ev-{i}", "title": "t"} for i in range(400)],
             "signals": [sig(i) for i in range(400)], "pulses": [], "source_health": [], "series": [], "forecasts": [],
             "observations": [{"scope": "BR", "hour": "x"}]}
    parts = chunks(batch)
    assert len(parts) > 1
    assert [len(p["observations"]) for p in parts] == [0] * (len(parts) - 1) + [1]
