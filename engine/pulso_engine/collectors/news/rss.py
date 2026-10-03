"""Coletor RSS/Atom. Usa apenas título, resumo curto e link com atribuição à fonte original."""
from __future__ import annotations

import html
import re
import socket
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from urllib.parse import urlsplit

from ...models import Signal
from ...processing.geo import locate, state_place
from ...processing.importance import brazil_relevant
from ...processing.keyword_engine import KeywordEngine
from ...processing.normalizer import canonical_url, clean_text, content_hash, is_broadcast_listing

USER_AGENT = "pulso-engine/0.1 (+https://github.com/henriquesouza1832001-eng/Pulso)"
MAX_BYTES = 5_000_000
ATOM = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/elements/1.1/}"
RSS1 = "{http://purl.org/rss/1.0/}"
PHYSICAL_CATEGORIES = frozenset({"WEATHER", "TRAFFIC", "SECURITY", "INFRASTRUCTURE", "EMERGENCY", "HEALTH", "PROTEST"})

# Confiabilidade base da FONTE por classe (um componente da confiança do evento, nunca "verdade").
RELIABILITY = {
    "OFFICIAL": 90, "NEWS_HIGH": 75, "NEWS_REGIONAL": 60, "TRAFFIC_PROVIDER": 70,
    "SOCIAL_VERIFIED": 45, "SOCIAL": 25, "UNKNOWN": 30,
}


PER_HOST_MAX = 2  # no máximo 2 requisições simultâneas ao MESMO servidor (o G1 tem ~20 feeds no mesmo host)
_host_gates: dict[str, threading.BoundedSemaphore] = {}
_host_gates_lock = threading.Lock()


def _host_gate(url: str) -> threading.BoundedSemaphore:
    host = (urlsplit(url).hostname or "").lower()
    with _host_gates_lock:
        return _host_gates.setdefault(host, threading.BoundedSemaphore(PER_HOST_MAX))


FETCH_DEADLINE_S = 30.0  # tempo TOTAL de leitura: o timeout do socket é por operação, então um servidor que goteja 1 byte por vez prenderia a coleta


def _read_bounded(resp, deadline_s: float | None = None) -> bytes:
    """Lê no máximo MAX_BYTES + 1 dentro de um prazo total (slow-loris/gotejamento não segura a coleta indefinidamente)."""
    limit = time.monotonic() + (FETCH_DEADLINE_S if deadline_s is None else deadline_s)
    chunks: list[bytes] = []
    total = 0
    while total <= MAX_BYTES:
        if time.monotonic() > limit:
            raise TimeoutError("leitura do feed excedeu o prazo total")
        # read1: devolve o que chegou numa leitura (read(n) esperaria n bytes, e o prazo nunca seria checado num servidor que goteja)
        chunk = getattr(resp, "read1", resp.read)(min(65536, MAX_BYTES + 1 - total))
        if not chunk:
            # read1 devolve b"" quando a conexão fecha antes do Content-Length prometido (não levanta IncompleteRead):
            # é falha de TRANSPORTE, não um XML quebrado (QA-006 separa as duas).
            if getattr(resp, "length", None):
                raise ConnectionError(f"conexão encerrada com {resp.length} bytes faltando (Content-Length)")
            break
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks)


