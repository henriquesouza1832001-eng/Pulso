"""Achados da revisão independente de código (2026-10-03): cada um vira um teste que falha sem a correção."""
import io
import json
import urllib.error
from datetime import datetime, timezone

import pytest

from pulso_engine import client, pipeline
from pulso_engine.models import Signal
from pulso_engine.pipeline import chunks, geo_source_ids, regeolocate, select_sources

NOW = datetime(2026, 10, 3, 12, 17, tzinfo=timezone.utc)  # minuto 17: ciclo comum (fora do horário de revisão)


# ---- 1) fonte metrics_only ATIVA não pode impedir o envio ------------------------------------------------------------
def _config(tmp_path, display):
    src = {"id": "s1", "name": "S1", "domain": "s1.com", "adapter": "rss", "source_class": "NEWS_HIGH", "url": "https://s1.com/rss",
           "state": None, "enabled": True, "access": "public_feed", "terms_url": "https://s1.com/termos", "interval_s": 300,
           "retention_days": 90, "display": display, "reviewed_by": "x", "reviewed_at": "2026-10-03"}
    p = tmp_path / "sources.json"
    p.write_text(json.dumps([src]), encoding="utf-8")
    return p


def _canned_batch():
    ev = {"event_id": "ev-1", "title": "TITULO SECRETO DO EVENTO", "category": "SECURITY", "pulse": 40, "confidence": 50,
          "source_count": 2, "alert_level": 2, "state": "SP"}
    sig = {"signal_id": "sig-1", "source_id": "s1", "hash": "h1", "event_id": "ev-1", "category": "SECURITY", "state": "SP"}
    return {"batch_id": "b", "sources": [{"id": "s1"}], "catalog_complete": True, "events": [ev], "events_total": 1, "signals": [sig],
            "pulses": [{"scope": "BR", "score": 40, "alert_level": 2}], "source_health": [{"source_id": "s1", "status": "ONLINE", "detail": None}],
            "series": [], "forecasts": []}


def _patch_main(monkeypatch, pushed):
    monkeypatch.setattr(pipeline, "is_due", lambda s, now: True)
    monkeypatch.setattr(pipeline, "run_once", lambda *a, **k: _canned_batch())
    for name in ("fetch_history", "fetch_pulse_history", "fetch_open_forecasts", "fetch_signals", "fetch_event_digest"):
        monkeypatch.setattr(client, name, lambda *a, **k: [])
    monkeypatch.setattr(client, "push_batch", lambda part, *a, **k: pushed.append(part) or {"ok": True})


def test_active_metrics_only_source_still_pushes_but_never_prints_content(tmp_path, monkeypatch, capsys):
    pushed = []
    _patch_main(monkeypatch, pushed)
    assert pipeline.main(["--config", str(_config(tmp_path, "metrics_only")), "--push"]) == 0
    out = capsys.readouterr().out
    assert pushed, "antes, a fonte metrics_only encerrava a rodada e nada era enviado"
    assert "TITULO SECRETO" not in out and "categorias:" in out  # só contagens no log público


def test_normal_sources_print_the_top_events_and_push(tmp_path, monkeypatch, capsys):
    pushed = []
    _patch_main(monkeypatch, pushed)
    assert pipeline.main(["--config", str(_config(tmp_path, "headline_link")), "--push"]) == 0
    assert pushed and "TITULO SECRETO" in capsys.readouterr().out


# ---- 2) regeolocate mantém a geografia que veio da fonte --------------------------------------------------------------
def sig(source, state, text="Obras avançam na avenida principal", conf=35):
    return Signal(signal_id="x", source_id=source, source_class="NEWS_REGIONAL", timestamp=NOW, collected_at=NOW, title=text,
                  category="OTHER", hash="h", state=state, geo_confidence=conf, latitude=-30.0 if state else None,
                  longitude=-51.0 if state else None)


