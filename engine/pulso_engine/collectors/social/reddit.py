"""Piloto Reddit: OAuth da API oficial; NUNCA ativar sem aprovação de uso/retenção."""
from __future__ import annotations
import base64
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlencode
from .common import USER_AGENT, credential, request_json, social_signal
from ...processing.keyword_engine import KeywordEngine
_SUBREDDIT = re.compile(r"^[A-Za-z0-9_]{2,21}$")


def subreddit_path(value: object) -> str:
    """'brasil+worldnews' -> 'brasil+worldnews', validando cada comunidade."""
    parts = value.split("+") if isinstance(value, str) else []
    if not parts or not all(_SUBREDDIT.match(p) for p in parts):
        raise ValueError("subreddit inválido")
    return "+".join(parts)


class RedditAdapter:
    def __init__(self, source: dict, keywords: KeywordEngine | None = None,
                 fetcher: Callable[..., dict] | None = None,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self.source, self.keywords = source, keywords or KeywordEngine()
        self.fetcher, self.now = fetcher or request_json, now
    def run(self) -> list:
        client_id, secret = credential("REDDIT_CLIENT_ID"), credential("REDDIT_CLIENT_SECRET")
        # O Reddit exige User-Agent único e descritivo: "<plataforma>:<app>:<versão> (by /u/<conta>)".
        agent = os.environ.get("REDDIT_USER_AGENT") or USER_AGENT
        basic = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
        token = self.fetcher("https://www.reddit.com/api/v1/access_token",
                             {"Authorization": f"Basic {basic}", "User-Agent": agent,
                              "Content-Type": "application/x-www-form-urlencoded"},
                             b"grant_type=client_credentials").get("access_token")
        if not isinstance(token, str) or not token:
            raise ValueError("Reddit não forneceu token OAuth")
        subreddit = subreddit_path(self.source["subreddit"])
        query = self.source.get("query")
        if query:  # busca temática nas comunidades escolhidas, mais recentes primeiro
            if not isinstance(query, str) or len(query) > 512:
                raise ValueError("consulta Reddit inválida")
            url = f"https://oauth.reddit.com/r/{subreddit}/search?" + urlencode(
                {"q": query, "restrict_sr": "on", "sort": "new", "t": "day", "limit": 25})
        else:
            url = f"https://oauth.reddit.com/r/{subreddit}/new?limit=25"
        data = self.fetcher(url, {"Authorization": f"Bearer {token}", "User-Agent": agent})
        signals = []
        for entry in data.get("data", {}).get("children", []):
            raw: dict[str, Any] = entry.get("data", {})
            post_id = raw.get("id")
            if not isinstance(post_id, str) or not post_id.isalnum() or raw.get("removed_by_category") or raw.get("over_18"):
                continue
            try:
                ts = datetime.fromtimestamp(float(raw["created_utc"]), tz=timezone.utc)
            except (ValueError, TypeError, KeyError, OverflowError):
                continue
            sig = social_signal(self.source, self.keywords, self.now(), item_id=post_id,
                                title=raw.get("title", ""), url=f"https://www.reddit.com/comments/{post_id}/",
                                timestamp=ts)
            if sig:
                signals.append(sig)
        return signals
