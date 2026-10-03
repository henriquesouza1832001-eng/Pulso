"""Estado por fonte (frescor + circuit breaker) integrado ao ciclo: escrita econômica, breaker em SHADOW por padrão e Retry-After.

Contrato com o Worker: `SourceRuntimeRow` / `EngineCycle` (packages/shared/src/contracts.ts). O Actions não tem memória: o estado
anterior chega em `breakers=` (vem de GET /api/admin/source-runtime) e o novo volta em `batch["source_runtime"]`.
"""
import urllib.error
from datetime import datetime, timedelta, timezone
from email.message import Message

from pulso_engine.circuit_breaker import BreakerState
from pulso_engine.pipeline import chunks, run_once
from pulso_engine.source_runtime import (HEARTBEAT_MIN, breaker_from_row, cycle_summary, retry_after_seconds, runtime_row,
                                         select_runtime)

NOW = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)


def rss(minutes_ago=10, title="Acidente grave em Betim deixa feridos"):
    d = (NOW - timedelta(minutes=minutes_ago)).strftime("%a, %d %b %Y %H:%M:%S +0000")
    return f"<rss><channel><item><title>{title}</title><link>https://x/1</link><pubDate>{d}</pubDate></item></channel></rss>".encode()


def src(sid="a", **kw):
    return {"id": sid, "name": sid, "domain": f"{sid}.com", "adapter": "rss", "source_class": "NEWS_HIGH", "url": f"https://{sid}.com/rss",
            "state": None, "enabled": True, **kw}


def feed(mapping, calls=None):
    def fetcher(url):
        sid = url.split("//")[1].split(".")[0]
        if calls is not None:
            calls.append(sid)
        v = mapping[sid]
        if isinstance(v, Exception):
            raise v
        return v
    return fetcher


def rows(batch):
    return {r["source_id"]: r for r in batch["source_runtime"]}


def cycle(sources, fetcher, now, prev=None):
    return run_once(sources, fetcher=fetcher, now=now, breakers=prev)


def http429(retry_after):
    h = Message()
    if retry_after is not None:
        h["Retry-After"] = retry_after
    return urllib.error.HTTPError("https://a.com/rss", 429, "Too Many Requests", h, None)


# ---------- peças puras ----------

def test_runtime_row_without_freshness_assessment_is_unavailable_never_fresh():
    r = runtime_row(None, "a", "ONLINE", BreakerState(), NOW)
    assert r["freshness_state"] == "UNAVAILABLE" and r["records"] == 0 and r["breaker_state"] == "CLOSED"


def test_breaker_from_row_never_blocks_on_missing_or_corrupt_state():
    assert breaker_from_row(None) == BreakerState()
    assert breaker_from_row({"breaker_state": "ABERTO"}) == BreakerState()  # valor desconhecido: CLOSED, nunca bloqueia por dúvida
    assert breaker_from_row({"breaker_state": "OPEN", "consecutive_failures": "x"}) == BreakerState()
    b = breaker_from_row({"breaker_state": "OPEN", "consecutive_failures": 3, "opened_count": 2, "next_attempt_at": "2026-10-04T16:00:00Z", "breaker_reason": "OFFLINE"})
    assert b.state == "OPEN" and b.opened_count == 2 and b.next_attempt_at == datetime(2026, 10, 4, 16, 0, tzinfo=timezone.utc)


def test_retry_after_seconds_parses_seconds_and_http_date_and_rejects_garbage():
    assert retry_after_seconds(http429("1800")) == 1800
    assert retry_after_seconds(http429("Sun, 04 Oct 2026 15:30:00 GMT"), NOW) == 1800
    for bad in ("amanhã", "-5", "0", "", None):
        assert retry_after_seconds(http429(bad), NOW) is None
    assert retry_after_seconds(ValueError("sem headers")) is None


def test_select_runtime_sends_only_changes_and_expired_heartbeats():
    base = runtime_row(None, "a", "ONLINE", BreakerState(), NOW)
    prev = {"a": {**base, "updated_at": "2026-10-04T14:55:00Z"}}
    again = {**base, "records": 99, "new_records": 5, "updated_at": "2026-10-04T15:00:00Z"}  # só contagem mudou: NÃO grava
    assert select_runtime([again], prev, NOW) == []
    assert select_runtime([{**again, "freshness_state": "STALE"}], prev, NOW)  # estado mudou: grava
    assert select_runtime([{**again, "breaker_state": "OPEN"}], prev, NOW)
    assert select_runtime([{**again, "transport": "OFFLINE"}], prev, NOW)
    assert select_runtime([again], {}, NOW) == [again]  # fonte nova
    old = {"a": {**base, "updated_at": (NOW - timedelta(minutes=HEARTBEAT_MIN + 1)).strftime("%Y-%m-%dT%H:%M:%SZ")}}
    assert select_runtime([again], old, NOW) == [again]  # batimento vencido
    assert select_runtime([again], {"a": {**base, "updated_at": "lixo"}}, NOW) == [again]  # data ilegível: reenvia


