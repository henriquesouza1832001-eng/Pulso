"""ONS (Operador Nacional do Sistema Elétrico): energia armazenada nos reservatórios (EAR) por subsistema.

Reservatório baixo é o antecedente de bandeira tarifária cara, risco de racionamento e apagão. Fonte OFICIAL, dados
abertos do ONS (CSV anual no S3 do portal). Sinal só quando algum subsistema está abaixo de `min_level` (% da EAR máxima)
ou caiu `min_drop_pp` pontos percentuais em 7 dias; em situação normal não emite nada (`quiet_ok`).
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from ...models import Signal
from ...processing.keyword_engine import KeywordEngine
from ...processing.normalizer import clean_text, content_hash
from ..news.rss import RELIABILITY, http_fetch

BRT = timezone(timedelta(hours=-3))
DEFAULT_MIN_LEVEL = 30.0
DEFAULT_MIN_DROP_PP = 8.0
MAX_DATA_AGE = timedelta(days=5)  # o ONS publica com 1-2 dias de atraso; mais que isso = dado parado, não notícia
PORTAL = "https://dados.ons.org.br/dataset/ear-diario-por-subsistema"
NAMES = {"SE": "Sudeste/Centro-Oeste", "S": "Sul", "NE": "Nordeste", "N": "Norte"}


def _pt(n: float) -> str:
    return f"{n:.1f}".replace(".", ",")


class OnsEarAdapter:
    adapter = "ons_ear"

    def __init__(self, source: dict[str, Any], keywords: KeywordEngine | None = None,
                 fetcher: Callable[[str], bytes] = http_fetch,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self.source = source
        self.source_id: str = source["id"]
        self.source_class: str = source["source_class"]
        self._fetch = fetcher
        self._now = now
        self._min_level = float(source.get("min_level", DEFAULT_MIN_LEVEL))
        self._min_drop = float(source.get("min_drop_pp", DEFAULT_MIN_DROP_PP))

    def _url(self) -> str:
        year = self._now().astimezone(BRT).year
        return self.source["url"].replace("{year}", str(year))

    def fetch(self) -> dict[str, dict[date, float]]:
        """{subsistema: {dia: % da EAR máxima}}."""
        text = self._fetch(self._url()).decode("utf-8-sig", errors="replace")
        out: dict[str, dict[date, float]] = {}
        for r in csv.DictReader(io.StringIO(text), delimiter=";"):
            try:
                sub = r["id_subsistema"].strip()
                out.setdefault(sub, {})[date.fromisoformat(r["ear_data"].strip())] = float(r["ear_verif_subsistema_percentual"])
            except (KeyError, ValueError, AttributeError):
                continue
        return out

    def run(self) -> list[Signal]:
        now = self._now()
        data = self.fetch()
        flagged: list[tuple[str, float, float | None, date]] = []
        for sub, days in data.items():
            if not days:
                continue
            last_day = max(days)
            if now - datetime.combine(last_day, datetime.min.time(), tzinfo=BRT) > MAX_DATA_AGE:
                continue
            level = days[last_day]
            week_ago = days.get(last_day - timedelta(days=7))
            drop = (week_ago - level) if week_ago is not None else None
            if level < self._min_level or (drop is not None and drop >= self._min_drop):
                flagged.append((sub, level, drop, last_day))
        if not flagged:
            return []
        flagged.sort(key=lambda f: f[1])
        day = max(f[3] for f in flagged)
        parts = [f"{NAMES.get(s, s)} {_pt(lv)}%" + (f" (queda de {_pt(d)} p.p. em 7 dias)" if d is not None and d >= self._min_drop else "")
                 for s, lv, d, _ in flagged]
        title = clean_text(f"Reservatórios em alerta: {'; '.join(parts[:3])} da energia armazenada (ONS)", 300)
        text = clean_text(f"Energia armazenada nos reservatórios em {day.strftime('%d/%m')}: {'; '.join(parts)}. Nível baixo ou queda "
                          "rápida pressiona a bandeira tarifária da conta de luz e aumenta o risco de racionamento.", 500)
        digest = content_hash(PORTAL, f"ons-ear-{day.isoformat()}-{','.join(sorted(f[0] for f in flagged))}")
        ts = min(datetime.combine(day, datetime.min.time(), tzinfo=BRT).astimezone(timezone.utc), now)
        return [Signal(
            signal_id=f"sig-{digest}", source_id=self.source_id, source_class=self.source_class,  # type: ignore[arg-type]
            timestamp=ts, collected_at=now, title=title, text=text, url=PORTAL, category="INFRASTRUCTURE",
            reliability=RELIABILITY.get(self.source_class, 90), hash=digest, canonical_url=PORTAL,
        )]
