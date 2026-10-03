"""Cliente do Worker (POST /api/ingest). O token vem do ambiente; nunca do código."""
from __future__ import annotations

import json
import os
import urllib.request


def fetch_history(hours: int = 48, base_url: str | None = None, token: str | None = None) -> list[dict]:
    """Histórico de contagens (rota interna do Worker). Falha de rede => lista vazia: o ciclo segue sem baseline."""
    base_url = base_url or os.environ.get("PULSO_API_URL", "http://localhost:8787")
    token = token or os.environ.get("PULSO_INGEST_TOKEN")
    if not token:
        return []
    req = urllib.request.Request(
        f"{base_url}/api/admin/series?hours={hours}",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "pulso-engine/0.1 (+https://github.com/henriquesouza1832001-eng/Pulso)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            return json.loads(resp.read()).get("series", [])
    except Exception:  # noqa: BLE001 - histórico é opcional
        return []


def fetch_signals(hours: int = 24, base_url: str | None = None, token: str | None = None) -> list[dict]:
    """Sinais já gravados (para agrupar com estado). Falha de rede => lista vazia: o ciclo segue sem estado."""
    base_url = base_url or os.environ.get("PULSO_API_URL", "http://localhost:8787")
    token = token or os.environ.get("PULSO_INGEST_TOKEN")
    if not token:
        return []
    req = urllib.request.Request(
        f"{base_url}/api/admin/signals?hours={hours}",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "pulso-engine/0.1 (+https://github.com/henriquesouza1832001-eng/Pulso)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
            return json.loads(resp.read()).get("signals", [])
    except Exception:  # noqa: BLE001 - o estado é opcional
        return []


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
