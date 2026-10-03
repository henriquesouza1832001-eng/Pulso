import pytest


@pytest.fixture(autouse=True)
def _allow_loopback_for_chaos_servers(monkeypatch):
    """Os servidores de caos sobem em 127.0.0.1. O guard SSRF (safe_http.py) bloqueia loopback em produção; aqui a exceção é explícita e só nestes testes."""
    monkeypatch.setenv("PULSO_ALLOW_PRIVATE_FETCH", "1")
