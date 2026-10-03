from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from pulso_engine.collectors.social.bluesky import BlueskyAdapter, parse_uri
from pulso_engine.collectors.social.common import SocialAPIError
from pulso_engine.config import DEFAULT_SOURCES_PATH, SourceConfigError, load_sources, validate_source

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
DID = "did:plc:abcdefghijklmnopqrstuvwx"


def src(sid="bluesky-clima"):
    return {s["id"]: s for s in load_sources(DEFAULT_SOURCES_PATH, only_enabled=False)}[sid]


def post(rkey, text, langs=("pt",), labels=None, created="2026-10-03T11:50:00.000Z", did=DID):
    p = {"uri": f"at://{did}/app.bsky.feed.post/{rkey}", "author": {"handle": "fulano.bsky.social", "did": did},
         "record": {"text": text, "createdAt": created, "langs": list(langs)}}
    if labels:
        p["labels"] = labels
    return p


def test_bluesky_sources_are_disabled_and_fail_closed():
    for sid in ("bluesky-politics", "bluesky-clima"):
        s = src(sid)
        assert not s["enabled"] and s["adapter"] == "bluesky" and s["source_class"] == "SOCIAL"
        with pytest.raises(SourceConfigError, match="autorização e revisão"):
            validate_source({**s, "enabled": True})
    assert all(s["adapter"] != "bluesky" for s in load_sources(DEFAULT_SOURCES_PATH))


def test_parse_uri_accepts_only_valid_posts():
    assert parse_uri(f"at://{DID}/app.bsky.feed.post/3kabc") == (DID, "3kabc")
    for bad in (None, 5, "https://x/y", f"at://{DID}/app.bsky.feed.like/3kabc", "at://naodid/app.bsky.feed.post/3k", f"at://{DID}/app.bsky.feed.post/"):
        assert parse_uri(bad) is None


def test_search_flow_normalizes_filters_and_protects_privacy(monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "pulso.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "senha-de-app")
    calls = []

    def fake(url, headers, data=None):
        calls.append((url, headers, data))
        if "createSession" in url:
            return {"accessJwt": "jwt-falso"}
        q = parse_qs(urlsplit(url).query)["q"][0]
        if q == "enchente":
            return {"posts": [
                post("3k1", "Enchente deixa ruas alagadas e famílias desabrigadas em Recife, diz Defesa Civil"),
                post("3k2", "Enchente em outro país", langs=("en",)),
                post("3k3", "Enchente com conteúdo marcado", labels=[{"val": "porn"}]),
                post("3k4", "Receita de bolo de cenoura"),
                {"uri": "lixo", "record": {"text": "x", "createdAt": "2026-10-03T11:00:00Z"}},
            ]}
        return {"posts": [post("3k1", "Enchente deixa ruas alagadas e famílias desabrigadas em Recife, diz Defesa Civil")]}  # repetido em outra consulta

    s = {**src(), "queries": ["enchente", "alagamento"]}
    signals = BlueskyAdapter(s, fetcher=fake, now=lambda: NOW).run()
    assert "createSession" in calls[0][0] and b"senha-de-app" in calls[0][2]
    search = [c for c in calls if "searchPosts" in c[0]]
    assert len(search) == 2  # uma requisição por termo
    q = parse_qs(urlsplit(search[0][0]).query)
    assert q["lang"] == ["pt"] and q["sort"] == ["latest"] and q["since"][0].startswith("2026-10-03T")
    assert search[0][1]["Authorization"] == "Bearer jwt-falso"
    assert len(signals) == 1  # inglês, rotulado, fora do tema, URI inválida e repetido: descartados
    sig = signals[0]
    assert sig.source_class == "SOCIAL" and sig.author is None and sig.text is None
    assert sig.url == f"https://bsky.app/profile/{DID}/post/3k1"  # DID opaco, nunca o @ legível
    assert "fulano" not in sig.url and "fulano" not in sig.title
    assert sig.state == "PE" and sig.category in ("WEATHER", "EMERGENCY", "INFRASTRUCTURE")


def test_errors_and_missing_credentials(monkeypatch):
    monkeypatch.delenv("BLUESKY_HANDLE", raising=False)
    monkeypatch.delenv("BLUESKY_APP_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="BLUESKY_HANDLE"):
        BlueskyAdapter(src(), fetcher=lambda *a, **k: {}, now=lambda: NOW).run()
    monkeypatch.setenv("BLUESKY_HANDLE", "a.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "x")

    def denied(url, headers, data=None):
        raise SocialAPIError(401)

    with pytest.raises(SocialAPIError) as e:
        BlueskyAdapter(src(), fetcher=denied, now=lambda: NOW).run()
    assert e.value.health_status == "AUTH_ERROR"
    with pytest.raises(ValueError, match="token"):
        BlueskyAdapter(src(), fetcher=lambda *a, **k: {}, now=lambda: NOW).run()
    monkeypatch.setenv("BLUESKY_PDS", "http://inseguro")
    with pytest.raises(ValueError, match="https"):
        BlueskyAdapter(src(), fetcher=lambda *a, **k: {}, now=lambda: NOW).run()
