"""Transporte HTTP seguro contra SSRF (campanha de plataforma, prioridade 7).

As URLs dos coletores vêm de `config/sources.json` (curadas pelo projeto), mas o servidor remoto controla os REDIRECTS e o DNS:
um feed sequestrado poderia mandar o Engine (que roda num runner com acesso à rede interna e ao endpoint de metadados da nuvem)
para `http://169.254.169.254/`, `localhost`, `10.x`... Este módulo fecha a classe, não os casos:

- resolve o nome e valida TODOS os endereços ANTES de conectar; só então conecta direto no IP validado (nenhum pacote vai à rede
  interna, e o DNS não pode ser trocado entre a checagem e o uso: sem janela de DNS rebinding). O TLS segue usando o nome original
  (SNI e verificação de certificado intactos);
- só destino público (`ipaddress.is_global`): bloqueia loopback, RFC1918, link-local (metadata), CGNAT, ULA, multicast, reservado,
  e IPv4 mapeado em IPv6;
- só http/https (nada de `file://`, `ftp://`, `data:`), inclusive em redirect.

Exceções declaradas: o próprio Worker do PULSO (host de `PULSO_API_URL`, que no desenvolvimento é `localhost`) e a variável
`PULSO_ALLOW_PRIVATE_FETCH=1`, só para os testes de caos que sobem servidores em loopback. Em produção a variável não existe.
Instalado como opener global em `pulso_engine/__init__.py`, então vale para RSS, INMET, IDAP, INPE, sociais e o cliente do Worker.
Limitação: se houver proxy no ambiente (HTTP(S)_PROXY), o destino validado é o do proxy, que então decide o resto.
"""
from __future__ import annotations

import http.client
import ipaddress
import os
import socket
import urllib.request
from urllib.parse import urlparse


class UnsafeURLError(ValueError):
    """Destino bloqueado (rede interna, esquema proibido). ValueError de propósito: `urllib` não a embrulha em URLError e o coletor
    NÃO tenta de novo (reintentar um destino interno não o torna seguro)."""


def _api_host() -> tuple[str | None, int | None]:
    p = urlparse(os.environ.get("PULSO_API_URL", "http://localhost:8787"))
    return p.hostname, p.port


def is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip.split("%")[0])  # remove o escopo de IPv6 (fe80::1%eth0)
    except ValueError:
        return False  # endereço ilegível: não é seguro assumir que é público
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_global and not addr.is_multicast


def _allowed(host: str | None, port: int | None) -> bool:
    if os.environ.get("PULSO_ALLOW_PRIVATE_FETCH", "") in ("1", "true", "on"):
        return True
    api_host, api_port = _api_host()
    return bool(host) and host == api_host and (api_port is None or port is None or port == api_port)


def validate_destination(host: str, port: int) -> list[tuple]:
    """Resolve `host` e devolve os endereços (família, tipo, proto, _, sockaddr) se TODOS forem públicos; senão UnsafeURLError.
    Falha de resolução propaga como `socket.gaierror` (problema de rede comum, não de segurança)."""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    for _fam, _typ, _proto, _canon, sockaddr in infos:
        if not is_public_ip(sockaddr[0]):
            raise UnsafeURLError(f"destino bloqueado (endereço não público): {host}")
    return infos


def _guarded_create_connection(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
    host, port = address
    if _allowed(host, port):
        return socket.create_connection(address, timeout, source_address)
    infos = validate_destination(host, port)  # nada é enviado antes disto
    err: OSError | None = None
    for fam, typ, proto, _canon, sockaddr in infos:  # conecta nos IPs JÁ validados, na ordem (mesmo fallback de create_connection)
        sock = socket.socket(fam, typ, proto)
        try:
            if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sockaddr)
            return sock
        except OSError as exc:
            err = exc
            sock.close()
    raise err or OSError(f"sem endereço para {host}")


class _HTTPConnection(http.client.HTTPConnection):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._create_connection = _guarded_create_connection


class _HTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._create_connection = _guarded_create_connection


class _HTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(_HTTPConnection, req)


class _HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_HTTPSConnection, req, context=self._context)


class _Redirect(urllib.request.HTTPRedirectHandler):
    """Só segue redirect para http/https (o padrão do urllib também aceitaria ftp)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse(newurl).scheme not in ("http", "https"):
            raise UnsafeURLError(f"redirect para esquema proibido: {urlparse(newurl).scheme or '(vazio)'}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def build_opener() -> urllib.request.OpenerDirector:
    """Opener com SÓ o que o Engine usa: http/https com validação de destino, redirect restrito, proxy do ambiente. Sem file/ftp/data."""
    opener = urllib.request.OpenerDirector()
    for h in (urllib.request.ProxyHandler(), urllib.request.UnknownHandler(), _HTTPHandler(), _HTTPSHandler(),
              urllib.request.HTTPDefaultErrorHandler(), _Redirect(), urllib.request.HTTPErrorProcessor()):
        opener.add_handler(h)
    return opener


def install() -> None:
    urllib.request.install_opener(build_opener())
