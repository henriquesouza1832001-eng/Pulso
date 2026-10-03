"""Cliente do Worker (POST /api/ingest). O token vem do ambiente; nunca do código."""
from __future__ import annotations

import json
import os
import time
import urllib.error
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


def _get_json(path: str, key: str, base_url: str | None, token: str | None) -> list[dict]:
    base_url = base_url or os.environ.get("PULSO_API_URL", "http://localhost:8787")
    token = token or os.environ.get("PULSO_INGEST_TOKEN")
    if not token:
        return []
    req = urllib.request.Request(
        f"{base_url}{path}",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "pulso-engine/0.1 (+https://github.com/henriquesouza1832001-eng/Pulso)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
            return json.loads(resp.read()).get(key, [])
    except Exception:  # noqa: BLE001 - previsões são opcionais: sem dado, o ciclo segue
        return []


def fetch_pulse_history(scope: str = "BR", hours: int = 72, base_url: str | None = None, token: str | None = None) -> list[dict]:
    return _get_json(f"/api/admin/pulse-history?scope={scope}&hours={hours}", "points", base_url, token)


def fetch_open_forecasts(base_url: str | None = None, token: str | None = None) -> list[dict]:
    return _get_json("/api/admin/forecasts/open", "forecasts", base_url, token)


RETRY_STATUS = frozenset({500, 502, 503, 504})  # o Worker/Cloudflare trocando de versão ou sobrecarregado
RETRY_BACKOFF_S = (2.0, 5.0)


class PushError(RuntimeError):
    """O Worker recusou o lote. Traz o motivo (ex.: invalid_batch + campo), que o urllib esconde."""

    def __init__(self, status: int, detail: str):
        self.status, self.detail = status, detail
        super().__init__(f"Worker respondeu HTTP {status}: {detail}")


def push_batch(batch: dict, base_url: str | None = None, token: str | None = None, retries: int = 2) -> dict:
    """Envia um lote. A ingestão é idempotente (upsert), então repetir é seguro: falhas TRANSITÓRIAS (rede, 5xx) têm até
    `retries` novas tentativas; 4xx (lote inválido, token) não são repetidos e mostram o motivo."""
    base_url = base_url or os.environ.get("PULSO_API_URL", "http://localhost:8787")
    token = token or os.environ.get("PULSO_INGEST_TOKEN")
    if not token:
        raise RuntimeError("PULSO_INGEST_TOKEN não definido (use variável de ambiente, nunca o Git).")
    data = json.dumps(batch).encode("utf-8")
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            f"{base_url}/api/ingest", data=data, method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}",
                     "User-Agent": "pulso-engine/0.1 (+https://github.com/henriquesouza1832001-eng/Pulso)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - URL controlada pela configuração
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:300].decode("utf-8", "replace")  # nunca inclui o token (ele só vai no cabeçalho)
            if exc.code in RETRY_STATUS and attempt < retries:
                time.sleep(RETRY_BACKOFF_S[min(attempt, len(RETRY_BACKOFF_S) - 1)])
                continue
            raise PushError(exc.code, detail) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt >= retries:
                raise
            time.sleep(RETRY_BACKOFF_S[min(attempt, len(RETRY_BACKOFF_S) - 1)])
    raise AssertionError("inalcançável")  # pragma: no cover


def fetch_event_digest(hours: int = 24, base_url: str | None = None, token: str | None = None) -> list[dict]:
    """Resumo dos eventos já gravados: o Engine só reenvia o que é novo ou mudou (limite de escrita do D1)."""
    return _get_json(f"/api/admin/events-digest?hours={hours}", "events", base_url, token)

