"""Coletor RSS/Atom. Usa apenas título, resumo curto e link com atribuição à fonte original."""
from __future__ import annotations

import html
import re
import threading
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from urllib.parse import urlsplit

from ...models import Signal
from ...processing.geo import locate, state_place
from ...processing.keyword_engine import KeywordEngine
from ...processing.normalizer import canonical_url, clean_text, content_hash

USER_AGENT = "pulso-engine/0.1 (+https://github.com/henriquesouza1832001-eng/Pulso)"
MAX_BYTES = 5_000_000
ATOM = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/elements/1.1/}"
RSS1 = "{http://purl.org/rss/1.0/}"

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


def http_fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml", "Accept-Encoding": "gzip"})
    with _host_gate(url):  # coleta em paralelo, mas educada: nunca martela um servidor só
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - URLs vêm de config/sources.json
            data = resp.read(MAX_BYTES + 1)
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

    data = _NAMED_ENTITY.sub(named, data)
    return _BARE_AMP.sub(b"&amp;", data)


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
        root = ET.fromstring(_sanitize_xml(data))
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
        if not title:
            return None
        now = self._now()
        ts = _parse_date(raw.get("date")) or now
        ts = min(ts, now)  # data futura em feed mal configurado nunca vale
        summary = clean_text(raw.get("summary"), 500) or None
        canon = canonical_url(raw.get("link"))
        text = f"{title}. {summary or ''}"
        # O título é o sinal mais forte: só recorre ao resumo se o título não classificar.
        category = self._keywords.classify(title) or self._keywords.classify(text) or "OTHER"
        # Feed regional (source.state = UF): sem lugar no texto, a notícia herda o estado da fonte, com confiança baixa.
        place = locate(text) or (state_place(self.source["state"], confidence=35) if self.source.get("state") else None)
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