def http_fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml", "Accept-Encoding": "gzip"})
    with _host_gate(url):  # coleta em paralelo, mas educada: nunca martela um servidor só
        for attempt in (1, 2):
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - URLs vêm de config/sources.json
                    data = _read_bounded(resp)
                break
            except urllib.error.HTTPError:
                raise  # 4xx/5xx é resposta do servidor (429, 403...): não insistir
            except (TimeoutError, socket.timeout, ConnectionError, urllib.error.URLError):
                if attempt == 2:
                    raise
                time.sleep(1.0)  # falha de rede transitória: uma segunda tentativa, só
    if len(data) > MAX_BYTES:
        raise ValueError("feed excede o tamanho máximo")
    if data[:2] == b"\x1f\x8b":  # gzip (alguns servidores comprimem mesmo sem pedido)
        # limite na SAÍDA: protege contra "bomba de descompressão"
        data = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(data, MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("feed descomprimido excede o tamanho máximo")
    return data


def _ensure_utf8(data: bytes) -> bytes:
    """Alguns feeds (ex.: UOL) vêm em Latin-1 sem declarar a codificação."""
    try:
        data.decode("utf-8")
        return data
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")
        if text.lstrip().startswith("<?xml"):
            text = text[text.index("?>") + 2:]
        return ('<?xml version="1.0" encoding="utf-8"?>' + text).encode("utf-8")


_XML_ENTITIES = {"amp", "lt", "gt", "quot", "apos"}
_MARKUP = {"<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&apos;"}
_NAMED_ENTITY = re.compile(rb"&([A-Za-z][A-Za-z0-9]*);")
_CDATA = re.compile(rb"(<!\[CDATA\[.*?\]\]>)", re.DOTALL)
_BARE_AMP = re.compile(rb"&(?![A-Za-z][A-Za-z0-9]*;|#[0-9]+;|#[xX][0-9a-fA-F]+;)")


def _sanitize_xml(data: bytes) -> bytes:
    """Tolera erros comuns de quem publica o feed: '&' solto e entidades HTML (&nbsp;, &eacute;...).

    Não relaxa a segurança: declarações <!ENTITY continuam recusadas antes de chegar aqui.
    """
    def named(m: re.Match[bytes]) -> bytes:
        name = m.group(1).decode()
        if name in _XML_ENTITIES:
            return m.group(0)
        char = html.unescape(m.group(0).decode())
        if char == m.group(0).decode():
            return m.group(0)  # entidade desconhecida: deixa (o parser recusa o feed)
        # `&LT;`/`&AMP;` em maiúsculas viram caracteres de marcação: reescapa, nunca injeta markup no XML.
        return "".join(_MARKUP.get(c, c) for c in char).encode("utf-8")

    # Dentro de <![CDATA[...]]> o texto é LITERAL: um "&" ali (ex.: URL com ?a=1&b=2) não pode virar "&amp;".
    parts = _CDATA.split(data)
    for i in range(0, len(parts), 2):  # índices pares = fora do CDATA
        parts[i] = _BARE_AMP.sub(b"&amp;", _NAMED_ENTITY.sub(named, parts[i]))
    return b"".join(parts)


def _text(el: ET.Element | None) -> str | None:
    return el.text.strip() if el is not None and el.text else None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class FeedContentError(ValueError):
    """O transporte funcionou (a resposta chegou), mas o corpo não é um feed legível: vazio ou XML quebrado.
    É problema de DADO, não de rede (QA-006): a saúde fica DEGRADED e o circuit breaker não abre."""
    health_status = "DEGRADED"


class RssAdapter:
    adapter = "rss"

    def __init__(
        self,
        source: dict[str, Any],
        keywords: KeywordEngine | None = None,
        fetcher: Callable[[str], bytes] = http_fetch,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.source = source
        self.source_id: str = source["id"]
        self.source_class: str = source["source_class"]
        self._keywords = keywords or KeywordEngine()
        self._fetch = fetcher
        self._now = now

    def fetch(self) -> list[dict[str, Any]]:
        data = _ensure_utf8(self._fetch(self.source["url"]))
        # stdlib não protege contra entidades XML maliciosas: recusamos DTDs com ENTITY.
        if b"<!ENTITY" in data:
            raise ValueError("feed com declaração ENTITY recusado")
        if not data.strip():
            raise FeedContentError("resposta vazia (transporte ok, sem conteúdo)")
        try:
            root = ET.fromstring(_sanitize_xml(data))
        except ET.ParseError as exc:
            raise FeedContentError(f"XML ilegível: {exc}") from exc
        items: list[dict[str, Any]] = []
        for it in root.iter("item"):
            items.append({
                "title": _text(it.find("title")), "link": _text(it.find("link")),
                "summary": _text(it.find("description")), "date": _text(it.find("pubDate")) or _text(it.find(f"{DC}date")),
                "author": _text(it.find(f"{DC}creator")) or _text(it.find("author")),
            })
        for it in root.iter(f"{RSS1}item"):  # RSS 1.0 / RDF (ex.: portais gov.br)
            items.append({
                "title": _text(it.find(f"{RSS1}title")), "link": _text(it.find(f"{RSS1}link")),
                "summary": _text(it.find(f"{RSS1}description")), "date": _text(it.find(f"{DC}date")),
                "author": _text(it.find(f"{DC}creator")),
            })
        for it in root.iter(f"{ATOM}entry"):
            link = it.find(f"{ATOM}link")
            items.append({
                "title": _text(it.find(f"{ATOM}title")), "link": link.get("href") if link is not None else None,
                "summary": _text(it.find(f"{ATOM}summary")), "date": _text(it.find(f"{ATOM}updated")) or _text(it.find(f"{ATOM}published")),
                "author": _text(it.find(f"{ATOM}author/{ATOM}name")),
            })
        return items

    def normalize(self, raw: dict[str, Any]) -> Signal | None:
        title = clean_text(raw.get("title"), 300)
        if not title or is_broadcast_listing(title):
            return None  # sem título, ou chamada de edição de telejornal (não é notícia)
        now = self._now()
        ts = _parse_date(raw.get("date")) or now
        ts = min(ts, now)  # data futura em feed mal configurado nunca vale
        summary = clean_text(raw.get("summary"), 500) or None
        canon = canonical_url(raw.get("link"))
        text = f"{title}. {summary or ''}"
        # O título é o sinal mais forte: só recorre ao resumo se o título não classificar.
        category = self._keywords.classify(title) or self._keywords.classify(text) or "OTHER"
        # Feed regional (source.state = UF): sem lugar no texto, a notícia herda o estado da fonte, com confiança baixa.
        explicit_place = locate(text)
        place = explicit_place or (state_place(self.source["state"], confidence=35) if self.source.get("state") else None)
        # Acontecimento físico de OUTRO país (engarrafamento na Ucrânia, surto na Flórida, protesto na França) não conta nas
        # séries brasileiras de clima/trânsito/saúde...: vira INTERNATIONAL. Política e economia ficam como estão (citam
        # países estrangeiros o tempo todo em assuntos brasileiros). Só o lugar EXPLÍCITO no texto vale, não o da fonte.
        if category in PHYSICAL_CATEGORIES and not brazil_relevant(text, explicit_place is not None):
            category = "INTERNATIONAL"
        digest = content_hash(canon, title)
        return Signal(
            signal_id=f"sig-{digest}", source_id=self.source_id, source_class=self.source_class,  # type: ignore[arg-type]
            timestamp=ts, collected_at=now, title=title, text=summary, url=canon, category=category,  # type: ignore[arg-type]
            latitude=place.lat if place else None, longitude=place.lon if place else None,
            geo_precision=place.precision if place else None,  # type: ignore[arg-type]
            geo_confidence=place.confidence if place else None,
            reliability=self.score_reliability(None), hash=digest, canonical_url=canon,
            author=clean_text(raw.get("author"), 200) or None,
            state=place.uf if place else None, city=place.city if place else None,
        )

    def validate(self, signal: Signal) -> bool:
        return bool(signal.title.strip()) and signal.timestamp.tzinfo is not None

    def geolocate(self, signal: Signal) -> Signal:
        return signal  # já feita em normalize()

    def score_reliability(self, signal: Signal | None) -> int:
        return RELIABILITY.get(self.source_class, 30)

    def run(self) -> list[Signal]:
        out: list[Signal] = []
        for raw in self.fetch():
            sig = self.normalize(raw)
            if sig is not None and self.validate(sig):
                out.append(sig)
        return out
