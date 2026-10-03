"""Injeção de falha / SSRF (docs/reliability/FAILURE_INJECTION_REPORT.md). Complementa test_ssrf_guard.py."""
import socket
import urllib.request

import pytest

from pulso_engine import safe_http
from pulso_engine.safe_http import UnsafeURLError, is_public_ip, validate_destination


@pytest.mark.parametrize("ip, alvo", [
    ("64:ff9b::7f00:1", "NAT64 -> 127.0.0.1"),
    ("64:ff9b::a9fe:a9fe", "NAT64 -> 169.254.169.254 (metadata)"),
    ("64:ff9b::a00:1", "NAT64 -> 10.0.0.1"),
    ("64:ff9b::c0a8:101", "NAT64 -> 192.168.1.1"),
    ("64:ff9b::6440:1", "NAT64 -> 100.64.0.1 (CGNAT)"),
    ("::7f00:1", "IPv4-compatível -> 127.0.0.1"),
    ("::a9fe:a9fe", "IPv4-compatível -> metadata"),
    ("fec0::1", "site-local obsoleto"),
    ("fd00:ec2::254", "metadata IPv6 da AWS (ULA)"),
    ("::ffff:169.254.169.254", "IPv4 mapeado -> metadata"),
    ("2002:a9fe:a9fe::", "6to4 -> metadata"),
    ("100.100.100.200", "metadata Alibaba (CGNAT)"),
    ("0.0.0.0", "0.0.0.0"), ("::", "::"), ("255.255.255.255", "broadcast"), ("224.0.0.1", "multicast v4"),
])
def test_ipv6_wrapping_a_private_ipv4_is_blocked(ip, alvo):
    """FI-001: o `is_global` do Python considera NAT64 (64:ff9b::/96) e IPv4-compatível globais; numa rede com DNS64/NAT64 eles
    alcançam o IPv4 embutido (inclusive o metadata da nuvem)."""
    assert not is_public_ip(ip), alvo


@pytest.mark.parametrize("ip", ["64:ff9b::808:808", "::ffff:8.8.8.8", "2001:4860:4860::8888", "1.1.1.1"])
def test_public_destinations_including_nat64_to_public_still_work(ip):
    assert is_public_ip(ip)  # o endurecimento não bloqueia destino público legítimo


@pytest.mark.parametrize("host", ["2130706433", "0x7f000001", "0177.0.0.1", "127.1", "0x7f.1", "017700000001", "localhost"])
def test_encoded_loopback_forms_are_resolved_then_blocked(host, monkeypatch):
    monkeypatch.delenv("PULSO_ALLOW_PRIVATE_FETCH", raising=False)
    with pytest.raises(UnsafeURLError):
        validate_destination(host, 80)


def test_mixed_dns_answer_public_plus_private_is_blocked(monkeypatch):
    """DNS que devolve um IP público E um interno (round-robin hostil / rebinding): TODOS precisam ser públicos."""
    answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
               (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 80))]
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: answers)
    with pytest.raises(UnsafeURLError):
        validate_destination("feed.example", 80)


def test_dns_answer_with_nat64_metadata_is_blocked(monkeypatch):
    answers = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("64:ff9b::a9fe:a9fe", 80, 0, 0))]
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: answers)
    with pytest.raises(UnsafeURLError):
        validate_destination("feed.example", 80)


@pytest.mark.parametrize("url", ["http://evil@127.0.0.1/", "http://user:pass@169.254.169.254/latest/meta-data/",
                                 "http://127.0.0.1:80@feed.example/", "http://[::ffff:127.0.0.1]/", "http://%31%32%37.0.0.1/",
                                 "http://[64:ff9b::a9fe:a9fe]/latest/meta-data/"])
def test_userinfo_and_encoded_urls_never_open_a_socket_to_a_private_address(url, monkeypatch):
    """Qualquer que seja o motivo da recusa (guarda, URL inválida, nome inexistente), nenhum socket conecta num IP interno."""
    monkeypatch.delenv("PULSO_ALLOW_PRIVATE_FETCH", raising=False)
    monkeypatch.setenv("PULSO_API_URL", "https://pulso-api.example.workers.dev")
    dialed = []

    def fake_connect(self, addr):
        dialed.append(addr[0])
        raise ConnectionRefusedError("teste: nenhuma conexão real")

    monkeypatch.setattr(socket.socket, "connect", fake_connect)
    with pytest.raises(Exception):
        safe_http.build_opener().open(urllib.request.Request(url), timeout=2)
    assert all(is_public_ip(ip) for ip in dialed), dialed
