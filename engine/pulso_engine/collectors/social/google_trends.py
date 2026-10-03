"""Google Trends (RSS público "em alta" do Brasil): o que os brasileiros estão BUSCANDO agora.

É um termômetro de atenção no estilo "pizza index": uma busca que explode costuma anteceder a manchete. O feed traz o
volume aproximado (`approx_traffic`) e as notícias que explicam o termo; usamos o título dessas notícias para
classificar, geolocalizar e filtrar por importância (mesmo critério do resto do motor). Busca detecta, nunca confirma:
classe SOCIAL (confiabilidade baixa), então um evento só ganha peso com fontes de imprensa ou oficiais juntas.
Sem login, sem chave; termos de uso do Google Trends citados em docs/sources/SOURCES.md.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable

from ...models import Signal
from ...processing.geo import locate
from ...processing.importance import DEFAULT_THRESHOLD, assess, brazil_relevant
from ...processing.keyword_engine import KeywordEngine
from ...processing.normalizer import canonical_url, clean_text, content_hash
from .._json import aware, valid
from ..news.rss import RELIABILITY, http_fetch

NS = {"ht": "https://trends.google.com/trending/rss"}


def _traffic(raw: str | None) -> int:
    """'500+', '2 mil+', '1 mi+' -> número aproximado de buscas."""
    m = re.match(r"\s*([\d.,]+)\s*(mil|mi)?", (raw or "").lower())
    if not m:
        return 0
    n = float(m.group(1).replace(".", "").replace(",", ".")) if "," in m.group(1) else float(m.group(1).replace(".", ""))
    return int(n * {"mil": 1_000, "mi": 1_000_000}.get(m.group(2) or "", 1))


class GoogleTrendsAdapter:
    adapter = "google_trends"

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

    def run(self) -> list[Signal]:
        root = ET.fromstring(self._fetch(self.source["url"]))
        now = self._now()
        out: list[Signal] = []
        seen: set[str] = set()
        for item in root.iter("item"):
            term = clean_text(item.findtext("title"), 120)
            traffic = _traffic(item.findtext("ht:approx_traffic", namespaces=NS))
            news = [(clean_text(n.findtext("ht:news_item_title", namespaces=NS), 300), n.findtext("ht:news_item_url", namespaces=NS))
                    for n in item.findall("ht:news_item", NS)]
            news = [(t, u) for t, u in news if t]
            if not term or not news:
                continue
            headline = news[0][0]
            blob = f"{term}. {' '.join(t for t, _ in news[:3])}"
            if assess(blob).score < self._threshold:
                continue
            place = locate(f"{term}. {headline}")  # só termo + manchete principal: as demais notícias misturam outros lugares
            if not brazil_relevant(blob, place is not None):
                continue
            url = canonical_url(news[0][1])
            if not url:
                continue
            try:
                ts = aware(parsedate_to_datetime(item.findtext("pubDate") or ""), now)
            except (TypeError, ValueError):
                ts = now
            vol = f" (cerca de {traffic:,} buscas)".replace(",", ".") if traffic else ""
            text = clean_text(f"Em alta no Google Brasil{vol}: \"{term}\". {headline}", 500)
            digest = content_hash(url, f"trends-{term.lower()}")
            if digest in seen:
                continue
            seen.add(digest)
            s = Signal(
                signal_id=f"sig-{digest}", source_id=self.source_id, source_class=self.source_class,  # type: ignore[arg-type]
                timestamp=min(ts, now), collected_at=now, title=headline, text=text, url=url,
                category=self._keywords.classify(blob) or "OTHER",  # type: ignore[arg-type]
                latitude=place.lat if place else None, longitude=place.lon if place else None,
                geo_precision=place.precision if place else None,  # type: ignore[arg-type]
                geo_confidence=place.confidence if place else None,
                reliability=RELIABILITY.get(self.source_class, 25), hash=digest, canonical_url=url, author=None,
                state=place.uf if place else None, city=place.city if place else None,
            )
            if valid(s):
                out.append(s)
        return out
