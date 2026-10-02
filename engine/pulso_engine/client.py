"""Cliente do Worker (POST /api/ingest). O token vem do ambiente; nunca do código."""
from __future__ import annotations

import json
import os
import urllib.request


def push_batch(batch: dict, base_url: str | None = None, token: str | None = None) -> dict:
    base_url = base_url or os.environ.get("PULSO_API_URL", "http://localhost:8787")
    token = token or os.environ.get("PULSO_INGEST_TOKEN")
    if not token:
        raise RuntimeError("PULSO_INGEST_TOKEN não definido (use variável de ambiente, nunca o Git).")
    req = urllib.request.Request(
        f"{base_url}/api/ingest",
        data=json.dumps(batch).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "pulso-engine/0.1 (+https://github.com/henriquesouza1832001-eng/Pulso)",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - URL controlada pela configuração
        return json.loads(resp.read())
