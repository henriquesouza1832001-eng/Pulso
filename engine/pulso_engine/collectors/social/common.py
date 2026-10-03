"""HTTP e normalização mínima para sensores sociais autorizados."""
from __future__ import annotations
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any
from ...models import Signal
from ...processing.geo import locate
from ...processing.keyword_engine import KeywordEngine
from ...processing.normalizer import clean_text, content_hash
USER_AGENT = "pulso-engine/0.1 (+https://github.com/henriquesouza1832001-eng/Pulso)"
MAX_BYTES = 5_000_000
_URL = re.compile(r"https?://\S+")
_MENTION = re.compile(r"(?<!\w)@\w{1,30}")


class SocialAPIError(Exception):
    """Erro HTTP da API social, já mapeado para o estado de saúde do protocolo (§5)."""

    def __init__(self, status: int):
        self.status = status
        # 429 → pausa até a próxima janela; 401/403 → alerta humano, não insistir.
        self.health_status = "RATE_LIMITED" if status == 429 else "AUTH_ERROR" if status in (401, 403) else "OFFLINE"
        super().__init__(f"API social respondeu HTTP {status}")


def request_json(url: str, headers: dict[str, str], data: bytes | None = None) -> dict[str, Any]:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, **headers})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            body = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise SocialAPIError(exc.code) from None  # nunca incluir URL, corpo ou token no log
    if len(body) > MAX_BYTES:
        raise ValueError("resposta social excede 5 MB")
    result = json.loads(body)
    if not isinstance(result, dict):
        raise ValueError("resposta social inválida")
    return result

def credential(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"credencial {name} não configurada")
    return value

def social_signal(source: dict, keywords: KeywordEngine, now: datetime, *,
                  item_id: str, title: str, url: str, timestamp: datetime) -> Signal | None:
    # Links e @menções saem: não guardamos identificadores de pessoas privadas.
    title = clean_text(_MENTION.sub("@usuário", _URL.sub(" ", title or "")), 300)
    if not item_id or not title or not timestamp.tzinfo or not url.startswith("https://"):
        return None
    category = keywords.classify(title) or "OTHER"
    allowed = source.get("categories")
    if allowed and category not in allowed:
        return None  # sensor temático: fora do tema é ruído, não sinal
    timestamp = min(timestamp.astimezone(timezone.utc), now)
    place = locate(title)
    # Não armazenar autoria, texto integral, métricas de perfil ou dados de usuários.
    digest = content_hash(url, title)
    return Signal(
        signal_id=f"sig-{digest}", source_id=source["id"], source_class="SOCIAL",
        timestamp=timestamp, collected_at=now, title=title, url=url,
        category=category, reliability=25,  # type: ignore[arg-type]
        latitude=place.lat if place else None, longitude=place.lon if place else None,
        geo_precision=place.precision if place else None,  # type: ignore[arg-type]
        geo_confidence=place.confidence if place else None,
        state=place.uf if place else None, city=place.city if place else None,
        hash=digest, canonical_url=url,
    )
