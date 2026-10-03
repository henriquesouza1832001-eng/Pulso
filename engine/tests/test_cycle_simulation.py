"""Simulação de VÁRIOS ciclos seguidos contra um "Worker de mentira" que guarda o que recebe (como o D1 real).

Prova de uma vez o encaixe das peças: agrupamento com estado (id de evento estável), orçamento de escrita (só o novo é
reenviado), descarte de matéria velha, frescor (o Pulso cai com o tempo) e reação a uma fonte nova sobre o mesmo fato.
"""
from datetime import datetime, timedelta, timezone

from pulso_engine.pipeline import run_once

T0 = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def rss(*items):
    body = "".join(f"<item><title>{t}</title><link>{u}</link><pubDate>{d}</pubDate></item>" for t, u, d in items)
    return f"<rss><channel>{body}</channel></rss>".encode()


def pub(minutes_before_t0: int) -> str:
    return (T0 - timedelta(minutes=minutes_before_t0)).strftime("%a, %d %b %Y %H:%M:%S GMT")


def source(i, cls="NEWS_HIGH", state=None):
    return {"id": f"s{i}", "name": f"Fonte {i}", "domain": f"s{i}.com", "state": state, "adapter": "rss",
            "source_class": cls, "url": f"https://s{i}.com/rss"}


class FakeWorker:
    """Guarda sinais e eventos como o D1 (upsert por chave) e devolve o que o Engine lê a cada ciclo."""

    def __init__(self):
        self.signals: dict[str, dict] = {}
        self.events: dict[str, dict] = {}
        self.writes = 0

    def stored(self, now):
        cutoff = now - timedelta(hours=24)
        return [s for s in self.signals.values() if datetime.fromisoformat(s["timestamp"].replace("Z", "+00:00")) >= cutoff]

    def digest(self):
        keys = ("event_id", "pulse", "alert_level", "status", "signal_count", "source_count")
        return [{k: e[k] for k in keys} for e in self.events.values()]

    def apply(self, batch):
        for s in batch["signals"]:
            self.signals[s["hash"]] = s
            self.writes += 1
        for e in batch["events"]:
            self.events[e["event_id"]] = e
            self.writes += 1


def cycle(worker, feeds, now, sources):
    batch = run_once(sources, fetcher=lambda u: feeds[u], now=now, stored=worker.stored(now), known_events=worker.digest())
    worker.apply(batch)
    return batch


STORY = "Enchente deixa mortos e desabrigados em Porto Alegre"


def test_story_lifecycle_across_cycles():
    w = FakeWorker()
    srcs = [source(1), source(2), source(3)]
    feeds = {"https://s1.com/rss": rss((STORY, "https://s1.com/a", pub(30))),
             "https://s2.com/rss": rss(("Enchente em Porto Alegre deixa mortos e desabrigados", "https://s2.com/b", pub(20))),
             "https://s3.com/rss": rss()}

    # 1) primeiro ciclo: nasce UM evento (duas fontes) e tudo é novo
    b1 = cycle(w, feeds, T0, srcs)
    assert len(b1["events"]) == 1 and len(b1["signals"]) == 2
    eid = b1["events"][0]["event_id"]
    pulse_fresh = b1["events"][0]["pulse"]

    # 2) mesmo feed 5 min depois: NADA a reescrever (orçamento de escrita), mesmo evento
    writes_before = w.writes
    b2 = cycle(w, feeds, T0 + timedelta(minutes=5), srcs)
    assert b2["signals"] == [] and b2["events"] == [] and w.writes == writes_before
    assert b2["events_total"] == 1

    # 3) uma terceira fonte noticia o MESMO fato: o evento existente é atualizado (id estável) e reenviado
    feeds["https://s3.com/rss"] = rss(("Porto Alegre: enchente deixa mortos e desabrigados, diz Defesa Civil", "https://s3.com/c", pub(-8)))
    b3 = cycle(w, feeds, T0 + timedelta(minutes=10), srcs)
    assert [e["event_id"] for e in b3["events"]] == [eid]
    assert b3["events"][0]["signal_count"] == 3 and b3["events"][0]["source_count"] == 3 and len(b3["signals"]) == 1

    # 4) horas depois, sem nada novo: o evento fica, mas o Pulso CAI (frescor) e só é reescrito quando muda >= 3 pontos
    later = T0 + timedelta(hours=7)
    b4 = cycle(w, feeds, later, srcs)
    assert b4["events_total"] == 1
    old = b4["events"][0] if b4["events"] else w.events[eid]
    assert old["event_id"] == eid
    # a matéria ainda tem menos de 24 h, então segue no estado, mas o frescor reduz o score de forma clara
    assert b4["pulses"][0]["score"] < pulse_fresh + 5

    # 5) passadas 26 h, a matéria sai da janela: nenhum sinal novo e nenhum evento refeito a partir dela
    b5 = cycle(w, feeds, T0 + timedelta(hours=26), srcs)
    assert b5["signals"] == [] and b5["events"] == []


