"""Feature flags: padrão seguro, sobrescrita por ambiente e interruptores reais no pipeline."""
from datetime import datetime, timezone

import pytest

from pulso_engine.flags import FLAGS, enabled, snapshot
from pulso_engine.pipeline import run_once

T = datetime(2026, 10, 3, 15, 2, tzinfo=timezone.utc)


def test_defaults_are_safe_only_shadow_features_are_on():
    on = {n for n, (default, state, _) in FLAGS.items() if default}
    assert on == {"HISTORY_OBSERVATIONS", "SENTINEL", "FORECAST_REGISTRY", "SOURCE_FRESHNESS"}
    assert all(state == "SHADOW" for n, (d, state, _) in FLAGS.items() if d)
    assert all(state == "OFF" for n, (d, state, _) in FLAGS.items() if not d)


def test_env_overrides_and_unknown_flag_is_an_error():
    assert enabled("ANOMALY_V2", {"PULSO_FLAG_ANOMALY_V2": "on"}) is True
    assert enabled("SENTINEL", {"PULSO_FLAG_SENTINEL": "0"}) is False
    assert enabled("SENTINEL", {"PULSO_FLAG_SENTINEL": "lixo"}) is True  # valor inválido: vale o padrão
    with pytest.raises(KeyError):
        enabled("NAO_EXISTE")
    assert set(snapshot({})) == set(FLAGS)


def _src():
    return {"id": "s1", "name": "S1", "domain": "s1.com", "state": None, "adapter": "rss", "source_class": "NEWS_HIGH", "url": "https://s1.com/rss"}


def _feed():
    d = "Sat, 03 Oct 2026 13:27:00 GMT"
    return f"<rss><channel><item><title>Temporal causa alagamento e deixa feridos em Recife</title><link>https://s1.com/a</link><pubDate>{d}</pubDate></item></channel></rss>".encode()


def test_flags_really_switch_features_off(monkeypatch):
    kw = dict(fetcher=lambda u: _feed(), now=T, history=[], pulse_points=[], open_forecasts=[], stored=[], known_events=[],
              obs_rows=[], active_investigations=[])
    monkeypatch.setenv("PULSO_FLAG_HISTORY_OBSERVATIONS", "0")
    assert run_once([_src()], **kw)["observations"] == []
    monkeypatch.setenv("PULSO_FLAG_HISTORY_OBSERVATIONS", "1")
    assert run_once([_src()], **kw)["observations"], "ligada: a hora fechada com sinal aparece"
    # Sentinela desligado: nunca devolve investigações, mesmo com histórico disponível
    monkeypatch.setenv("PULSO_FLAG_SENTINEL", "0")
    assert run_once([_src()], **kw)["investigations"] == []
