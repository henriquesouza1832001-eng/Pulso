"""INMET: avisos meteorológicos ativos (API pública apiprevmet3). Fonte OFICIAL: confirma, não só detecta."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from ...models import Signal
from ...processing.keyword_engine import KeywordEngine
from ...processing.normalizer import clean_text, content_hash
from .._json import aware, loads, valid
from ..news.rss import RELIABILITY, http_fetch

SEVERITY = ["Perigo Potencial", "Perigo", "Grande Perigo"]
UF_RE = re.compile(r" - ([A-Z]{2}) \(")
BRT = timezone(timedelta(hours=-3))


def _flat(v: Any) -> str:
    return " ".join(map(str, v)) if isinstance(v, list) else str(v or "")


def _centroid(poligono: str | None) -> tuple[float, float] | None:
    try:
        ring = json.loads(poligono or "")["coordinates"][0]
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        return sum(lats) / len(lats), sum(lons) / len(lons)
    except (ValueError, KeyError, IndexError, TypeError):
        return None


class InmetAdapter:
    adapter = "inmet"

    def __init__(self, source: dict[str, Any], keywords: KeywordEngine | None = None,
                 fetcher: Callable[[str], bytes] = http_fetch,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self.source = source
        self.source_id: str = source["id"]
        self.source_class: str = source["source_class"]
        self._fetch = fetcher
        self._now = now
        self._min = SEVERITY.index(source.get("min_severity", "Perigo"))

    def fetch(self) -> list[dict[str, Any]]:
        return list(loads(self._fetch(self.source["url"])).get("hoje", []))

    def normalize(self, raw: dict[str, Any]) -> Signal | None:
        sev = raw.get("severidade")
        if raw.get("encerrado") or sev not in SEVERITY or SEVERITY.index(sev) < self._min:
            return None
        now = self._now()
        desc = clean_text(raw.get("descricao"), 80)
        states = clean_text(raw.get("estados"), 120)
        title = clean_text(f"INMET: {desc} ({sev}) em {states}", 300)
        try:
            ts = aware(datetime.strptime(raw["inicio"], "%Y-%m-%d %H:%M").replace(tzinfo=BRT), now)
        except (KeyError, ValueError):
            ts = now
        ufs = set(UF_RE.findall(raw.get("municipios") or ""))
        place = _centroid(raw.get("poligono")) if len(ufs) == 1 else None
        url = f"https://alertas2.inmet.gov.br/{raw.get('id_aviso')}"
        digest = content_hash(url, title)
        return Signal(
            signal_id=f"sig-{digest}", source_id=self.source_id, source_class=self.source_class,  # type: ignore[arg-type]
            timestamp=ts, collected_at=now, title=title, text=clean_text(_flat(raw.get("riscos")), 500) or None,
            url=url, category="WEATHER", latitude=place[0] if place else None, longitude=place[1] if place else None,
            geo_precision="STATE" if place else None, geo_confidence=70 if place else None,
            reliability=RELIABILITY.get(self.source_class, 90), hash=digest, canonical_url=url,
            state=next(iter(ufs)) if len(ufs) == 1 else None,
        )

    validate = staticmethod(valid)

    def run(self) -> list[Signal]:
        sigs = (self.normalize(r) for r in self.fetch())
        return [s for s in sigs if s is not None and valid(s)]
