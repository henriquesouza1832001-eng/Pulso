import json
import warnings

import pytest

from pulso_engine.config import DEFAULT_SOURCES_PATH, SourceConfigError, load_sources, validate_source

OK = {
    "id": "x", "name": "X", "adapter": "rss", "source_class": "NEWS_HIGH", "url": "https://x.com/rss",
    "access": "public_feed", "terms_url": "https://x.com/termos", "interval_s": 300, "retention_days": 90,
    "display": "headline_link", "reviewed_by": "alguem", "reviewed_at": "2026-10-02",
}


def test_shipped_sources_pass_the_protocol():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert len(load_sources(DEFAULT_SOURCES_PATH)) >= 5


def test_valid_source_passes():
    validate_source(OK)


@pytest.mark.parametrize("patch,msg", [
    ({"terms_url": None}, "faltam campos"),
    ({"interval_s": 30}, "abaixo do mínimo"),
    ({"source_class": "FAMOSO"}, "source_class"),
    ({"access": "public_page"}, "robots_checked"),
    ({"access": "authorized_scrape"}, "authorization_ref"),
    ({"url": "ftp://x"}, "http"),
    ({"retention_days": 0}, "retention_days"),
])
def test_protocol_violations_are_rejected(patch, msg):
    with pytest.raises(SourceConfigError, match=msg):
        validate_source({**OK, **patch})


def test_pending_review_warns_but_unknown_fields_missing_fail(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps([{**OK, "reviewed_by": "PENDENTE"}]), encoding="utf-8")
    with pytest.warns(UserWarning, match="conformidade pendente"):
        load_sources(p)
    p.write_text(json.dumps([OK, OK]), encoding="utf-8")
    with pytest.raises(SourceConfigError, match="duplicados"):
        load_sources(p)
