import json
from datetime import datetime, timezone

from pulso_engine.collectors.registry import build_adapter

NOW = datetime(2026, 10, 2, 15, 0, tzinfo=timezone.utc)


def run(adapter, body, **extra):
    src = {"id": f"t-{adapter}", "adapter": adapter, "source_class": extra.pop("source_class", "OFFICIAL"), "url": "https://x", **extra}
    return build_adapter(src, None, lambda url: json.dumps(body).encode(), lambda: NOW).run()


def test_usgs_only_places_points_inside_brazil():
    def quake(title, lon, lat):
        return {"properties": {"title": title, "url": "https://usgs/" + title, "time": 1790990000000},
                "geometry": {"coordinates": [lon, lat, 10]}}
    sigs = run("usgs", {"features": [quake("M 6.1 - Acre", -70.5, -9.0), quake("M 6.4 - Japan", 140.0, 36.0)]})
    by = {s.title: s for s in sigs}
    assert by["Terremoto: M 6.1 - Acre"].latitude == -9.0
    assert by["Terremoto: M 6.4 - Japan"].latitude is None and by["Terremoto: M 6.4 - Japan"].category == "INTERNATIONAL"


def test_gdelt_maps_articles_and_flags_rate_limit():
    body = {"articles": [{"url": "https://g1.globo.com/x?utm_source=a", "title": "Enchente atinge Porto Alegre", "seendate": "20261002T143000Z"}]}
    (sig,) = run("gdelt", body, source_class="NEWS_REGIONAL")
    assert sig.url == "https://g1.globo.com/x" and sig.timestamp == datetime(2026, 10, 2, 14, 30, tzinfo=timezone.utc)
    src = {"id": "g", "adapter": "gdelt", "source_class": "NEWS_REGIONAL", "url": "https://x"}
    try:
        build_adapter(src, None, lambda u: b"Please limit requests to one every 5 seconds", lambda: NOW).run()
    except RuntimeError as exc:
        assert "RATE_LIMITED" in str(exc)
    else:
        raise AssertionError("deveria sinalizar limite de taxa")


def test_mastodon_filters_noise_foreign_and_keeps_no_author():
    post = lambda i, html, lang="pt": {"id": i, "url": f"https://m.social/@a/{i}", "content": html, "language": lang, "created_at": "2026-10-02T14:00:00.000Z"}
    body = [post("1", "<p>Defesa Civil confirma 2 mortos em deslizamento em Petrópolis</p>"),
            post("2", "<p>Inundações causam 70 mortes na Índia e no Nepal</p>"),
            post("3", "<p>Fulana casou, veja os famosos no casamento</p>"),
            post("4", "<p>Landslide kills two in Rio</p>", lang="en")]
    sigs = run("mastodon", body, source_class="SOCIAL", tags=["enchente"], instances=["m.social"])
    assert [s.url.rsplit("/", 1)[1] for s in sigs] == ["1"]
    assert sigs[0].author is None and sigs[0].source_class == "SOCIAL"
