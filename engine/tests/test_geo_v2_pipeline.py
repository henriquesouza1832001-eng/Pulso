"""GEO_V2 no pipeline: desligado não muda nada (só conta em sombra); ligado troca estado por município, sem oscilar."""
from datetime import datetime, timedelta, timezone

from pulso_engine.pipeline import refine_geo, run_once
from pulso_engine.models import Signal

T = datetime(2026, 10, 3, 15, 2, tzinfo=timezone.utc)


def _feed(title):
    d = (T - timedelta(minutes=20)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    return f"<rss><channel><item><title>{title}</title><link>https://s1.com/a</link><pubDate>{d}</pubDate></item></channel></rss>".encode()


def _src(state=None):
    return {"id": "s1", "name": "S1", "domain": "s1.com", "state": state, "adapter": "rss", "source_class": "NEWS_HIGH", "url": "https://s1.com/rss"}


def _run(title, **kw):
    return run_once([_src()], fetcher=lambda u: _feed(title), now=T, history=[], pulse_points=[], open_forecasts=[], stored=kw.pop("stored", []),
                    known_events=[], **kw)


def test_flag_off_changes_nothing_and_reports_the_shadow(monkeypatch):
    monkeypatch.delenv("PULSO_FLAG_GEO_V2", raising=False)
    b = _run("Acidente grave em Itaúna deixa feridos")
    ev = b["events"][0]
    assert ev["city"] != "Itaúna" or ev["geo_precision"] != "CITY"  # V1: sem o município
    assert b["geo_v2_shadow"] == {"signals": 1, "would_upgrade": 1}


def test_flag_on_places_the_event_in_the_city(monkeypatch):
    monkeypatch.setenv("PULSO_FLAG_GEO_V2", "1")
    b = _run("Acidente grave em Itaúna deixa feridos")
    ev = b["events"][0]
    assert (ev["city"], ev["state"], ev["geo_precision"]) == ("Itaúna", "MG", "CITY")
    assert -21 < ev["latitude"] < -19 and b["geo_v2_shadow"] is None


def test_refine_is_idempotent_and_never_touches_source_geo(monkeypatch):
    monkeypatch.setenv("PULSO_FLAG_GEO_V2", "1")
    s = Signal(signal_id="s", source_id="s1", source_class="NEWS_HIGH", timestamp=T, collected_at=T, title="Acidente em Itaúna deixa feridos",
               url="https://s1.com/a", category="TRAFFIC", reliability=70, hash="h1", canonical_url="https://s1.com/a")
    once = refine_geo(s, frozenset(), {})
    twice = refine_geo(once, frozenset(), {})
    assert once.city == "Itaúna" and twice == once  # sem oscilar entre ciclos
    assert refine_geo(s, frozenset({"s1"}), {}) is s  # geografia vinda da fonte (INPE, Defesa Civil...) nunca é trocada
