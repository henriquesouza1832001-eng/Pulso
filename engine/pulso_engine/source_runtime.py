"""Estado de execução por fonte (frescor + circuit breaker) e resumo do ciclo, prontos para o Worker (`source_runtime`, `engine_cycle`).

Puro e sem rede: junta o que `source_freshness.py` (frescor, Claude A) e `circuit_breaker.py` (estado do breaker) já decidem, e
decide O QUE VALE ENVIAR. O Actions não tem memória entre ciclos, então o estado anterior (breaker, último avanço de conteúdo)
vem do Worker (`GET /api/admin/source-runtime`) e volta no lote. Escrita econômica: uma linha só vai se algo MUDOU ou no batimento
periódico, nunca todas as fontes a cada ciclo (orçamento de escrita, docs/decisions/0008).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from .circuit_breaker import CLOSED, BreakerState
from .events import iso
from .source_freshness import coverage as freshness_coverage, freshness_percentiles

HEARTBEAT_MIN = 360  # fonte sem mudança de estado reporta no máximo a cada 6 h (prova de vida; os campos valem "em updated_at")
UNAVAILABLE = "UNAVAILABLE"  # frescor não calculado (flag desligada): nunca finge FRESH nem zero

# campos cuja mudança obriga a enviar a linha; contagens e idade mudam todo ciclo e NÃO disparam escrita sozinhas
_STATE_FIELDS = ("transport", "freshness_state", "breaker_state", "consecutive_failures", "opened_count", "next_attempt_at", "breaker_reason")


def parse_iso(v: str | None) -> datetime | None:
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def breaker_from_row(row: dict | None) -> BreakerState:
    """Reconstrói o estado do breaker a partir da linha gravada. Linha ausente ou ilegível = CLOSED (nunca bloqueia por dúvida)."""
    if not row:
        return BreakerState()
    state = row.get("breaker_state")
    if state not in ("CLOSED", "OPEN", "HALF_OPEN"):
        return BreakerState()
    try:
        return BreakerState(state, int(row.get("consecutive_failures") or 0), int(row.get("opened_count") or 0),
                            parse_iso(row.get("next_attempt_at")), row.get("breaker_reason"))
    except (TypeError, ValueError):
        return BreakerState()


def retry_after_seconds(exc: BaseException, now: datetime | None = None) -> float | None:
    """Lê `Retry-After` de um HTTPError (segundos ou data HTTP). Valor inválido/negativo = None (o breaker aplica o próprio backoff)."""
    headers = getattr(exc, "headers", None)
    raw = headers.get("Retry-After") if headers is not None and hasattr(headers, "get") else None
    if not raw:
        return None
    raw = str(raw).strip()
    try:
        secs = float(raw)
    except ValueError:
        try:
            when = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        secs = (when - (now or datetime.now(timezone.utc))).total_seconds()
    return secs if secs > 0 else None


def runtime_row(assessment: dict | None, source_id: str, transport: str, breaker: BreakerState, now: datetime) -> dict:
    """Uma linha no contrato `SourceRuntimeRow`. Sem avaliação de frescor (flag desligada) o estado é UNAVAILABLE, não FRESH."""
    fr = (assessment or {}).get("freshness") or {}
    q = (assessment or {}).get("quality") or {}
    return {
        "source_id": source_id, "transport": transport,
        "freshness_state": fr.get("state", UNAVAILABLE),
        "newest_item_age_min": fr.get("newest_item_age_min"),
        "last_content_advance": fr.get("last_content_advance"),
        "records": int(q.get("records", 0)), "new_records": int(q.get("new_records", 0)), "duplicate_records": int(q.get("duplicate_records", 0)),
        "breaker_state": breaker.state, "consecutive_failures": breaker.consecutive_failures,
        "next_attempt_at": iso(breaker.next_attempt_at) if breaker.next_attempt_at else None,
        "opened_count": breaker.opened_count, "breaker_reason": (breaker.last_reason or None) and str(breaker.last_reason)[:80],
        "updated_at": iso(now),
    }


def select_runtime(rows: list[dict], previous: dict[str, dict], now: datetime, heartbeat_min: int = HEARTBEAT_MIN) -> list[dict]:
    """Só o que vale gravar: fonte nova, estado que mudou, ou batimento vencido. Idêntico e recente = não envia."""
    out = []
    for r in rows:
        prev = previous.get(r["source_id"])
        if prev is None or any(prev.get(k) != r.get(k) for k in _STATE_FIELDS):
            out.append(r)
            continue
        seen = parse_iso(prev.get("updated_at"))
        if seen is None or now - seen >= timedelta(minutes=heartbeat_min):
            out.append(r)
    return out


def cycle_summary(rows: list[dict], assessments: list[dict], families: dict[str, str], *, now: datetime, duration_s: float,
                  sources_due: int, sources_skipped: int, signals_sent: int, events: int, flags: dict[str, bool],
                  engine_ref: str | None = None) -> dict:
    """Resumo do ciclo (contrato `EngineCycle`): contagens, frescor agregado por estado, cobertura por família, idade p50/p95/max."""
    ref = engine_ref or os.environ.get("GITHUB_SHA", "")
    states = {"FRESH": 0, "STALE": 0, "EMPTY": 0, "QUIET": 0, "UNKNOWN": 0}
    for r in rows:
        if r["freshness_state"] in states:
            states[r["freshness_state"]] += 1
    pct = freshness_percentiles(assessments)
    return {
        "cycle_at": iso(now), "duration_s": round(duration_s, 2), "sources_due": sources_due, "sources_skipped": sources_skipped,
        "records": sum(r["records"] for r in rows), "new_records": sum(r["new_records"] for r in rows),
        "duplicate_records": sum(r["duplicate_records"] for r in rows),
        "signals_sent": signals_sent, "events": events,
        "freshness": states, "coverage": freshness_coverage(assessments, families),
        "age": {k: pct[k] for k in ("n", "p50", "p95", "max")},
        "breakers_open": sum(1 for r in rows if r["breaker_state"] != CLOSED),
        "flags": dict(flags),
        "engine_ref": ref[:12] if ref else None,
    }
