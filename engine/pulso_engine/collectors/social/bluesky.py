"""Bluesky: busca de posts pela API oficial (AT Protocol) com conta + senha de app. NUNCA ativar sem a conta e a revisão.

Fluxo: `com.atproto.server.createSession` (handle + senha de app) -> `accessJwt`; depois `app.bsky.feed.searchPosts` por
termo, só posts em português, mais recentes primeiro, desde o início da janela. A busca do Bluesky não tem OR: o sensor
traz uma LISTA de consultas (`queries`), uma requisição por termo (até MAX_QUERIES), com os posts deduplicados.
Privacidade: o link do post usa o DID da conta (identificador opaco), nunca o @ legível; autor, texto integral e métricas
não são guardados (`social_signal`). Rede social detecta, nunca confirma: classe SOCIAL, confiabilidade baixa.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import urlencode

from ...processing.keyword_engine import KeywordEngine
from .common import credential, request_json, social_signal

DEFAULT_HOST = "https://bsky.social"
MAX_QUERIES = 8
PER_QUERY = 25
_DID = re.compile(r"^did:(plc|web):[A-Za-z0-9._:%-]{4,200}$")
_RKEY = re.compile(r"^[A-Za-z0-9._~:-]{1,512}$")


def parse_uri(uri: object) -> tuple[str, str] | None:
    """'at://did:plc:abc.../app.bsky.feed.post/3kxyz' -> (did, rkey); None se não for um post válido."""
    if not isinstance(uri, str) or not uri.startswith("at://"):
        return None
    parts = uri[5:].split("/")
    if len(parts) != 3 or parts[1] != "app.bsky.feed.post" or not _DID.match(parts[0]) or not _RKEY.match(parts[2]):
        return None
    return parts[0], parts[2]


class BlueskyAdapter:
    def __init__(self, source: dict, keywords: KeywordEngine | None = None,
                 fetcher: Callable[..., dict] | None = None,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self.source, self.keywords = source, keywords or KeywordEngine()
        self.fetcher, self.now = fetcher or request_json, now

    def run(self) -> list:
        handle, password = credential("BLUESKY_HANDLE"), credential("BLUESKY_APP_PASSWORD")
        host = (os.environ.get("BLUESKY_PDS") or DEFAULT_HOST).rstrip("/")
        if not host.startswith("https://"):
            raise ValueError("BLUESKY_PDS precisa ser https")
        queries = self.source.get("queries")
        if not isinstance(queries, list) or not queries or not all(isinstance(q, str) and 1 <= len(q) <= 200 for q in queries):
            raise ValueError("consultas Bluesky inválidas")
        session = self.fetcher(f"{host}/xrpc/com.atproto.server.createSession", {"Content-Type": "application/json"},
                               json.dumps({"identifier": handle, "password": password}).encode())
        jwt = session.get("accessJwt")
        if not isinstance(jwt, str) or not jwt:
            raise ValueError("Bluesky não forneceu token de acesso")
        # Só desde a rodada anterior (e no máximo 6 h): não relemos o mesmo post a cada ciclo.
        window = min(int(self.source.get("interval_s", 900)) * 2, 6 * 3600)
        since = (self.now() - timedelta(seconds=window)).strftime("%Y-%m-%dT%H:%M:%SZ")
        seen: set[str] = set()
        signals = []
        for q in queries[:MAX_QUERIES]:
            params = urlencode({"q": q, "lang": "pt", "sort": "latest", "limit": PER_QUERY, "since": since})
            data = self.fetcher(f"{host}/xrpc/app.bsky.feed.searchPosts?{params}", {"Authorization": f"Bearer {jwt}"})
            for post in data.get("posts", []):
                ids = parse_uri(post.get("uri"))
                record = post.get("record") if isinstance(post.get("record"), dict) else {}
                if ids is None or ids in seen or (record.get("langs") and "pt" not in record["langs"]):
                    continue
                labels = post.get("labels") or []
                if labels:  # conteúdo marcado pela moderação do Bluesky (adulto, spam...): descartado
                    continue
                try:
                    ts = datetime.fromisoformat(str(record["createdAt"]).replace("Z", "+00:00"))
                except (KeyError, ValueError):
                    continue
                if not ts.tzinfo:
                    continue
                seen.add(ids)
                did, rkey = ids
                sig = social_signal(self.source, self.keywords, self.now(), item_id=rkey, title=str(record.get("text", "")),
                                    url=f"https://bsky.app/profile/{did}/post/{rkey}", timestamp=ts)
                if sig:
                    signals.append(sig)
        return signals
