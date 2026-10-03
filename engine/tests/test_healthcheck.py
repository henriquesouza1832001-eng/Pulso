from pulso_engine.healthcheck import evaluate


def health(age=120, sources=None, api="ONLINE", db="ONLINE"):
    return {"api": api, "db": db, "collection": {"age_seconds": age, "stale": False},
            "sources": sources if sources is not None else [{"source_id": f"s{i}", "status": "ONLINE"} for i in range(10)]}


def test_healthy_system_has_no_problems():
    assert evaluate(health()) == []


def test_down_api_or_db_and_stalled_collection_are_reported():
    assert any("API" in p for p in evaluate(health(api="OFFLINE")))
    assert any("banco" in p for p in evaluate(health(db="OFFLINE")))
    assert any("parada há 41 min" in p for p in evaluate(health(age=41 * 60)))
    assert any("nunca gravou" in p for p in evaluate({**health(), "collection": {"age_seconds": None}}))


def test_mass_source_failure_is_reported_but_a_few_failures_are_not():
    few = [{"source_id": f"s{i}", "status": "OFFLINE" if i < 2 else "ONLINE"} for i in range(10)]
    assert evaluate(health(sources=few)) == []  # 2 de 10 fora do ar é normal (feeds instáveis)
    most = [{"source_id": f"s{i}", "status": "OFFLINE" if i < 7 else "ONLINE"} for i in range(10)]
    probs = evaluate(health(sources=most))
    assert any("7 de 10 fontes OFFLINE" in p for p in probs) and any("só 3 de 10" in p for p in probs)


def test_sources_that_have_not_reported_yet_are_ignored_and_auth_errors_are_flagged():
    fresh = [{"source_id": "a", "status": "ONLINE"}] + [{"source_id": f"u{i}", "status": "UNKNOWN"} for i in range(30)]
    assert evaluate(health(sources=fresh)) == []  # catálogo novo: fontes ainda sem primeira coleta não contam
    auth = [{"source_id": "x-clima", "status": "AUTH_ERROR"}] + [{"source_id": f"s{i}", "status": "ONLINE"} for i in range(9)]
    assert any("x-clima" in p for p in evaluate(health(sources=auth)))
