"""Defesa Civil Nacional: alertas oficiais (IDAP, formato CAP 1.2 em feed Atom). Fonte OFICIAL.

O feed público tem ~22 MB (cada alerta carrega polígonos enormes), então é lido em FLUXO: só os campos úteis de cada
alerta são extraídos e os polígonos são descartados na hora. Um sinal por alerta vigente (CAP `identifier`), só de
severidade `Moderate` para cima (configurável). Alerta expirado ou cancelado não é sinal de agora.

Segurança: recusa `<!DOCTYPE`/`<!ENTITY` (olhando o início do documento), impõe teto de bytes e nunca guarda geometria.
"""
from __future__ import annotations

import io
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import IO, Any, Callable

from ...models import Signal
from ...processing.geo import locate, state_place
from ...processing.keyword_engine import KeywordEngine
from ...processing.normalizer import clean_text, content_hash
from ..news.rss import RELIABILITY, USER_AGENT

CAP = "{urn:oasis:names:tc:emergency:cap:1.2}"
ATOM = "{http://www.w3.org/2005/Atom}"
PORTAL = "https://www.gov.br/mdr/pt-br/assuntos/protecao-e-defesa-civil"
MAX_STREAM_BYTES = 60_000_000  # o feed real tem ~22 MB; acima disso algo está errado
CHUNK = 64 * 1024
SEVERITY = ["Minor", "Moderate", "Severe", "Extreme"]
SEVERITY_PT = {"Minor": "baixo", "Moderate": "moderado", "Severe": "severo", "Extreme": "extremo"}
UF_RE = re.compile(r"/([A-Z]{2})\b")


def open_stream(url: str) -> IO[bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/atom+xml, application/xml"})
    return urllib.request.urlopen(req, timeout=60)  # noqa: S310 - URL fixa de config/sources.json


def _t(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def _dt(value: str) -> datetime | None:
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def iter_alerts(stream: IO[bytes], max_bytes: int = MAX_STREAM_BYTES):
    """Gera um dict por alerta (sem polígonos), lendo o XML em pedaços."""
    parser = ET.XMLPullParser(events=("end",))
    total = 0
    first = True
    while chunk := stream.read(CHUNK):
        total += len(chunk)
        if total > max_bytes:
            raise ValueError("feed CAP excede o tamanho máximo")
        if first:
            head = chunk[:8192].lower()
            if b"<!entity" in head or b"<!doctype" in head:
                raise ValueError("feed com DOCTYPE/ENTITY recusado")
            first = False
        parser.feed(chunk)
        for _, elem in parser.read_events():
            if elem.tag != f"{CAP}alert":
                continue
            info = elem.find(f"{CAP}info")
            if info is not None:
                yield {
                    "identifier": _t(elem.find(f"{CAP}identifier")), "sent": _t(elem.find(f"{CAP}sent")),
                    "status": _t(elem.find(f"{CAP}status")), "msgType": _t(elem.find(f"{CAP}msgType")),
                    "event": _t(info.find(f"{CAP}event")), "severity": _t(info.find(f"{CAP}severity")),
                    "expires": _t(info.find(f"{CAP}expires")), "senderName": _t(info.find(f"{CAP}senderName")),
                    "description": _t(info.find(f"{CAP}description")),
                    "areas": [_t(a.find(f"{CAP}areaDesc")) for a in info.findall(f"{CAP}area") if _t(a.find(f"{CAP}areaDesc"))],
                }
            elem.clear()  # libera os polígonos da memória


class IdapCapAdapter:
    adapter = "idap_cap"

    def __init__(self, source: dict[str, Any], keywords: KeywordEngine | None = None,
                 fetcher: Callable[[str], IO[bytes] | bytes] | None = None,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self.source = source
        self.source_id: str = source["id"]
        self.source_class: str = source["source_class"]
        self._open = fetcher or open_stream
        self._now = now
        self._min = SEVERITY.index(source.get("min_severity", "Moderate"))

    def fetch(self) -> list[dict[str, Any]]:
        data = self._open(self.source["url"])
        stream = io.BytesIO(data) if isinstance(data, (bytes, bytearray)) else data
        try:
            return list(iter_alerts(stream, int(self.source.get("max_bytes", MAX_STREAM_BYTES))))
        finally:
            close = getattr(stream, "close", None)
            if close:
                close()

    def normalize(self, raw: dict[str, Any]) -> Signal | None:
        if raw["status"] != "Actual" or raw["msgType"] == "Cancel" or not raw["identifier"] or not raw["areas"]:
            return None
        sev = raw["severity"]
        if sev not in SEVERITY or SEVERITY.index(sev) < self._min:
            return None
        now = self._now()
        expires, sent = _dt(raw["expires"]), _dt(raw["sent"])
        if sent is None or (expires is not None and expires <= now):
            return None  # vencido (ou sem data): não é alerta de agora
        areas = raw["areas"]
        ufs = {u for a in areas for u in UF_RE.findall(a)}
        shown = ", ".join(areas[:3]) + (f" e mais {len(areas) - 3} áreas" if len(areas) > 3 else "")
        event = raw["event"].capitalize() or "Alerta"
        title = clean_text(f"Defesa Civil: {event} ({SEVERITY_PT[sev]}) em {shown}", 300)
        uf = next(iter(ufs)) if len(ufs) == 1 else None
        place = None
        if uf:
            city = re.match(r"\s*([^/,]+)/" + uf, areas[0])
            place = (locate(f"{city.group(1).title()}, {uf}") if city and len(areas) == 1 else None) or state_place(uf, confidence=70)
        digest = content_hash(f"{PORTAL}?alerta={raw['identifier']}", f"idap-{raw['identifier']}")
        return Signal(
            signal_id=f"sig-{digest}", source_id=self.source_id, source_class=self.source_class,  # type: ignore[arg-type]
            timestamp=min(sent.astimezone(timezone.utc), now), collected_at=now, title=title,
            text=clean_text(raw["description"], 500) or None, url=PORTAL,
            category="EMERGENCY" if sev == "Extreme" else "WEATHER",
            latitude=place.lat if place else None, longitude=place.lon if place else None,
            geo_precision=place.precision if place else None,  # type: ignore[arg-type]
            geo_confidence=place.confidence if place else None,
            reliability=RELIABILITY.get(self.source_class, 90), hash=digest, canonical_url=PORTAL,
            state=uf, city=place.city if place else None,
        )

    def run(self) -> list[Signal]:
        out: dict[str, Signal] = {}
        for raw in self.fetch():
            s = self.normalize(raw)
            if s is not None:
                out.setdefault(s.hash, s)  # Update com o mesmo identifier não duplica
        return list(out.values())