def test_regeolocate_keeps_source_geography_and_clears_stale_text_geography():
    geo = geo_source_ids([{"id": "g1-rs", "adapter": "rss", "state": "RS"}, {"id": "inpe", "adapter": "inpe_fires", "state": None},
                          {"id": "folha", "adapter": "rss", "state": None}])
    assert geo == {"g1-rs", "inpe"}
    assert regeolocate(sig("g1-rs", "RS"), geo).state == "RS"      # estado do feed regional sobrevive
    assert regeolocate(sig("inpe", "PA", conf=60), geo).state == "PA"
    assert regeolocate(sig("folha", "PA"), geo).state is None      # localização antiga errada de fonte nacional é limpa
    fixed = regeolocate(sig("g1-rs", "RS", text="Enchente atinge Manaus"), geo)
    assert fixed.state == "AM"                                     # o texto, quando cita lugar, sempre corrige


# ---- 3) sinal de um evento que não foi reenviado não pode ser descartado -------------------------------------------------
def test_signals_of_an_unchanged_event_are_still_sent_in_their_own_parts():
    batch = _canned_batch()
    batch["events"] = []  # o evento ev-1 não mudou: não está na lista a reenviar
    parts = chunks(batch)
    sent = [g for p in parts for g in p["signals"]]
    assert [g["hash"] for g in sent] == ["h1"]  # antes o sinal era descartado em silêncio


# ---- 4) leitura estrita: "Worker fora do ar" não pode virar "banco vazio" ----------------------------------------------
def _http(code):
    return urllib.error.HTTPError("https://w/x", code, "x", {}, io.BytesIO(b"{}"))


def test_strict_reads_raise_on_unavailable_or_auth_but_soft_reads_return_empty(monkeypatch):
    monkeypatch.setattr(client.time, "sleep", lambda s: None)

    def fail(code):
        def urlopen(req, timeout=0):
            raise _http(code)
        return urlopen

    monkeypatch.setattr(client.urllib.request, "urlopen", fail(503))
    assert client.fetch_signals(base_url="https://w", token="t") == []                      # opcional: segue sem
    with pytest.raises(client.WorkerUnavailable):
        client.fetch_signals(base_url="https://w", token="t", strict=True)                  # estrito: sobe
    monkeypatch.setattr(client.urllib.request, "urlopen", fail(401))
    with pytest.raises(client.WorkerAuthError):
        client.fetch_event_digest(base_url="https://w", token="t", strict=True)
    monkeypatch.delenv("PULSO_INGEST_TOKEN", raising=False)
    with pytest.raises(client.WorkerAuthError):
        client.fetch_signals(base_url="https://w", strict=True)


def test_cycle_is_skipped_when_the_worker_is_unavailable_and_fails_on_bad_token(tmp_path, monkeypatch, capsys):
    pushed = []
    _patch_main(monkeypatch, pushed)
    ran = []
    monkeypatch.setattr(pipeline, "run_once", lambda *a, **k: ran.append(1) or _canned_batch())

    def unavailable(*a, **k):
        raise client.WorkerUnavailable("HTTP 503")

    monkeypatch.setattr(client, "fetch_signals", unavailable)
    cfg = str(_config(tmp_path, "headline_link"))
    assert pipeline.main(["--config", cfg, "--push"]) == 0
    assert not ran and not pushed and "ciclo pulado" in capsys.readouterr().err  # nada recriado nem reenviado

    def auth(*a, **k):
        raise client.WorkerAuthError("Worker recusou o token (HTTP 401)")

    monkeypatch.setattr(client, "fetch_signals", auth)
    assert pipeline.main(["--config", cfg, "--push"]) == 1 and not pushed


# ---- 5) saúde enviada precisa das suas fontes registradas (chave estrangeira) ------------------------------------------
def test_health_rows_bring_their_sources_even_without_signals():
    batch = {"signals": [{"source_id": "a"}], "catalog_complete": True,
             "sources": [{"id": "a"}, {"id": "nova-que-falhou"}, {"id": "outra"}]}
    select_sources(batch, NOW, extra_ids={"nova-que-falhou"})
    assert {s["id"] for s in batch["sources"]} == {"a", "nova-que-falhou"} and batch["catalog_complete"] is False
    full = {"signals": [], "catalog_complete": True, "sources": [{"id": "a"}]}
    select_sources(full, datetime(2026, 10, 3, 12, 31, tzinfo=timezone.utc), extra_ids={"x"})  # horário de revisão: catálogo todo
    assert len(full["sources"]) == 1 and full["catalog_complete"] is True
