"""Coletor do X (Twitter) pela API v2 OFICIAL (busca recente). Sem raspagem, sem login por navegador.

Exige o secret `X_BEARER_TOKEN` (plano pago do X; ver docs/sources/SOURCES.md). Só entram sinais de
IMPORTÂNCIA (desastre, vítimas, emergência): fofoca e entretenimento são descartados em `normalize`.
Rede social detecta, nunca confirma sozinha: a classe é SOCIAL (ou SOCIAL_VERIFIED para conta verificada).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable

from ...models import Signal
from ...processing.geo import locate
from ...processing.importance import DEFAULT_THRESHOLD, assess, brazil_relevant
from ...processing.keyword_engine import KeywordEngine
from ...processing.normalizer import canonical_url, clean_text, content_hash
from ..news.rss import RELIABILITY, USER_AGENT, http_fetch

SEARCH_URL = "https://api.x.com/2/tweets/search/recent"
MAX_BYTES = 5_000_000
# Consulta padrão: termos de impacto, em português, sem retweets e sem respostas (menos duplicata e ruído).
DEFAULT_QUERY = (
    '(enchente OR alagamento OR deslizamento OR desabamento OR incêndio OR tornado OR ciclone OR terremoto '
    'OR "defesa civil" OR apagão OR surto OR evacuação OR tiroteio OR mortos OR vítimas) '
    "lang:pt -is:retweet -is:reply"
)


class XAuthError(RuntimeError):
    pass


def x_fetch(url: str) -> bytes:
    token = os.environ.get("X_BEARER_TOKEN", "").strip()
    if not token:
        raise XAuthError("X_BEARER_TOKEN ausente (secret não configurado)")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - host fixo (api.x.com)
            data = resp.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise XAuthError(f"AUTH_ERROR HTTP {exc.code}: não insistir; checar plano/token") from exc
        if exc.code == 429:
            raise RuntimeError("RATE_LIMITED HTTP 429: pausar até o reset") from exc
        raise
    if len(data) > MAX_BYTES:
        raise ValueError("resposta excede o tamanho máximo")
    return data


class XAdapter:
    adapter = "x"

    def __init__(
        self,
        source: dict[str, Any],
        keywords: KeywordEngine | None = None,
        fetcher: Callable[[str], bytes] = http_fetch,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.source = source
        self.source_id: str = source["id"]
        self.source_class: str = source["source_class"]
        self._keywords = keywords or KeywordEngine()
        # O pipeline injeta o fetcher do RSS (sem autenticação); para o X usamos o fetch com Bearer.
        self._fetch = x_fetch if fetcher is http_fetch else fetcher
        self._now = now
        self._threshold = int(source.get("min_importance", DEFAULT_THRESHOLD))

    def _url(self) -> str:
        params = {
            "query": self.source.get("query", DEFAULT_QUERY),
            "max_results": str(min(max(int(self.source.get("max_results", 50)), 10), 100)),
            "tweet.fields": "created_at,lang,author_id",
            "expansions": "author_id",
            "user.fields": "verified,username",
        }
        return f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"

    def fetch(self) -> list[dict[str, Any]]:
        body = json.loads(self._fetch(self._url()))
        users = {u["id"]: u for u in body.get("includes", {}).get("users", [])}
        out: list[dict[str, Any]] = []
        for t in body.get("data", []):
            out.append({**t, "_user": users.get(t.get("author_id"), {})})
        return out

    def normalize(self, raw: dict[str, Any]) -> Signal | None:
        text = clean_text(raw.get("text"), 500)
        tweet_id = raw.get("id")
        if not text or not tweet_id:
            return None
        if assess(text).score < self._threshold:
            return None  # fofoca/entretenimento ou impacto insuficiente: não entra no motor
        now = self._now()
        try:
            ts = datetime.fromisoformat(str(raw.get("created_at")).replace("Z", "+00:00"))
        except ValueError:
            ts = now
        ts = min(ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc), now)
        user = raw.get("_user", {})
        verified = bool(user.get("verified"))
        cls = "SOCIAL_VERIFIED" if verified else self.source_class
        url = canonical_url(f"https://x.com/i/web/status/{tweet_id}")
        title = text[:300]
        place = locate(text)
        if not brazil_relevant(text, place is not None):
            return None  # fora do escopo (outro país)
        digest = content_hash(url, title)
        return Signal(
            signal_id=f"sig-{digest}", source_id=self.source_id, source_class=cls,  # type: ignore[arg-type]
            timestamp=ts, collected_at=now, title=title, text=text, url=url,
            category=self._keywords.classify(text) or "OTHER",  # type: ignore[arg-type]
            latitude=place.lat if place else None, longitude=place.lon if place else None,
            geo_precision=place.precision if place else None,  # type: ignore[arg-type]
            geo_confidence=place.confidence if place else None,
            reliability=RELIABILITY.get(cls, 25), hash=digest, canonical_url=url,
            # Sem perfil individual: só guardamos o @ de contas verificadas (veículos, órgãos).
            author=user.get("username") if verified else None,
            state=place.uf if place else None, city=place.city if place else None,
        )

    def validate(self, signal: Signal) -> bool:
        return bool(signal.title.strip()) and signal.timestamp.tzinfo is not None

    def score_reliability(self, signal: Signal | None) -> int:
        return RELIABILITY.get(self.source_class, 25)

    def run(self) -> list[Signal]:
        out: list[Signal] = []
        for raw in self.fetch():
            sig = self.normalize(raw)
            if sig is not None and self.validate(sig):
                out.append(sig)
        return out
