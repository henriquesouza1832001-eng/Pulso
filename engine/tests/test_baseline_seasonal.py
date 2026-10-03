from datetime import datetime, timedelta, timezone

from pulso_engine.anomaly import anomaly_score
from pulso_engine.baseline import BR_TZ, INSUFFICIENT, seasonal_baseline

AT = datetime(2026, 10, 4, 6, 20, tzinfo=timezone.utc)  # domingo 03:20 em Brasília


def rows_for(fn, days=42, scope="BR", cat="TRAFFIC"):
    out = []
    end = AT.replace(minute=0)
    for i in range(1, 24 * days):
        h = end - timedelta(hours=i)
        v = fn(h.astimezone(BR_TZ))
        if v:
            out.append({"scope": scope, "category": cat, "source_class": "NEWS_HIGH",
                        "hour": h.strftime("%Y-%m-%dT%H:%M:%SZ"), "signals": v, "sources": 1, "duplicates": 0})
    return out


def test_no_rows_is_insufficient():
    assert seasonal_baseline([], "BR", "TRAFFIC", AT) == INSUFFICIENT
    assert not INSUFFICIENT.valid
    assert anomaly_score(50, INSUFFICIENT) == 0.0  # nunca finge anomalia


def test_dow_hour_separates_sunday_night_from_monday_rush():
    fn = lambda l: 40 if (l.weekday() == 0 and l.hour == 18) else (2 if l.hour == 3 and l.weekday() == 6 else 5)  # noqa: E731
    rows = rows_for(fn)
    sunday3 = seasonal_baseline(rows, "BR", "TRAFFIC", AT)
    assert sunday3.basis == "dow_hour" and sunday3.valid
    assert sunday3.mean < 5
    monday18 = seasonal_baseline(rows, "BR", "TRAFFIC", datetime(2026, 10, 5, 21, 20, tzinfo=timezone.utc))
    assert monday18.mean > 30
    assert anomaly_score(39, monday18) < anomaly_score(39, sunday3)


def test_falls_back_to_hour_of_day_with_one_week():
    rows = rows_for(lambda l: 4, days=8)
    b = seasonal_baseline(rows, "BR", "TRAFFIC", AT)
    assert b.valid and b.basis in ("dow_hour", "hour")
    b2 = seasonal_baseline(rows_for(lambda l: 4, days=4), "BR", "TRAFFIC", AT)
    assert b2.basis == "insufficient"  # 3 dias: nem 5 horas comparáveis


def test_sparse_history_is_insufficient():
    rows = rows_for(lambda l: 1 if l.hour == 12 and l.day % 9 == 0 else 0)
    assert not seasonal_baseline(rows, "BR", "TRAFFIC", AT).valid


def test_other_scope_and_category_ignored():
    rows = rows_for(lambda l: 5, scope="UF:MG", cat="WEATHER")
    assert not seasonal_baseline(rows, "BR", "TRAFFIC", AT).valid


def test_current_hour_excluded():
    rows = rows_for(lambda l: 5)
    rows.append({"scope": "BR", "category": "TRAFFIC", "source_class": "X", "hour": AT.replace(minute=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "signals": 999, "sources": 1, "duplicates": 0})
    assert seasonal_baseline(rows, "BR", "TRAFFIC", AT).mean < 10
