"""Circuit breaker por fonte: CLOSED -> OPEN -> HALF_OPEN, com backoff exponencial, jitter estável e respeito ao Retry-After.

Puro e determinístico: o estado é um dict pequeno (`BreakerState`) que quem orquestra guarda entre ciclos (o Actions não tem
memória: o estado precisa vir de `source_health`/Worker; ver docs/operations/FAILURE_RUNBOOK.md). Falhas de TRANSPORTE contam
(OFFLINE, RATE_LIMITED, AUTH_ERROR); conteúdo vazio/velho com transporte ok NÃO abre o breaker (é problema de dado, não de rede).
Nunca insiste: aberto = a fonte é PULADA até a hora da próxima tentativa. Não esconde nada: a fonte pulada continua reportando o
último estado e o motivo (`skipped_until`).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

CLOSED, OPEN, HALF_OPEN = "CLOSED", "OPEN", "HALF_OPEN"
FAILURE_THRESHOLD = 3  # falhas de transporte consecutivas para abrir
BASE_OPEN_MIN = 10
MAX_OPEN_MIN = 6 * 60
MAX_RETRY_AFTER_MIN = 24 * 60  # Retry-After absurdo não pode silenciar a fonte por dias
FAIL_STATES = frozenset({"OFFLINE", "RATE_LIMITED", "AUTH_ERROR"})


@dataclass(frozen=True)
class BreakerState:
    state: str = CLOSED
    consecutive_failures: int = 0
    opened_count: int = 0  # quantas aberturas seguidas (expoente do backoff)
    next_attempt_at: datetime | None = None
    last_reason: str | None = None


def _jitter(source_id: str, opened_count: int) -> float:
    """0,85..1,15 estável por fonte e abertura: espalha as retomadas sem aleatoriedade (testável, reproduzível)."""
    h = int(hashlib.sha1(f"{source_id}:{opened_count}".encode()).hexdigest()[:6], 16)
    return 0.85 + (h % 1000) / 1000 * 0.30


def allow_request(b: BreakerState, now: datetime) -> tuple[bool, BreakerState]:
    """(pode tentar?, estado). OPEN vencido vira HALF_OPEN e libera UMA tentativa de prova."""
    if b.state == OPEN and b.next_attempt_at is not None and now < b.next_attempt_at:
        return False, b
    if b.state == OPEN:
        return True, replace(b, state=HALF_OPEN)
    return True, b


def record(b: BreakerState, source_id: str, transport: str, now: datetime, retry_after_s: float | None = None) -> BreakerState:
    """Registra o resultado de uma tentativa. Sucesso fecha e zera; falha de transporte soma e pode abrir."""
    if transport not in FAIL_STATES:
        return BreakerState()  # ONLINE/DEGRADED: transporte funcionou (o dado pode estar vazio/velho, isso é outra dimensão)
    failures = b.consecutive_failures + 1
    probe_failed = b.state == HALF_OPEN
    if not (probe_failed or failures >= FAILURE_THRESHOLD or retry_after_s):
        return replace(b, state=CLOSED, consecutive_failures=failures, last_reason=transport)
    opened = b.opened_count + 1
    wait_min = min(MAX_OPEN_MIN, BASE_OPEN_MIN * 2 ** (opened - 1)) * _jitter(source_id, opened)
    if retry_after_s:  # o servidor pediu: nunca antes do que ele disse (limitado)
        wait_min = max(wait_min, min(MAX_RETRY_AFTER_MIN, retry_after_s / 60))
    return BreakerState(OPEN, failures, opened, now + timedelta(minutes=wait_min), transport)