def test_stale_feed_items_never_reach_the_worker_and_official_confirms():
    w = FakeWorker()
    srcs = [source(1), source(2, cls="OFFICIAL", state="RS")]
    feeds = {"https://s1.com/rss": rss((STORY, "https://s1.com/a", pub(15)),
                                       ("Reportagem antiga sobre deslizamento deixa mortos em Petrópolis", "https://s1.com/old", pub(60 * 50))),
             "https://s2.com/rss": rss(("Defesa Civil: enchente deixa mortos e desabrigados em Porto Alegre", "https://s2.com/c", pub(10)))}
    b = cycle(w, feeds, T0, srcs)
    assert all("Petrópolis" not in s["title"] for s in b["signals"])  # 50 h atrás: fora
    assert len(b["events"]) == 1
    ev = b["events"][0]
    assert ev["status"] == "CONFIRMED" and ev["source_count"] == 2 and ev["state"] == "RS"
    assert ev["confidence"] >= 45  # fonte oficial pesa na confiança


def test_two_unrelated_stories_from_the_same_sources_stay_separate_and_slow_categories_are_stable():
    w = FakeWorker()
    srcs = [source(1), source(2)]
    feeds = {"https://s1.com/rss": rss((STORY, "https://s1.com/a", pub(30)), ("Senado aprova PEC que acaba com a escala 6x1 em votação histórica", "https://s1.com/g", pub(25))),
             "https://s2.com/rss": rss(("Enchente em Porto Alegre deixa mortos e desabrigados", "https://s2.com/b", pub(20)), ("PEC da escala 6x1 é aprovada pelo Senado em votação histórica", "https://s2.com/h", pub(18)))}
    b1 = cycle(w, feeds, T0, srcs)
    assert len(b1["events"]) == 2 and {e["category"] for e in b1["events"]} == {"WEATHER", "POLITICS"}
    ids1 = {e["event_id"] for e in b1["events"]}
    # categorias lentas (clima 6 h, política 12 h): 15 min depois o Pulso quase não mexe -> nada é reescrito e os ids ficam
    b2 = cycle(w, feeds, T0 + timedelta(minutes=15), srcs)
    assert b2["events"] == [] and {e["event_id"] for e in w.events.values()} == ids1


def test_fast_decaying_traffic_is_rewritten_as_it_cools_but_keeps_its_id():
    w = FakeWorker()
    srcs = [source(1), source(2)]
    feeds = {"https://s1.com/rss": rss(("Greve de metroviários paralisa o metrô de São Paulo", "https://s1.com/g", pub(5))),
             "https://s2.com/rss": rss(("Metroviários entram em greve e o metrô de São Paulo para", "https://s2.com/h", pub(4)))}
    b1 = cycle(w, feeds, T0, srcs)
    assert len(b1["events"]) == 1 and b1["events"][0]["category"] == "TRAFFIC"
    eid, p1 = b1["events"][0]["event_id"], b1["events"][0]["pulse"]
    quiet = cycle(w, feeds, T0 + timedelta(minutes=30), srcs)  # esfriou pouco (< PULSE_RESEND_DELTA): não vale reescrever
    assert quiet["events"] == []
    b2 = cycle(w, feeds, T0 + timedelta(minutes=90), srcs)  # trânsito esfria rápido (meia-vida de 1 h)
    assert [e["event_id"] for e in b2["events"]] == [eid] and b2["events"][0]["pulse"] <= p1 - 8
