"""Banco Central (Olinda/PTAX): cotação do dólar. Sinal só em choque cambial (|variação| >= `min_pct`).

O dólar mexe com preços (combustível, alimentos, viagens) e é um dos indicadores que o brasileiro mais sente.
Fonte OFICIAL, serviço aberto de dados do Banco Central; citar a fonte. Em dia calmo não emite nada (e isso é normal:
a fonte é marcada `quiet_ok` para não aparecer como DEGRADED).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from ...models import Signal
from ...processing.keyword_engine import KeywordEngine
from ...processing.normalizer import clean_text, content_hash
from ..news.rss import RELIABILITY, http_fetch

BRT = timezone(timedelta(hours=-3))
DEFAULT_MIN_PCT = 1.0
MAX_QUOTE_AGE = timedelta(hours=48)
PORTAL = "https://www.bcb.gov.br/estabilidadefinanceira/historicocotacoes"


def _br(n: float, nd: int = 2) -> str:
    return f"{n:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")


class BcbPtaxAdapter:
    adapter = "bcb_ptax"

    def __init__(self, source: dict[str, Any], keywords: KeywordEngine | None = None,
                 fetcher: Callable[[str], bytes] = http_fetch,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self.source = source
        self.source_id: str = source["id"]
        self.source_class: str = source["source_class"]
        self._fetch = fetcher
        self._now = now
        self._min_pct = float(source.get("min_pct", DEFAULT_MIN_PCT))

    def _url(self) -> str:
        now = self._now().astimezone(BRT)
        start = (now - timedelta(days=10)).strftime("%m-%d-%Y")
        end = now.strftime("%m-%d-%Y")
        return (f"{self.source['url'].rstrip('/')}(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
                f"?@dataInicial='{start}'&@dataFinalCotacao='{end}'&$orderby=dataHoraCotacao%20desc&$top=10&$format=json")

    def fetch(self) -> list[dict[str, Any]]:
        return list(json.loads(self._fetch(self._url())).get("value", []))

    def run(self) -> list[Signal]:
        quotes = []
        for q in self.fetch():
            try:
                t = datetime.strptime(q["dataHoraCotacao"][:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=BRT)
                quotes.append((t, float(q["cotacaoVenda"])))
            except (KeyError, ValueError, TypeError):
                continue
        quotes.sort(reverse=True)
        if len(quotes) < 2:
            return []
        (t_now, last), (_, prev) = quotes[0], quotes[1]
        now = self._now()
        pct = (last / prev - 1) * 100
        if abs(pct) < self._min_pct or now - t_now.astimezone(timezone.utc) > MAX_QUOTE_AGE:
            return []
        verb = "sobe" if pct > 0 else "cai"
        day = t_now.strftime("%d/%m")
        title = clean_text(f"Dólar {verb} {_br(abs(pct), 1)}%: PTAX fecha a R$ {_br(last)} (Banco Central)", 300)
        text = clean_text(f"Cotação de venda PTAX de {day}: R$ {_br(last, 4)}, contra R$ {_br(prev, 4)} no pregão anterior "
                          f"({'+' if pct > 0 else '-'}{_br(abs(pct))}%). Choque cambial: tende a pressionar preços de combustíveis, "
                          "alimentos e viagens.", 500)
        url = f"{PORTAL}?data={t_now.strftime('%Y-%m-%d')}"
        digest = content_hash(url, f"ptax-{t_now.strftime('%Y-%m-%d')}")
        return [Signal(
            signal_id=f"sig-{digest}", source_id=self.source_id, source_class=self.source_class,  # type: ignore[arg-type]
            timestamp=min(t_now.astimezone(timezone.utc), now), collected_at=now, title=title, text=text, url=url,
            category="ECONOMY", reliability=RELIABILITY.get(self.source_class, 90), hash=digest, canonical_url=url,
        )]
