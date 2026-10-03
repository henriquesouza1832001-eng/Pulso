"""GDELT DOC 2.0: cobertura de notícias em volume (títulos e links, atualizado a cada ~15 min).

Limite do serviço: 1 requisição a cada 5 s. O coletor faz UMA consulta por rodada.
"""
from __future__ import annotations

import urllib.parse
from datetime import datetime, timezone
from typing import Any, Callable

from ...models import Signal
from ...processing.geo import locate
from ...processing.keyword_engine import KeywordEngine
from ...processing.normalizer import canonical_url, clean_text, content_hash
from .._json import aware, loads, valid
from .rss import RELIABILITY, http_fetch

API = "https://api.gdeltproject.org/api/v2/doc/doc"
DEFAULT_QUERY = "(enchente OR deslizamento OR incêndio OR apagão OR embaixada OR tornado OR tempestade) sourcecountry:BR sourcelang:portuguese"


class GdeltAdapter:
    adapter = "gdelt"

    def __init__(self, source: dict[str, Any], keywords: KeywordEngine | None = None,
                 fetcher: Callable[[str], bytes] = http_fetch,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self.source = source
        self.source_id: str = source["id"]
        self.source_class: str = source["source_class"]
        self._keywords = keywords or KeywordEngine()
        self._fetch = fetcher
        self._now = now

    def fetch(self) -> list[dict[str, Any]]:
        q = urllib.parse.urlencode({"query": self.source.get("query", DEFAULT_QUERY), "mode": "artlist", "format": "json",
                                    "maxrecords": "75", "sort": "datedesc", "timespan": self.source.get("timespan", "60min")})
        data = self._fetch(f"{API}?{q}")
        if not data.lstrip().startswith(b"{"):
            raise RuntimeError(f"RATE_LIMITED ou resposta inesperada do GDELT: {data[:80]!r}")
        return list(loads(data).get("articles", []))

    def normalize(self, raw: dict[str, Any]) -> Signal | None:
        title = clean_text(raw.get("title"), 300)
        url = canonical_url(raw.get("url"))
        if not title or not url:
            return None
        now = self._now()
        try:
            ts = aware(datetime.strptime(raw["seendate"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc), now)
        except (KeyError, ValueError):
            ts = now
        place = locate(title)
        digest = content_hash(url, title)
        return Signal(
            signal_id=f"sig-{digest}", source_id=self.source_id, source_class=self.source_class,  # type: ignore[arg-type]
            timestamp=ts, collected_at=now, title=title, url=url, category=self._keywords.classify(title) or "OTHER",  # type: ignore[arg-type]
            latitude=place.lat if place else None, longitude=place.lon if place else None,
            geo_precision=place.precision if place else None,  # type: ignore[arg-type]
            geo_confidence=place.confidence if place else None,
            reliability=RELIABILITY.get(self.source_class, 60), hash=digest, canonical_url=url,
            state=place.uf if place else None, city=place.city if place else None,
        )

    validate = staticmethod(valid)

    def run(self) -> list[Signal]:
        out: dict[str, Signal] = {}
        for r in self.fetch():
            s = self.normalize(r)
            if s is not None and valid(s):
                out.setdefault(s.hash, s)  # a mesma URL repetida não gera dois sinais com o mesmo id
        return list(out.values())