def test_cycle_summary_counts_states_and_never_hides_breakers():
    b = cycle([src("a"), src("b")], feed({"a": rss(), "b": OSError("reset")}), NOW)
    s = cycle_summary(b["source_runtime"], b["source_freshness"], {"a": "NEWS_HIGH", "b": "NEWS_HIGH"}, now=NOW, duration_s=12.345,
                      sources_due=2, sources_skipped=0, signals_sent=1, events=0, flags={"X": True}, engine_ref="abcdef1234567890")
    assert s["freshness"]["FRESH"] == 1 and s["freshness"]["UNKNOWN"] == 1  # offline = UNKNOWN, não zero e não FRESH
    assert s["duration_s"] == 12.35 and s["engine_ref"] == "abcdef123456" and s["sources_due"] == 2
    assert s["coverage"]["NEWS_HIGH"]["sources"] == 2


# ---------- integração com o ciclo ----------

def test_runtime_rows_cover_every_collected_source_with_freshness_and_transport():
    b = cycle([src("a"), src("b"), src("c")], feed({"a": rss(), "b": rss(minutes_ago=3000), "c": OSError("reset")}), NOW)
    r = rows(b)
    assert (r["a"]["freshness_state"], r["a"]["transport"]) == ("FRESH", "ONLINE")
    assert (r["b"]["freshness_state"], r["b"]["transport"]) == ("STALE", "ONLINE")  # 200 != dado novo
    assert (r["c"]["freshness_state"], r["c"]["transport"]) == ("UNKNOWN", "OFFLINE")
    assert all(x["updated_at"] == "2026-10-04T15:00:00Z" for x in r.values())


def test_three_transport_failures_open_the_breaker_and_state_travels_between_cycles():
    prev = None
    for i in range(3):
        b = cycle([src("a")], feed({"a": OSError("reset")}), NOW + timedelta(minutes=5 * i), prev)
        prev = rows(b)
        assert prev["a"]["consecutive_failures"] == i + 1
    r = prev["a"]
    assert r["breaker_state"] == "OPEN" and r["opened_count"] == 1 and r["next_attempt_at"] and r["breaker_reason"] == "OFFLINE"


def test_empty_or_stale_content_with_ok_transport_never_opens_the_breaker():
    prev = None
    for i in range(5):  # problema de DADO, não de rede
        b = cycle([src("a")], feed({"a": rss(minutes_ago=3000)}), NOW + timedelta(minutes=5 * i), prev)
        prev = rows(b)
    assert prev["a"]["breaker_state"] == "CLOSED" and prev["a"]["consecutive_failures"] == 0


