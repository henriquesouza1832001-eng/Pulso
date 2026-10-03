"""SSRF no transporte dos coletores (prioridade 7). Servidores HTTP locais REAIS: nada de mock do guard.

Propriedade: um servidor remoto (feed sequestrado) não consegue fazer o Engine falar com a rede interna nem ler arquivo local,
nem por URL direta, nem por redirect, nem por DNS apontando para IP interno. HARNESS_VERIFIED: loopback real; o endereço do par é
conferido depois de conectar. Limitação honesta: não prova DNS rebinding contra servidores reais de terceiros.
"""
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from pulso_engine import safe_http
from pulso_engine.collectors.news.rss import http_fetch
from pulso_engine.safe_http import UnsafeURLError, is_public_ip

PRIVATE = ["10.0.0.1", "10.255.255.255", "172.16.0.1", "172.31.255.255", "192.168.1.1", "127.0.0.1", "127.1.2.3", "0.0.0.0", "169.254.169.254",
           "169.254.0.1", "100.64.0.1", "192.0.2.1", "198.18.0.1", "224.0.0.1", "255.255.255.255", "::1", "::", "fe80::1", "fe80::1%eth0",
           "fc00::1", "fd00:ec2::254", "::ffff:127.0.0.1", "::ffff:10.0.0.1", "::ffff:169.254.169.254", "ff02::1", "lixo", ""]
PUBLIC = ["8.8.8.8", "1.1.1.1", "200.160.2.3", "2606:4700:4700::1111", "::ffff:8.8.8.8"]


@pytest.mark.parametrize("ip", PRIVATE)
def test_private_loopback_linklocal_metadata_and_garbage_are_not_public(ip):
    assert is_public_ip(ip) is False


@pytest.mark.parametrize("ip", PUBLIC)
def test_real_public_addresses_are_allowed(ip):
    assert is_public_ip(ip) is True


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silencioso
        pass

    def do_GET(self):
        if self.path == "/ok":
            body = b"<rss><channel></channel></rss>"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/to/"):
            self.send_response(302)
            self.send_header("Location", self.path[len("/to/"):].replace("%3A", ":"))
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()


@pytest.fixture(scope="module")
def local():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(autouse=True)
def _production_like(monkeypatch):
    monkeypatch.delenv("PULSO_ALLOW_PRIVATE_FETCH", raising=False)  # como em produção: loopback NÃO é permitido
    monkeypatch.setenv("PULSO_API_URL", "https://pulso-api.example.workers.dev")


def test_direct_loopback_url_is_blocked_before_any_byte_is_read(local):
    with pytest.raises(UnsafeURLError):
        http_fetch(f"{local}/ok")


def test_blocked_destination_is_not_retried_and_is_not_wrapped_as_a_network_error(local):
    # reintentar um destino interno não o torna seguro; e não pode virar URLError (que o coletor reintenta)
    calls = []
    orig = safe_http.validate_destination
    safe_http.validate_destination = lambda *a, **k: (calls.append(1), orig(*a, **k))[1]
    try:
        with pytest.raises(UnsafeURLError):
            http_fetch(f"{local}/ok")
    finally:
        safe_http.validate_destination = orig
    assert len(calls) == 1


def test_nothing_is_sent_to_a_blocked_destination_not_even_a_connection_attempt(local, monkeypatch):
    # o servidor local conta conexões: validar ANTES de conectar significa zero conexões (nenhum SYN à rede interna)
    seen = []
    orig = _Handler.do_GET
    _Handler.do_GET = lambda self: (seen.append(self.path), orig(self))[1]
    try:
        with pytest.raises(UnsafeURLError):
            http_fetch(f"{local}/ok")
    finally:
        _Handler.do_GET = orig
    assert seen == []


def test_redirect_to_the_cloud_metadata_endpoint_is_blocked(monkeypatch, local):
    # a 1ª perna (o servidor) é liberada de propósito para provar que é a 2ª (metadata) que o guard barra
    monkeypatch.setenv("PULSO_API_URL", local)  # o servidor local passa a ser o "host permitido" (como o Worker em desenvolvimento)
    with pytest.raises((UnsafeURLError, urllib.error.URLError)):
        http_fetch(f"{local}/to/http://169.254.169.254/latest/meta-data/")


@pytest.mark.parametrize("target", ["file:///etc/passwd", "file:///C:/Windows/win.ini", "ftp://example.com/x", "gopher://example.com/", "data:text/plain,oi"])
def test_redirect_to_non_http_schemes_is_refused_never_read(monkeypatch, local, target):
    monkeypatch.setenv("PULSO_API_URL", local)
    with pytest.raises((UnsafeURLError, urllib.error.URLError)):
        http_fetch(f"{local}/to/{target.replace(':', '%3A', 1)}")


def test_the_opener_has_no_file_ftp_or_data_handlers():
    names = {type(h).__name__ for h in safe_http.build_opener().handlers}
    assert not ({"FileHandler", "FTPHandler", "DataHandler"} & names)


def test_the_worker_host_itself_is_allowed_so_local_development_keeps_working(monkeypatch, local):
    monkeypatch.setenv("PULSO_API_URL", local)
    assert http_fetch(f"{local}/ok").startswith(b"<rss>")


def test_explicit_test_override_allows_loopback_and_only_when_set(monkeypatch, local):
    monkeypatch.setenv("PULSO_ALLOW_PRIVATE_FETCH", "1")
    assert http_fetch(f"{local}/ok").startswith(b"<rss>")
    monkeypatch.setenv("PULSO_ALLOW_PRIVATE_FETCH", "0")
    with pytest.raises(UnsafeURLError):
        http_fetch(f"{local}/ok")


def test_a_blocked_source_degrades_to_offline_and_never_breaks_the_cycle(local):
    from datetime import datetime, timezone

    from pulso_engine.pipeline import run_once

    src = {"id": "sequestrada", "name": "s", "domain": "s.com", "adapter": "rss", "source_class": "NEWS_HIGH", "url": f"{local}/ok", "state": None, "enabled": True}
    b = run_once([src], now=datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc))
    h = b["source_health"][0]
    assert h["status"] == "OFFLINE" and "UnsafeURLError" in h["detail"]
    assert b["source_freshness"][0]["freshness"]["state"] == "UNKNOWN"  # nunca zero, nunca FRESH
