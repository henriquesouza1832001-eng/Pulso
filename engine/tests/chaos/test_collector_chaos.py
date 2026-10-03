"""Matriz de caos dos coletores (campanha de plataforma §4): cada falha de transporte/conteúdo contra um servidor HTTP local.

Invariantes (valem para TODAS as linhas): o ciclo nunca levanta exceção; o transporte é um dos 5 estados; nada que falhou ou veio
quebrado/velho aparece como FRESH; falha de transporte => frescor UNKNOWN (nunca zero); tempo limitado. HARNESS_VERIFIED: servidor
local real (urllib de verdade); não prova o comportamento de servidores de terceiros na produção.
"""
import time
import types
import urllib.request
from datetime import datetime, timezone

import pytest

from pulso_engine.collectors.news import rss as R
from pulso_engine.pipeline import run_once
from tests.chaos.server import start

TRANSPORTS = {"ONLINE", "DEGRADED", "RATE_LIMITED", "OFFLINE", "AUTH_ERROR"}
OFF, ONL, DEG, RL = "OFFLINE", "ONLINE", "DEGRADED", "RATE_LIMITED"

# caminho -> (transporte, frescor). Decisões de classificação documentadas em docs/operations/FAILURE_RUNBOOK.md.
MATRIX = {
    "fresh": (ONL, "FRESH"), "stale": (ONL, "STALE"), "empty": (DEG, "EMPTY"),
    "204": (OFF, "UNKNOWN"), "redirect-ok": (ONL, "FRESH"), "301": (ONL, "FRESH"), "redirect-loop": (OFF, "UNKNOWN"),
    "304": (OFF, "UNKNOWN"), "403": (OFF, "UNKNOWN"), "404": (OFF, "UNKNOWN"), "408": (OFF, "UNKNOWN"), "429": (RL, "UNKNOWN"),
    "500": (OFF, "UNKNOWN"), "502": (OFF, "UNKNOWN"), "503": (OFF, "UNKNOWN"), "504": (OFF, "UNKNOWN"),
    "truncated": (OFF, "UNKNOWN"), "gzip-ok": (ONL, "FRESH"), "gzip-bad": (OFF, "UNKNOWN"), "gzip-bomb": (OFF, "UNKNOWN"),
    "latin1": (ONL, "FRESH"), "bad-utf8": (ONL, "UNKNOWN"),  # título ilegível e sem data: lido, mas frescor não verificável
    "malformed": (OFF, "UNKNOWN"), "json-not-xml": (OFF, "UNKNOWN"), "html": (DEG, "EMPTY"), "schema-drift": (DEG, "EMPTY"),
    "huge": (OFF, "UNKNOWN"), "hang": (OFF, "UNKNOWN"), "reset": (OFF, "UNKNOWN"), "drip": (OFF, "UNKNOWN"),
}


@pytest.fixture(scope="module")
def server():
    srv, base = start()
    yield base
    srv.shutdown()


@pytest.fixture(autouse=True)
def fast_network(monkeypatch):
    real = urllib.request.urlopen
    monkeypatch.setattr(R.urllib.request, "urlopen", lambda req, timeout=15: real(req, timeout=1))  # leitura/conexão: 1 s nos testes
    # sem espera entre tentativas; shim só dentro do módulo do coletor (o servidor de teste continua usando o time.sleep real)
    monkeypatch.setattr(R, "time", types.SimpleNamespace(sleep=lambda s: None, monotonic=time.monotonic))
    monkeypatch.setattr(R, "FETCH_DEADLINE_S", 2.0)  # prazo total de leitura (gotejamento)


def cycle(url, **extra):
    src = {"id": "chaos", "name": "chaos", "domain": "chaos", "adapter": "rss", "source_class": "NEWS_HIGH", "url": url, "state": None, "enabled": True, **extra}
    t0 = time.monotonic()
    batch = run_once([src], fetcher=R.http_fetch, now=datetime.now(timezone.utc))
    return batch, time.monotonic() - t0


@pytest.mark.parametrize("case", sorted(MATRIX))
def test_http_and_content_faults(server, case):
    batch, elapsed = cycle(f"{server}/{case}")
    health, fresh = batch["source_health"][0], batch["source_freshness"][0]
    transport, state = MATRIX[case]
    assert health["status"] in TRANSPORTS
    assert (health["status"], fresh["freshness"]["state"]) == (transport, state), (case, health["detail"])
    if state != "FRESH":
        assert fresh["freshness"]["state"] != "FRESH"
        # Nada quebrado vira sinal. Exceções DOCUMENTADAS: "stale" (matéria velha lida corretamente) e "bad-utf8" (item sem data válida
        # entra com timestamp = instante da coleta: comportamento antigo do coletor, achado F-1 em docs/maturity/PLATFORM_MATURITY.md;
        # o frescor da FONTE não é inflado por isso, pois a saúde trata o item como sem data verificável).
        assert batch["signals"] == [] or case in ("stale", "bad-utf8")
    if transport in (OFF, RL):
        assert fresh["freshness"]["newest_item_age_min"] is None  # falha de transporte nunca vira "idade zero"
    assert elapsed < 12, f"{case} demorou {elapsed:.1f}s"


def test_429_keeps_rate_limited_state_and_is_not_retried(server):
    from tests.chaos.server import Handler
    Handler.hits.clear()
    batch, _ = cycle(f"{server}/429")
    assert batch["source_health"][0]["status"] == "RATE_LIMITED" and Handler.hits["/429"] == 1  # não insiste (Retry-After respeitado: 1 tentativa)


def test_5xx_is_not_retried_either(server):
    from tests.chaos.server import Handler
    Handler.hits.clear()
    cycle(f"{server}/503")
    assert Handler.hits["/503"] == 1


@pytest.mark.parametrize("url", ["http://nonexistent.invalid/rss", "http://127.0.0.1:9/rss"])
def test_dns_failure_and_refused_connection(url):
    batch, elapsed = cycle(url)
    assert batch["source_health"][0]["status"] == "OFFLINE" and batch["source_freshness"][0]["freshness"]["state"] == "UNKNOWN" and elapsed < 12


def test_tls_error_against_plain_http_port(server):
    batch, _ = cycle("https://" + server.split("//")[1] + "/fresh")
    assert batch["source_health"][0]["status"] == "OFFLINE" and "SSL" in (batch["source_health"][0]["detail"] or "")


def test_one_broken_source_never_stops_the_others(server):
    good = {"id": "ok", "name": "ok", "domain": "ok", "adapter": "rss", "source_class": "NEWS_HIGH", "url": f"{server}/fresh", "state": None, "enabled": True}
    bad = {**good, "id": "bad", "url": f"{server}/gzip-bomb"}
    batch = run_once([bad, good], fetcher=R.http_fetch, now=datetime.now(timezone.utc))
    status = {h["source_id"]: h["status"] for h in batch["source_health"]}
    assert status == {"bad": "OFFLINE", "ok": "ONLINE"} and batch["signals"]


def test_quiet_threshold_source_empty_is_quiet_not_an_error(server):
    batch, _ = cycle(f"{server}/empty", quiet_ok=True)
    assert batch["source_health"][0]["status"] == "ONLINE" and batch["source_freshness"][0]["freshness"]["state"] == "QUIET"
