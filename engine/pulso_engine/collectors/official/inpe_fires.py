"""INPE Queimadas: focos de calor detectados por satélite (dados abertos, arquivo CSV diário do Brasil).

Um sinal por UF quando o número de detecções nas últimas `window_h` horas passa de `min_focos`: é o indicador
objetivo de uma frente de fogo (e da fumaça que ela leva às cidades), em vez de esperar a imprensa. Fonte OFICIAL.
Um foco é uma detecção de calor, não necessariamente um incêndio confirmado: o texto diz "detecções".
Citar a fonte (INPE) é condição de uso dos dados abertos.
"""
from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from ...models import Signal
from ...processing.geo import state_place, uf_from_state_name
from ...processing.keyword_engine import KeywordEngine
from ...processing.normalizer import clean_text, content_hash
from ..news.rss import RELIABILITY, http_fetch

PORTAL = "https://terrabrasilis.dpi.inpe.br/queimadas/situacao-atual/"
DEFAULT_MIN_FOCOS = 150
DEFAULT_WINDOW_H = 3


def _day_url(base: str, day: datetime) -> str:
    return f"{base.rstrip('/')}/focos_diario_br_{day.strftime('%Y%m%d')}.csv"


class InpeFiresAdapter:
    adapter = "inpe_fires"

    def __init__(self, source: dict[str, Any], keywords: KeywordEngine | None = None,
                 fetcher: Callable[[str], bytes] = http_fetch,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self.source = source
        self.source_id: str = source["id"]
        self.source_class: str = source["source_class"]
        self._fetch = fetcher
        self._now = now
        self._min = int(source.get("min_focos", DEFAULT_MIN_FOCOS))
        self._window = timedelta(hours=int(source.get("window_h", DEFAULT_WINDOW_H)))

    def fetch(self) -> list[dict[str, str]]:
        """Detecções da janela. O arquivo é por dia UTC: perto da meia-noite precisa também do dia anterior."""
        now = self._now()
        days = [now]
        if now - self._window < now.replace(hour=0, minute=0, second=0, microsecond=0):
            days.insert(0, now - timedelta(days=1))
        rows: list[dict[str, str]] = []
        errors: list[Exception] = []
        for day in days:
            try:
                text = self._fetch(_day_url(self.source["url"], day)).decode("utf-8", errors="replace")
            except Exception as exc:  # noqa: BLE001 - o arquivo do dia pode ainda não existir logo após 00:00Z
                errors.append(exc)
                continue
            rows += list(csv.DictReader(io.StringIO(text)))
        if not rows and errors:
            raise errors[-1]
        return rows

    def _parse(self, raw: dict[str, str]) -> tuple[datetime, str, str, str, float, float, float] | None:
        try:
            t = datetime.strptime(raw["data_hora_gmt"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            uf = uf_from_state_name(raw["estado"])
            frp = float(raw["frp"]) if raw.get("frp") else 0.0
            return t, uf or "", raw.get("municipio", ""), raw.get("bioma", ""), float(raw["lat"]), float(raw["lon"]), frp
        except (KeyError, ValueError, TypeError):  # linha malformada (colunas faltando vira None no csv)
            return None

    def run(self) -> list[Signal]:
        now = self._now()
        start = now - self._window
        by_uf: dict[str, list[tuple]] = {}
        for raw in self.fetch():
            p = self._parse(raw)
            if p and p[1] and start < p[0] <= now:
                by_uf.setdefault(p[1], []).append(p)
        out: list[Signal] = []
        hours = int(self._window.total_seconds() // 3600)
        for uf, dets in sorted(by_uf.items()):
            if len(dets) < self._min:
                continue
            newest = max(d[0] for d in dets)
            towns = Counter(d[2] for d in dets).most_common(3)
            biome = Counter(d[3] for d in dets if d[3]).most_common(1)
            frp = sum(d[6] for d in dets)
            place = state_place(uf, confidence=60)
            lat = sum(d[4] for d in dets) / len(dets)
            lon = sum(d[5] for d in dets) / len(dets)
            name = raw_state_name(uf)
            title = clean_text(f"Focos de queimada em {name}: {len(dets)} detecções por satélite em {hours} h (INPE)", 300)
            text = clean_text("Maior concentração: " + ", ".join(f"{t.title()} ({n})" for t, n in towns)
                              + (f". Bioma principal: {biome[0][0]}" if biome else "")
                              + f". Potência radiativa somada: {frp:,.0f} MW. Cada foco é uma detecção de calor por satélite.", 500)
            # Um sinal por UF por janela de `window_h` horas (hash estável): a contagem sobe durante a janela, mas
            # reescrever o sinal a cada ciclo estouraria o orçamento de escrita do banco.
            bucket = int(newest.timestamp() // self._window.total_seconds())
            digest = content_hash(f"{PORTAL}?uf={uf}&janela={bucket}", f"focos-{uf}")
            out.append(Signal(
                signal_id=f"sig-{digest}", source_id=self.source_id, source_class=self.source_class,  # type: ignore[arg-type]
                timestamp=min(newest, now), collected_at=now, title=title, text=text, url=f"{PORTAL}?uf={uf}",
                category="WEATHER", latitude=lat, longitude=lon, geo_precision="STATE",
                geo_confidence=place.confidence if place else 60, reliability=RELIABILITY.get(self.source_class, 90),
                hash=digest, canonical_url=f"{PORTAL}?uf={uf}", state=uf,
            ))
        return out


def raw_state_name(uf: str) -> str:
    from ...processing.geo import _STATES  # tabela (uf, nome, ...) já usada na geolocalização
    return next((s[1] for s in _STATES if s[0] == uf), uf)
