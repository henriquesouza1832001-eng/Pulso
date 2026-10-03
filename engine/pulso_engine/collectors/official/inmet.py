"""Avisos meteorológicos ativos do INMET (API pública de avisos; licença: reprodução citando a fonte).

Um aviso cobre vários estados: vira UM sinal por UF, para cada estado aparecer no mapa.
Só entra o que é impactante: severidade mínima configurável (`min_severity`, padrão "Perigo").
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from ...models import Signal
from ...processing.geo import state_place, uf_from_state_name
from ...processing.keyword_engine import KeywordEngine
from ...processing.normalizer import clean_text, content_hash
from ..news.rss import http_fetch

# Graus oficiais do INMET (padrão CAP), do menor para o maior.
SEVERITIES = ("Perigo Potencial", "Perigo", "Grande Perigo")
# Severidade do evento vem da categoria (events.BASE_SEVERITY): "Grande Perigo" = risco de grandes danos.
CATEGORY_BY_SEVERITY = {"Perigo Potencial": "WEATHER", "Perigo": "WEATHER", "Grande Perigo": "EMERGENCY"}
BRT = timezone(timedelta(hours=-3))  # horários da API em hora de Brasília


def _parse_local(value: Any) -> datetime | None:
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M").replace(tzinfo=BRT).astimezone(timezone.utc)
    except ValueError:
        return None


class InmetAdapter:
    def __init__(self, source: dict, keywords: KeywordEngine | None = None,
                 fetcher: Callable[[str], bytes] | None = None,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self.source, self.fetcher, self.now = source, fetcher or http_fetch, now
        floor = source.get("min_severity", "Perigo")
        if floor not in SEVERITIES:
            raise ValueError("min_severity inválida")
        self.allowed = set(SEVERITIES[SEVERITIES.index(floor):])

    def run(self) -> list[Signal]:
        data = json.loads(self.fetcher(self.source["url"]))
        now = self.now()
        signals: list[Signal] = []
        # Só "hoje" (avisos vigentes); "futuro" ainda não aconteceu e não vira sinal de evento.
        for alert in data.get("hoje", []) if isinstance(data, dict) else []:
            signals.extend(self.normalize(alert, now))
        return signals

    def normalize(self, alert: dict[str, Any], now: datetime) -> list[Signal]:
        severity, kind, alert_id = alert.get("severidade"), clean_text(alert.get("descricao"), 80), alert.get("id")
        start, end = _parse_local(alert.get("inicio")), _parse_local(alert.get("fim"))
        if severity not in self.allowed or not kind or not isinstance(alert_id, int) or alert.get("encerrado"):
            return []
        if not start or (end and end < now):
            return []  # aviso vencido não é sinal atual
        risks = alert.get("riscos") or []
        text = clean_text(risks[0] if risks and isinstance(risks[0], str) else "", 500) or None
        url = f"https://apiprevmet3.inmet.gov.br/avisos/rss/{alert_id}"
        out = []
        for name in str(alert.get("estados") or "").split(","):
            uf = uf_from_state_name(name)
            place = state_place(uf, confidence=70) if uf else None
            if not place:
                continue
            title = f"INMET: aviso de {kind.lower()} ({severity}) em {name.strip()}"
            digest = content_hash(f"{url}#{uf}", title)  # mesmo aviso, um sinal por UF
            out.append(Signal(
                signal_id=f"sig-{digest}", source_id=self.source["id"], source_class="OFFICIAL",
                timestamp=min(start, now), collected_at=now, title=title, text=text, url=url,
                category=CATEGORY_BY_SEVERITY[severity],  # type: ignore[arg-type]
                latitude=place.lat, longitude=place.lon, geo_precision="STATE", geo_confidence=place.confidence,
                reliability=90, hash=digest, canonical_url=url, state=uf,
            ))
        return out
