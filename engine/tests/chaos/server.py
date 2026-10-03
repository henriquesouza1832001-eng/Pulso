"""Servidor HTTP local que INJETA falhas de coletor (matriz de caos). Só escuta em 127.0.0.1, em porta efêmera."""
from __future__ import annotations

import gzip
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NOW = datetime.now(timezone.utc)


def _date(minutes_ago: int) -> str:
    return (NOW - timedelta(minutes=minutes_ago)).strftime("%a, %d %b %Y %H:%M:%S +0000")


def rss(items: list[tuple[str, int]]) -> bytes:
    body = "".join(f"<item><title>{t}</title><link>https://x.invalid/{i}</link><pubDate>{_date(a)}</pubDate></item>" for i, (t, a) in enumerate(items))
    return f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>x</title>{body}</channel></rss>'.encode()


FRESH = rss([("Acidente grave em Betim deixa feridos", 10)])
STALE = rss([("Notícia antiga de anteontem sobre obra", 3000)])
EMPTY = rss([])


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    hits: dict[str, int] = {}

    def log_message(self, *a):  # silencioso
        pass

    def _send(self, code, body=b"", headers=None):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        p = self.path
        Handler.hits[p] = Handler.hits.get(p, 0) + 1
        if p == "/fresh":
            return self._send(200, FRESH, {"Content-Type": "application/rss+xml"})
        if p == "/stale":
            return self._send(200, STALE)
        if p == "/empty":
            return self._send(200, EMPTY)
        if p == "/204":
            return self._send(204)
        if p == "/redirect-ok":
            return self._send(302, b"", {"Location": "/fresh"})
        if p == "/redirect-loop":
            return self._send(302, b"", {"Location": "/redirect-loop"})
        if p == "/301":
            return self._send(301, b"", {"Location": "/fresh"})
        if p == "/304":
            return self._send(304)
        if p in ("/403", "/404", "/408", "/500", "/502", "/503", "/504"):
            return self._send(int(p[1:]), b"erro")
        if p == "/429":
            return self._send(429, b"slow down", {"Retry-After": "120"})
        if p == "/truncated":  # promete 100000 bytes, envia pouco e fecha
            self.send_response(200)
            self.send_header("Content-Length", "100000")
            self.end_headers()
            self.wfile.write(FRESH[:60])
            self.wfile.flush()
            self.close_connection = True
            return
        if p == "/gzip-ok":
            return self._send(200, gzip.compress(FRESH), {"Content-Encoding": "gzip"})
        if p == "/gzip-bad":
            return self._send(200, b"\x1f\x8b" + b"lixo nao gzip" * 10, {"Content-Encoding": "gzip"})
        if p == "/gzip-bomb":
            return self._send(200, gzip.compress(b"A" * 20_000_000), {"Content-Encoding": "gzip"})
        if p == "/latin1":
            body = FRESH.decode().replace("Acidente grave em Betim", "Acidente grave em São Luís").encode("latin-1")
            return self._send(200, body)
        if p == "/bad-utf8":
            return self._send(200, b'<?xml version="1.0" encoding="utf-8"?><rss><channel><item><title>\xff\xfe\xfa</title></item></channel></rss>')
        if p == "/malformed":
            return self._send(200, b"<rss><channel><item><title>quebrado</title></item")
        if p == "/json-not-xml":
            return self._send(200, b'{"items": [{"title": "isto e json"}]}', {"Content-Type": "application/json"})
        if p == "/html":
            return self._send(200, b"<html><body>Pagina de erro disfarcada de 200</body></html>", {"Content-Type": "text/html"})
        if p == "/schema-drift":  # RSS válido, mas sem <item> (tags renomeadas)
            return self._send(200, b'<?xml version="1.0"?><rss><channel><entry-novo><heading>x</heading></entry-novo></channel></rss>')
        if p == "/huge":
            return self._send(200, b"<rss><channel>" + b"<item><title>x</title></item>" * 250_000 + b"</channel></rss>")
        if p == "/hang":  # nunca responde dentro do timeout
            time.sleep(8)
            return self._send(200, FRESH)
        if p == "/drip":  # goteja 1 byte a cada 0,3 s: o timeout por operação nunca dispara
            self.send_response(200)
            self.send_header("Content-Length", str(len(FRESH)))
            self.end_headers()
            for b in FRESH:
                self.wfile.write(bytes([b]))
                self.wfile.flush()
                time.sleep(0.3)
            return
        if p == "/reset":  # fecha sem responder
            self.connection.close()
            self.close_connection = True
            return
        self._send(404, b"?")


class QuietServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):  # clientes que abortam são o ponto do teste: sem traceback no log
        pass


def start() -> tuple[ThreadingHTTPServer, str]:
    srv = QuietServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"