def test_shadow_by_default_collects_even_an_open_breaker_and_does_not_evolve_its_state(monkeypatch):
    monkeypatch.delenv("PULSO_FLAG_CIRCUIT_BREAKER_ENFORCE", raising=False)
    open_row = {"source_id": "a", "breaker_state": "OPEN", "consecutive_failures": 3, "opened_count": 1, "breaker_reason": "OFFLINE",
                "next_attempt_at": (NOW + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    calls = []
    b = cycle([src("a")], feed({"a": rss()}, calls), NOW, {"a": open_row})
    assert calls == ["a"] and b["breakers_skipped"] == 0  # SHADOW: não pula
    r = rows(b)["a"]
    assert r["breaker_state"] == "OPEN" and r["opened_count"] == 1 and r["consecutive_failures"] == 3  # nem fecha nem infla o backoff


def test_enforce_skips_an_open_breaker_without_calling_the_source_and_reports_why(monkeypatch):
    monkeypatch.setenv("PULSO_FLAG_CIRCUIT_BREAKER_ENFORCE", "1")
    until = (NOW + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    open_row = {"source_id": "a", "breaker_state": "OPEN", "consecutive_failures": 3, "opened_count": 1, "breaker_reason": "OFFLINE", "next_attempt_at": until}
    calls = []
    b = cycle([src("a"), src("b")], feed({"a": rss(), "b": rss()}, calls), NOW, {"a": open_row})
    assert calls == ["b"] and b["breakers_skipped"] == 1  # a fonte aberta NÃO foi chamada; a outra seguiu normal
    health = {h["source_id"]: h for h in b["source_health"]}
    assert health["a"]["status"] == "OFFLINE" and "circuit breaker" in health["a"]["detail"] and until in health["a"]["detail"]
    r = rows(b)
    assert r["a"]["breaker_state"] == "OPEN" and r["a"]["opened_count"] == 1  # pulada = sem tentativa = o breaker não muda
    assert r["a"]["freshness_state"] == "UNKNOWN"  # não afirma nada sobre o dado; nunca "zero"
    assert r["b"]["freshness_state"] == "FRESH"


def test_half_open_probe_success_closes_and_failure_reopens_with_longer_backoff(monkeypatch):
    monkeypatch.setenv("PULSO_FLAG_CIRCUIT_BREAKER_ENFORCE", "1")
    due = {"source_id": "a", "breaker_state": "OPEN", "consecutive_failures": 3, "opened_count": 1, "breaker_reason": "OFFLINE",
           "next_attempt_at": (NOW - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    ok = rows(cycle([src("a")], feed({"a": rss()}), NOW, {"a": due}))["a"]
    assert ok["breaker_state"] == "CLOSED" and ok["consecutive_failures"] == 0 and ok["opened_count"] == 0  # sonda deu certo
    bad = rows(cycle([src("a")], feed({"a": OSError("reset")}), NOW, {"a": due}))["a"]
    assert bad["breaker_state"] == "OPEN" and bad["opened_count"] == 2  # a sonda falhou: reabre com backoff maior
    assert datetime.fromisoformat(bad["next_attempt_at"].replace("Z", "+00:00")) > NOW + timedelta(minutes=10)


def test_429_with_retry_after_opens_immediately_and_never_retries_before_the_server_said(monkeypatch):
    b = cycle([src("a")], feed({"a": http429("7200")}), NOW)  # servidor pediu 2 h
    r = rows(b)["a"]
    assert r["transport"] == "RATE_LIMITED" and r["breaker_state"] == "OPEN"
    assert datetime.fromisoformat(r["next_attempt_at"].replace("Z", "+00:00")) >= NOW + timedelta(hours=2)


def test_429_without_retry_after_still_counts_but_does_not_open_on_the_first_failure():
    r = rows(cycle([src("a")], feed({"a": http429(None)}), NOW))["a"]
    assert r["transport"] == "RATE_LIMITED" and r["breaker_state"] == "CLOSED" and r["consecutive_failures"] == 1


def test_last_content_advance_is_carried_when_nothing_new_arrives():
    first = rows(cycle([src("a")], feed({"a": rss(minutes_ago=10)}), NOW))["a"]
    assert first["last_content_advance"] == "2026-10-04T15:00:00Z"
    stored = cycle([src("a")], feed({"a": rss(minutes_ago=10)}), NOW)["signals"]  # o que já foi gravado
    later = NOW + timedelta(minutes=5)
    again = run_once([src("a")], fetcher=feed({"a": rss(minutes_ago=15)}), now=later, stored=stored, breakers={"a": first})
    assert rows(again)["a"]["new_records"] == 0
    assert rows(again)["a"]["last_content_advance"] == first["last_content_advance"]  # não avançou: mantém o anterior


def test_flags_off_means_no_runtime_rows_and_no_breaker_effect(monkeypatch):
    monkeypatch.setenv("PULSO_FLAG_RUNTIME_PERSIST", "0")
    monkeypatch.setenv("PULSO_FLAG_CIRCUIT_BREAKER", "0")
    b = cycle([src("a")], feed({"a": rss()}), NOW)
    assert b["source_runtime"] == []


def test_runtime_persist_without_freshness_marks_unavailable_not_fresh(monkeypatch):
    monkeypatch.setenv("PULSO_FLAG_SOURCE_FRESHNESS", "0")
    r = rows(cycle([src("a")], feed({"a": rss()}), NOW))["a"]
    assert r["freshness_state"] == "UNAVAILABLE" and r["transport"] == "ONLINE"


def test_chunks_carry_runtime_only_in_the_last_part_and_never_the_full_list():
    b = cycle([src("a")], feed({"a": rss()}), NOW)
    b["source_runtime_send"] = b["source_runtime"]
    b["engine_cycle"] = {"cycle_at": "2026-10-04T15:00:00Z"}
    parts = chunks(b)
    assert parts[-1]["source_runtime"] == b["source_runtime"] and parts[-1]["engine_cycle"] == b["engine_cycle"]
    assert all(p["source_runtime"] == [] and p["engine_cycle"] is None for p in parts[:-1])
    no_select = chunks({**b, "source_runtime_send": []})
    assert no_select[-1]["source_runtime"] == []  # sem seleção, nada vai (`source_runtime` completo é só do log)
