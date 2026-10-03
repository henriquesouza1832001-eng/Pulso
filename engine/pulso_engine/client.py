"""Cliente do Worker (POST /api/ingest). O token vem do ambiente; nunca do código."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request


RETRY_STATUS = frozenset({500, 502, 503, 504})  # o Worker/Cloudflare trocando de versão ou sobrecarregado
RETRY_BACKOFF_S = (2.0, 5.0)
USER_AGENT = "pulso-engine/0.1 (+https://github.com/henriquesouza1832001-eng/Pulso)"


class WorkerUnavailable(RuntimeError):
    """O Worker não respondeu (rede, timeout, 5xx) depois das tentativas."""


class WorkerAuthError(RuntimeError):
    """Token ausente ou recusado (401/403): configuração errada, não adianta repetir."""


def _read_json(url: str, token: str, timeout: int, attempts: int = 2) -> dict:
    """GET autenticado com uma nova tentativa em falha transitória."""
    for attempt in range(attempts):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - URL de configuração do projeto
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise WorkerAuthError(f"Worker recusou o token (HTTP {exc.code})") from None
            if exc.code in RETRY_STATUS and attempt < attempts - 1:
                time.sleep(RETRY_BACKOFF_S[0])
                continue
            raise WorkerUnavailable(f"HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as exc:
            if attempt < attempts - 1:
                time.sleep(RETRY_BACKOFF_S[0])
                continue
            raise WorkerUnavailable(f"{type(exc).__name__}: {exc}") from None
    raise AssertionError("inalcançável")  # pragma: no cover


def _get_json(path: str, key: str, base_url: str | None, token: str | None, strict: bool = False, timeout: int = 20) -> list[dict]:
    """Lê uma lista do Worker. `strict=False` (dado opcional): qualquer falha vira lista vazia e o ciclo segue sem ele.
    `strict=True` (dado de que depende não reenviar tudo): a falha sobe, para o ciclo NÃO tratar 'Worker fora do ar' como
    'banco vazio' (o que recriaria e reenviaria todos os sinais e eventos)."""
    base_url = base_url or os.environ.get("PULSO_API_URL", "http://localhost:8787")
    token = token or os.environ.get("PULSO_INGEST_TOKEN")
    if not token:
        if strict:
            raise WorkerAuthError("PULSO_INGEST_TOKEN não definido (use variável de ambiente, nunca o Git).")
        return []
    try:
        return _read_json(f"{base_url}{path}", token, timeout).get(key, [])
    except (WorkerUnavailable, WorkerAuthError):
        if strict:
            raise
        return []


def fetch_history(hours: int = 48, base_url: str | None = None, token: str | None = None, strict: bool = False) -> list[dict]:
    """Histórico de contagens (baseline). Opcional: sem ele a anomalia vale 0 e não há previsão."""
    return _get_json(f"/api/admin/series?hours={hours}", "series", base_url, token, strict, timeout=30)


def fetch_signals(hours: int = 24, base_url: str | None = None, token: str | None = None, strict: bool = False) -> list[dict]:
    """Sinais já gravados (agrupar com estado e não reenviar o que já está lá)."""
    return _get_json(f"/api/admin/signals?hours={hours}", "signals", base_url, token, strict, timeout=30)


def fetch_pulse_history(scope: str = "BR", hours: int = 72, base_url: str | None = None, token: str | None = None) -> list[dict]:
    return _get_json(f"/api/admin/pulse-history?scope={scope}&hours={hours}", "points", base_url, token)


def fetch_observations(hours: int = 24 * 28, limit: int = 30000, base_url: str | None = None, token: str | None = None) -> list[dict]:
    """Histórico agregado por hora (base do baseline sazonal do Sentinela). Mais novas primeiro; o teto poupa leitura do banco."""
    return _get_json(f"/api/admin/observations?hours={hours}&limit={limit}", "observations", base_url, token, timeout=45)


def fetch_active_investigations(base_url: str | None = None, token: str | None = None) -> list[dict]:
    """Investigações do Sentinela ainda não encerradas (para não pesquisar de novo a mesma coisa)."""
    return _get_json("/api/admin/investigations?status=active", "investigations", base_url, token)


def fetch_open_forecasts(base_url: str | None = None, token: str | None = None) -> list[dict]:
    return _get_json("/api/admin/forecasts/open", "forecasts", base_url, token)




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


def fetch_event_digest(hours: int = 24, base_url: str | None = None, token: str | None = None, strict: bool = False) -> list[dict]:
    """Resumo dos eventos já gravados: o Engine só reenvia o que é novo ou mudou (limite de escrita do D1)."""
    return _get_json(f"/api/admin/events-digest?hours={hours}", "events", base_url, token, strict)

