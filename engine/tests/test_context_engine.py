from datetime import date, datetime, timedelta, timezone

from pulso_engine.anomaly import window_anomaly
from pulso_engine.baseline import BR_TZ, seasonal_baseline
from pulso_engine.intelligence.context_engine import (contextual_baseline, day_context, effective_weekday, fetch_holidays,
                                                      parse_holidays)

SAMPLE = b'[{"date":"2026-10-12","name":"Nossa Senhora Aparecida","type":"national"},{"date":"2026-11-02","name":"Finados","type":"national"}]'
HOLIDAYS = {date(2026, 10, 12): "Nossa Senhora Aparecida"}
AT = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)  # segunda 12:00 em Brasília, FERIADO


def test_parse_and_fetch_without_network_and_with_failures():
    assert parse_holidays(SAMPLE)[date(2026, 10, 12)] == "Nossa Senhora Aparecida" and len(parse_holidays(SAMPLE)) == 2
    assert parse_holidays(b"nao e json") == {} and parse_holidays(b'{"x":1}') == {}
    calls = []

    def fetcher(url):
        calls.append(url)
        if "2025" in url:
            raise OSError("fora do ar")
        return SAMPLE

    got = fetch_holidays([2025, 2026], fetcher)
    assert len(calls) == 2 and date(2026, 10, 12) in got  # o ano que falhou não derrubou o outro


def test_holiday_counts_as_sunday():
    assert effective_weekday(AT, HOLIDAYS) == 6 and effective_weekday(AT, {}) == 0
    ctx = day_context(AT, HOLIDAYS)
    assert ctx["holiday"] == "Nossa Senhora Aparecida" and ctx["weekday"] == 0 and ctx["effective_weekday"] == 6


def rows(days=60):
    out = []
    end = AT.replace(minute=0)
    for h in range(1, 24 * days):
        t = end - timedelta(hours=h)
        local = t.astimezone(BR_TZ)
        quiet_day = local.weekday() == 6 or local.date() in HOLIDAYS
        out.append({"scope": "BR", "category": "TRAFFIC", "source_class": "NEWS_HIGH", "hour": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "signals": 2 if (quiet_day and local.hour == 12) else 20 if local.hour == 12 else 5, "sources": 2, "duplicates": 0})
    return out


def test_holiday_monday_is_compared_with_sundays_not_mondays():
    r = rows()
    plain = seasonal_baseline(r, "BR", "TRAFFIC", AT)
    ctx = contextual_baseline(r, "BR", "TRAFFIC", AT, HOLIDAYS)
    assert plain.mean > 10 and ctx.mean < 5  # sem contexto, "normal" seria de segunda comum
    # 12 sinais/h num feriado: anomalia contra domingos, mas "normal" contra as segundas
    assert window_anomaly(12, 60, ctx)["status"] == "ANOMALY"
    assert window_anomaly(12, 60, plain)["status"] == "NORMAL"


def test_without_holidays_equals_plain_seasonal_and_insufficient_stays_insufficient():
    r = rows()
    plain, ctx = seasonal_baseline(r, "BR", "TRAFFIC", AT), contextual_baseline(r, "BR", "TRAFFIC", AT, {})
    assert (plain.mean, plain.std, plain.basis) == (ctx.mean, ctx.std, ctx.basis)
    assert not contextual_baseline([], "BR", "TRAFFIC", AT, HOLIDAYS).valid
    assert not contextual_baseline(rows(days=3), "BR", "TRAFFIC", AT, HOLIDAYS).valid
