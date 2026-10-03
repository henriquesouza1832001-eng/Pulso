"Piloto X: busca recente via API v2 oficial, só mediante plano e permissão de uso."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import urlencode
from .common import credential, request_json, social_signal
from ...processing.keyword_engine import KeywordEngine
class XAdapter:
    def __init__(self, source: dict, keywords: KeywordEngine | None = None,
                 fetcher: Callable[..., dict] | None = None,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self.source, self.keywords = source, keywords or KeywordEngine()
        self.fetcher, self.now = fetcher or request_json, now
    def run(self) -> list:
        token = credential("X_BEARER_TOKEN")
        query = self.source["query"]
        if not isinstance(query, str) or not 1 <= len(query) <= 512:
            raise ValueError("consulta X inválida")
        # Só o intervalo desde a rodada anterior: cada post lido é cobrado, não relemos o mesmo.
        window = min(int(self.source.get("interval_s", 900)), 6 * 24 * 3600)
        start = (self.now() - timedelta(seconds=window)).strftime("%Y-%m-%dT%H:%M:%SZ")
        params = urlencode({"query": query, "max_results": 10, "tweet.fields": "created_at", "start_time": start})
        data = self.fetcher(f"https://api.x.com/2/tweets/search/recent?{params}",
                            {"Authorization": f"Bearer {token}"})
        signals = []
        for raw in data.get("data", []):
            post_id = raw.get("id")
            if not isinstance(post_id, str) or not post_id.isdigit():
                continue
            try:
                ts = datetime.fromisoformat(raw["created_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
            except (KeyError, ValueError, AttributeError):
                continue
            sig = social_signal(self.source, self.keywords, self.now(), item_id=post_id,
                                title=raw.get("text", ""), url=f"https://x.com/i/status/{post_id}", timestamp=ts)
            if sig:
                signals.append(sig)
        return signals
