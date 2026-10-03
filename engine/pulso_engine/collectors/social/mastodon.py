"""Mastodon: linha do tempo pública por hashtag (API aberta, sem login). Rede social detecta, nunca confirma."""
from __future__ import annotations

import urllib.parse
from datetime import datetime, timezone
from typing import Any, Callable

from ...models import Signal
from ...processing.geo import locate
from ...processing.importance import DEFAULT_THRESHOLD, assess, brazil_relevant
from ...processing.keyword_engine import KeywordEngine
from ...processing.normalizer import canonical_url, clean_text, content_hash
from .._json import aware, loads, valid
from ..news.rss import RELIABILITY, http_fetch

DEFAULT_INSTANCES = ["mastodon.social"]
DEFAULT_TAGS = ["enchente", "deslizamento", "incendio", "apagao", "desabamento", "defesacivil"]
MAX_TAGS = 8


class MastodonAdapter:
    adapter = "mastodon"

    def __init__(self, source: dict[str, Any], keywords: KeywordEngine | None = None,
                 fetcher: Callable[[str], bytes] = http_fetch,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self.source = source
        self.source_id: str = source["id"]
        self.source_class: str = source["source_class"]
        self._keywords = keywords or KeywordEngine()
        self._fetch = fetcher
        self._now = now
        self._threshold = int(source.get("min_importance", DEFAULT_THRESHOLD))

    def fetch(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for inst in self.source.get("instances", DEFAULT_INSTANCES):
            for tag in list(self.source.get("tags", DEFAULT_TAGS))[:MAX_TAGS]:
                url = f"https://{inst}/api/v1/timelines/tag/{urllib.parse.quote(tag)}?limit=40"
                try:
                    out += loads(self._fetch(url))
                except Exception:  # uma instância/tag fora do ar não derruba as outras
                    continue
        return out

    def normalize(self, raw: dict[str, Any]) -> Signal | None:
        if raw.get("language") not in (None, "pt"):
            return None
        text = clean_text(raw.get("content"), 500)
        url = canonical_url(raw.get("url"))
        if not text or not url or assess(text).score < self._threshold:
            return None
        now = self._now()
        try:
            ts = aware(datetime.fromisoformat(str(raw["created_at"]).replace("Z", "+00:00")), now)
        except (KeyError, ValueError):
            ts = now
        place = locate(text)
        if not brazil_relevant(text, place is not None):
            return None  # fora do escopo (outro país)
        digest = content_hash(url, text[:300])
        return Signal(
            signal_id=f"sig-{digest}", source_id=self.source_id, source_class=self.source_class,  # type: ignore[arg-type]
            timestamp=ts, collected_at=now, title=text[:300], text=text, url=url,
            category=self._keywords.classify(text) or "OTHER",  # type: ignore[arg-type]
            latitude=place.lat if place else None, longitude=place.lon if place else None,
            geo_precision=place.precision if place else None,  # type: ignore[arg-type]
            geo_confidence=place.confidence if place else None,
            reliability=RELIABILITY.get(self.source_class, 25), hash=digest, canonical_url=url,
            author=None,  # sem perfil de pessoa
            state=place.uf if place else None, city=place.city if place else None,
        )

    validate = staticmethod(valid)

    def run(self) -> list[Signal]:
        seen: set[str] = set()
        out: list[Signal] = []
        for r in self.fetch():
            s = self.normalize(r)
            if s is not None and valid(s) and s.hash not in seen:
                seen.add(s.hash)
                out.append(s)
        return out
