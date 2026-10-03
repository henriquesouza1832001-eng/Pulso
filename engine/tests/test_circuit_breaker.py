from datetime import datetime, timedelta, timezone

from pulso_engine.circuit_breaker import (CLOSED, FAILURE_THRESHOLD, HALF_OPEN, MAX_OPEN_MIN, OPEN, BreakerState, allow_request, record)

NOW = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)


def fail(b, t=NOW, sid="s", transport="OFFLINE", ra=None):
    return record(b, sid, transport, t, ra)


def test_closed_until_threshold_then_opens_and_skips():
    b = BreakerState()
    for _ in range(FAILURE_THRESHOLD - 1):
        b = fail(b)
        assert b.state == CLOSED and allow_request(b, NOW)[0]
    b = fail(b)
    assert b.state == OPEN and b.next_attempt_at > NOW
    ok, same = allow_request(b, NOW + timedelta(minutes=1))
    assert not ok and same is b  # aberta: pulada, sem insistir


def test_half_open_probe_closes_on_success_and_reopens_longer_on_failure():
    b = BreakerState()
    for _ in range(FAILURE_THRESHOLD):
        b = fail(b)
    first_wait = b.next_attempt_at - NOW
    later = b.next_attempt_at + timedelta(seconds=1)
    ok, half = allow_request(b, later)
    assert ok and half.state == HALF_OPEN
    reopened = fail(half, later)  # a prova falhou: reabre IMEDIATAMENTE (sem esperar 3 falhas) e com espera maior
    assert reopened.state == OPEN and reopened.opened_count == 2 and reopened.next_attempt_at - later > first_wait
    ok2, half2 = allow_request(reopened, reopened.next_attempt_at)
    assert record(half2, "s", "ONLINE", reopened.next_attempt_at) == BreakerState()  # prova ok: fecha e zera


def test_backoff_is_exponential_and_capped():
    b = BreakerState()
    waits = []
    t = NOW
    for _ in range(10):
        for _ in range(FAILURE_THRESHOLD if b.state == CLOSED else 1):
            if b.state == OPEN:
                _, b = allow_request(b, b.next_attempt_at)
                t = b.next_attempt_at or t
            b = fail(b, t)
        waits.append((b.next_attempt_at - t).total_seconds() / 60)
    assert waits[1] > waits[0] and max(waits) <= MAX_OPEN_MIN * 1.15 + 1


def test_retry_after_is_respected_and_bounded():
    b = fail(BreakerState(), transport="RATE_LIMITED", ra=3600)  # 429 com Retry-After: 1 h abre na hora, sem esperar 3 falhas
    assert b.state == OPEN and b.next_attempt_at - NOW >= timedelta(minutes=60)
    huge = fail(BreakerState(), transport="RATE_LIMITED", ra=10 * 24 * 3600)
    assert huge.next_attempt_at - NOW <= timedelta(hours=24)  # Retry-After absurdo é limitado


def test_empty_or_stale_data_with_working_transport_never_opens_the_breaker():
    b = BreakerState()
    for t in ("ONLINE", "DEGRADED") * 5:
        b = record(b, "s", t, NOW)
    assert b == BreakerState()


def test_jitter_is_stable_per_source_and_spreads_sources():
    open_for = lambda sid: (fail(fail(fail(BreakerState(), sid=sid), sid=sid), sid=sid).next_attempt_at - NOW)  # noqa: E731
    assert open_for("a") == open_for("a")
    assert len({open_for(f"src{i}") for i in range(20)}) > 10
