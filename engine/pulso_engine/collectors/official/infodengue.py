"""InfoDengue (Fiocruz/FGV): alerta semanal de dengue por município (API aberta, sem chave).

Cobre as 27 capitais. Um sinal por capital quando o nível do alerta da semana mais recente é >= `min_level`
(1 verde, 2 amarelo, 3 laranja, 4 vermelho; padrão 3). O nível é um alerta de transmissão modelado, não uma contagem
oficial de casos confirmados: o texto diz "estimados". Dado semanal: o sinal descreve a situação ATUAL (timestamp = agora)
e tem hash estável por (município, semana, nível), então reaparece no máximo uma vez por dia no banco.
Citar a fonte (InfoDengue) é condição de uso.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

from ...models import Signal
from ...processing.geo import locate, state_place
from ...processing.keyword_engine import KeywordEngine
from ...processing.normalizer import clean_text, content_hash
from ..news.rss import RELIABILITY, http_fetch

API = "https://info.dengue.mat.br/api/alertcity"
PORTAL = "https://info.dengue.mat.br/"
LEVEL_NAME = {1: "verde", 2: "amarelo", 3: "laranja", 4: "vermelho"}
# UF -> (capital, geocódigo IBGE de 7 dígitos). Os 27 códigos foram conferidos contra o `municipio_nome` da API.
CAPITALS: dict[str, tuple[str, int]] = {
    "AC": ("Rio Branco", 1200401), "AL": ("Maceió", 2704302), "AP": ("Macapá", 1600303), "AM": ("Manaus", 1302603),
    "BA": ("Salvador", 2927408), "CE": ("Fortaleza", 2304400), "DF": ("Brasília", 5300108), "ES": ("Vitória", 3205309),
    "GO": ("Goiânia", 5208707), "MA": ("São Luís", 2111300), "MT": ("Cuiabá", 5103403), "MS": ("Campo Grande", 5002704),
    "MG": ("Belo Horizonte", 3106200), "PA": ("Belém", 1501402), "PB": ("João Pessoa", 2507507), "PR": ("Curitiba", 4106902),
    "PE": ("Recife", 2611606), "PI": ("Teresina", 2211001), "RJ": ("Rio de Janeiro", 3304557), "RN": ("Natal", 2408102),
    "RS": ("Porto Alegre", 4314902), "RO": ("Porto Velho", 1100205), "RR": ("Boa Vista", 1400100),
    "SC": ("Florianópolis", 4205407), "SP": ("São Paulo", 3550308), "SE": ("Aracaju", 2800308), "TO": ("Palmas", 1721000),
}


class InfoDengueAdapter:
    adapter = "infodengue"

    def __init__(self, source: dict[str, Any], keywords: KeywordEngine | None = None,
                 fetcher: Callable[[str], bytes] = http_fetch,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self.source = source
        self.source_id: str = source["id"]
        self.source_class: str = source["source_class"]
        self._fetch = fetcher
        self._now = now
        self._min_level = int(source.get("min_level", 3))
        self._disease = source.get("disease", "dengue")

    def _url(self, code: int) -> str:
        year = self._now().year
        return (f"{API}?geocode={code}&disease={self._disease}&format=json"
                f"&ew_start=1&ew_end=53&ey_start={year}&ey_end={year}")

    def fetch(self) -> dict[str, list[dict[str, Any]]]:
        """Linhas semanais por UF. Uma capital que falha não derruba as outras (a falha de TODAS vira erro)."""
        out: dict[str, list[dict[str, Any]]] = {}
        errors: list[Exception] = []
        for uf, (_, code) in CAPITALS.items():
            try:
                rows = json.loads(self._fetch(self._url(code)))
                if not isinstance(rows, list):  # a API devolve um objeto {"error": ...} quando algo falha
                    raise ValueError(f"resposta inesperada para {uf}")
                out[uf] = [r for r in rows if isinstance(r, dict)]
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
        if not out and errors:
            raise errors[-1]
        return out

    def normalize(self, uf: str, rows: list[dict[str, Any]]) -> Signal | None:
        city, _ = CAPITALS[uf]
        valid = [r for r in rows if isinstance(r.get("SE"), int) and isinstance(r.get("nivel"), int)]
        if not valid:
            return None
        row = max(valid, key=lambda r: r["SE"])
        level = row["nivel"]
        if level < self._min_level:
            return None
        week = row["SE"] % 100
        name = LEVEL_NAME.get(level, str(level))
        now = self._now()
        title = clean_text(f"Dengue: alerta {name} em {city}/{uf} (semana epidemiológica {week})", 300)
        est, lo, hi = row.get("casos_est"), row.get("casos_est_min"), row.get("casos_est_max")
        parts = []
        if est is not None:
            parts.append(f"Casos estimados na semana: {est:.0f}" + (f" (intervalo {lo}–{hi})" if lo is not None and hi is not None else ""))
        if row.get("p_inc100k") is not None:
            parts.append(f"incidência de {row['p_inc100k']:.1f} por 100 mil habitantes")
        if row.get("Rt") is not None:
            parts.append(f"Rt {row['Rt']:.2f}")
        text = clean_text("; ".join(parts) + f". Nível {level} ({name}) do InfoDengue (Fiocruz/FGV): alerta modelado, não contagem confirmada.", 500)
        place = locate(f"{city}, {uf}") or state_place(uf, confidence=70)
        digest = content_hash(f"{PORTAL}?geocode={CAPITALS[uf][1]}&se={row['SE']}&nivel={level}", f"dengue-{uf}-{row['SE']}-{level}")
        return Signal(
            signal_id=f"sig-{digest}", source_id=self.source_id, source_class=self.source_class,  # type: ignore[arg-type]
            timestamp=now, collected_at=now, title=title, text=text, url=PORTAL, category="HEALTH",
            latitude=place.lat if place else None, longitude=place.lon if place else None,
            geo_precision=place.precision if place else None,  # type: ignore[arg-type]
            geo_confidence=place.confidence if place else None, reliability=RELIABILITY.get(self.source_class, 90),
            hash=digest, canonical_url=PORTAL, state=uf, city=city,
        )

    def run(self) -> list[Signal]:
        sigs = (self.normalize(uf, rows) for uf, rows in self.fetch().items())
        return [s for s in sigs if s is not None]
