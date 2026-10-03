"""USGS: terremotos significativos (GeoJSON oficial). Entra como INTERNATIONAL; coordenadas só se dentro do Brasil."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from ...models import Signal
from ...processing.keyword_engine import KeywordEngine
from ...processing.normalizer import clean_text, content_hash
from .._json import aware, loads, valid
from ..news.rss import RELIABILITY, http_fetch


class UsgsAdapter:
    adapter = "usgs"

    def __init__(self, source: dict[str, Any], keywords: KeywordEngine | None = None,
                 fetcher: Callable[[str], bytes] = http_fetch,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self.source = source
        self.source_id: str = source["id"]
        self.source_class: str = source["source_class"]
        self._fetch = fetcher
        self._now = now

    def fetch(self) -> list[dict[str, Any]]:
        return list(loads(self._fetch(self.source["url"])).get("features", []))

    def normalize(self, raw: dict[str, Any]) -> Signal | None:
        p = raw.get("properties") or {}
        title = clean_text(f"Terremoto: {p.get('title')}", 300) if p.get("title") else ""
        url = p.get("url")
        if not title or not url or p.get("time") is None:
            return None
        now = self._now()
        ts = aware(datetime.fromtimestamp(p["time"] / 1000, tz=timezone.utc), now)
        lon, lat = (raw.get("geometry") or {}).get("coordinates", [None, None])[:2]
        in_br = lat is not None and -34 <= lat <= 6 and -74 <= lon <= -34
        digest = content_hash(url, title)
        return Signal(
            signal_id=f"sig-{digest}", source_id=self.source_id, source_class=self.source_class,  # type: ignore[arg-type]
            timestamp=ts, collected_at=now, title=title, url=url, category="INTERNATIONAL",
            latitude=lat if in_br else None, longitude=lon if in_br else None,
            geo_precision="POINT" if in_br else None, geo_confidence=90 if in_br else None,
            reliability=RELIABILITY.get(self.source_class, 90), hash=digest, canonical_url=url,
        )

    validate = staticmethod(valid)

    def run(self) -> list[Signal]:
        sigs = (self.normalize(r) for r in self.fetch())
        return [s for s in sigs if s is not None and valid(s)]
