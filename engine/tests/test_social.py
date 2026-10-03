from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit
import pytest
from pulso_engine.collectors.social.reddit import RedditAdapter, subreddit_path
from pulso_engine.collectors.social.x import XAdapter
from pulso_engine.collectors.social.common import SocialAPIError
from pulso_engine.config import DEFAULT_SOURCES_PATH, SourceConfigError, load_sources, validate_source
from pulso_engine.events import status_for
from pulso_engine.models import EventStats
from pulso_engine.pipeline import is_due, main, run_once
NOW = datetime(2026, 10, 3, tzinfo=timezone.utc)


def sources():
    return {s["adapter"]: s for s in load_sources(DEFAULT_SOURCES_PATH, only_enabled=False) if s["adapter"] in ("reddit", "x")}


def test_social_sources_disabled_and_fail_closed():
    reddit, x = sources()["reddit"], sources()["x"]
    assert not reddit["enabled"] and not x["enabled"]
    for src in (reddit, x):
        with pytest.raises(SourceConfigError, match="autorização e revisão"):
            validate_source({**src, "enabled": True})
    assert all(s["adapter"] not in ("reddit", "x") for s in load_sources(DEFAULT_SOURCES_PATH))


def test_reddit_oauth_and_normalization(monkeypatch):
    monkeypatch.setenv("REDDIT_CLIENT_ID", "test-id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "test-secret")
    calls = []
    def fake(url, headers, data=None):
        calls.append((url, headers, data))
        if data:
            return {"access_token": "fake-access-token"}
        return {"data": {"children": [
            {"data": {"id": "ab12", "title": "Candidatura ao Senado em São Paulo é registrada no TSE", "created_utc": NOW.timestamp()}},
            {"data": {"id": "ab13", "title": "Senado vota hoje", "created_utc": NOW.timestamp(), "removed_by_category": "deleted"}},
            {"data": {"id": "ab14", "title": "Receita de bolo de cenoura", "created_utc": NOW.timestamp()}},
        ]}}
    signals = RedditAdapter(sources()["reddit"], fetcher=fake, now=lambda: NOW).run()
    assert calls[0][0] == "https://www.reddit.com/api/v1/access_token"
    search = urlsplit(calls[1][0])
    assert search.path == "/r/brasil/search"
    assert parse_qs(search.query)["restrict_sr"] == ["on"] and "candidatura" in parse_qs(search.query)["q"][0]
    assert all(h["User-Agent"] for _, h, _ in calls)
    assert len(signals) == 1 and signals[0].author is None  # removido e fora do tema descartados
    assert signals[0].source_class == "SOCIAL" and signals[0].text is None
    assert signals[0].category == "POLITICS" and signals[0].state == "SP"
    assert signals[0].url == "https://www.reddit.com/comments/ab12/"


def test_x_recent_search_and_normalization(monkeypatch):
    monkeypatch.setenv("X_BEARER_TOKEN", "test-token")
    def fake(url, headers):
        assert urlsplit(url).path == "/2/tweets/search/recent"
        assert "-is:retweet" in parse_qs(urlsplit(url).query)["query"][0]
        assert headers["Authorization"] == "Bearer test-token"
        assert parse_qs(urlsplit(url).query)["start_time"] == ["2026-10-02T23:45:00Z"]  # só a janela nova
        return {"data": [{"id": "123", "text": "@fulano debate da eleição no Senado https://t.co/x", "created_at": "2026-10-03T00:00:00Z"},
                         {"id": "bad", "text": "ignored", "created_at": "2026-10-03T00:00:00Z"}]}
    sigs = XAdapter(sources()["x"], fetcher=fake, now=lambda: NOW).run()
    assert len(sigs) == 1 and sigs[0].url == "https://x.com/i/status/123"
    assert sigs[0].author is None and sigs[0].text is None
    assert sigs[0].title == "@usuário debate da eleição no Senado"  # sem @menção nem link

def test_credentials_required_and_failure_isolated(monkeypatch):
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    with pytest.raises(ValueError, match="X_BEARER_TOKEN"):
        XAdapter(sources()["x"]).run()
    batch = run_once([sources()["x"]], now=NOW)
    assert batch["source_health"][0]["status"] == "OFFLINE"
    assert "test-token" not in (batch["source_health"][0]["detail"] or "")
    assert batch["signals"] == []


def test_social_only_never_confirmed():
    stats = EventStats(severity=35, signal_count=3, independent_sources=3,
                       source_classes=frozenset({"SOCIAL"}), newest_age_min=2,
                       persistence_min=10, velocity_per_hour=3)
    assert status_for(stats) == "DETECTED"


@pytest.mark.parametrize("code,status", [(429, "RATE_LIMITED"), (401, "AUTH_ERROR"), (403, "AUTH_ERROR"), (500, "OFFLINE")])
def test_api_errors_map_to_health(monkeypatch, code, status):
    monkeypatch.setenv("X_BEARER_TOKEN", "test-token")
    def failing(url, headers):
        raise SocialAPIError(code)
    monkeypatch.setattr("pulso_engine.collectors.social.x.request_json", failing)
    batch = run_once([sources()["x"]], now=NOW)
    assert batch["source_health"][0]["status"] == status


def test_config_requires_topic_fields():
    reddit, x = sources()["reddit"], sources()["x"]
    for src, field in ((reddit, "subreddit"), (x, "query")):
        with pytest.raises(SourceConfigError, match=field):
            validate_source({**src, field: ""})
    with pytest.raises(SourceConfigError, match="categories"):
        validate_source({**x, "categories": ["NAO_EXISTE"]})


def test_invalid_subreddit_rejected():
    with pytest.raises(ValueError, match="subreddit"):
        subreddit_path("brasil/../x")
    assert subreddit_path("brasil+worldnews") == "brasil+worldnews"


def test_interval_throttle():
    src = {"interval_s": 900}
    due = [is_due(src, NOW + timedelta(minutes=m)) for m in range(0, 30, 5)]
    assert due == [True, False, False, True, False, False]
    assert all(is_due({"interval_s": 300}, NOW + timedelta(minutes=m)) for m in range(0, 30, 5))


def test_pilot_flag_refuses_push_for_disabled():
    with pytest.raises(SystemExit):
        main(["--source", "x-politics", "--push"])


def test_pilot_log_shows_only_counts(monkeypatch, capsys):
    monkeypatch.setenv("X_BEARER_TOKEN", "test-token")
    def fake(url, headers):
        return {"data": [{"id": "9", "text": "Protesto em Brasília contra o Senado", "created_at": "2026-10-03T00:00:00Z"}]}
    monkeypatch.setattr("pulso_engine.collectors.social.x.request_json", fake)
    assert main(["--source", "x-politics"]) == 0
    out = capsys.readouterr().out
    assert "categorias:" in out and "Brasília" not in out  # logs do Actions são públicos
