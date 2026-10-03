import math
from datetime import datetime, timedelta, timezone

from pulso_engine.forecast_surge import (
    MIN_COVERAGE_POINTS, make_surge_forecasts, merge_series, resolve_surge_due, rolling_hour,
)

NOW = datetime(2026, 10, 3, 12, 2, tzinfo=timezone.utc)  # a janela 12:00 ainda está aberta


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def rows_for(counts_per_hour, scope="BR", category="WEATHER", end=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)):
    """Linhas de série de 5 min: distribui cada contagem horária (a última termina em `end`)."""
    rows = []
    n = len(counts_per_hour)
    for i, total in enumerate(counts_per_hour):
        hour_start = end - timedelta(hours=n - i)
        for b in range(12):
            share = total // 12 + (1 if b < total % 12 else 0)
            if share:
                rows.append({"scope": scope, "category": category, "bucket": iso(hour_start + timedelta(minutes=5 * b)),
                             "signals": share, "sources": 2})
    return rows


def wave(n=60):
    return [8 + round(5 * math.sin(i / 2.5)) for i in range(n)]


def test_no_forecast_without_enough_history():
    assert make_surge_forecasts(rows_for([6, 7, 8, 9, 8, 7]), NOW) == []  # poucas horas: não se prevê
    assert make_surge_forecasts([], NOW) == []


def test_no_forecast_without_current_activity():
    quiet = wave(60)[:-1] + [0]
    assert make_surge_forecasts(rows_for(quiet), NOW) == []


def test_makes_valid_forecasts_with_evidence():
    fcs = make_surge_forecasts(rows_for(wave(60)), NOW)
    assert fcs, "com ~2,5 dias de histórico contínuo deveria prever"
    for f in fcs:
        assert f["metric"] == "signals_weather" and f["scope"] == "BR" and f["comparator"] == "gte"
        assert 0 < f["probability"] < 1 and f["interval_low"] <= f["probability"] <= f["interval_high"]
        assert f["evidence"]["pairs"] >= 24 and f["evidence"]["history_hours"] >= 12
        assert f["forecast_id"].startswith("fc-surge-br-weather-") and f["forecast_id"].split("-")[4] in ("x15", "hi") and f["status"] == "open"
        assert f["threshold"] > f["evidence"]["current_hour_signals"]
        assert "clima" in f["question"] and "no Brasil" in f["question"]


def test_rolling_hour_counts_only_closed_windows():
    rows = [{"scope": "BR", "category": "WEATHER", "bucket": iso(NOW.replace(minute=0)), "signals": 99, "sources": 1},  # aberta
            {"scope": "BR", "category": "WEATHER", "bucket": iso(NOW.replace(minute=0) - timedelta(minutes=5)), "signals": 4, "sources": 1}]
    assert rolling_hour(rows, "BR", "WEATHER", NOW) == 4


def test_merge_series_keeps_the_largest_value():
    a = [{"scope": "BR", "category": "X", "bucket": "2026-10-03T10:00:00Z", "signals": 3, "sources": 1}]
    b = [{"scope": "BR", "category": "X", "bucket": "2026-10-03T10:00:00Z", "signals": 7, "sources": 2}]
    assert merge_series(a, b)[0]["signals"] == 7 and merge_series(b, a)[0]["signals"] == 7


def _open(created, threshold=10, prob=0.4):
    return {"forecast_id": "f1", "metric": "signals_weather", "scope": "BR", "comparator": "gte", "threshold": float(threshold),
            "probability": prob, "created_at": iso(created), "resolves_at": iso(created + timedelta(minutes=60)), "evidence": {}}


def _pulse_points(start, n):
    return [{"timestamp": iso(start + timedelta(minutes=5 * i)), "score": 20} for i in range(n)]


def test_resolves_with_real_count_when_collection_is_covered():
    created = datetime(2026, 10, 3, 10, 0, tzinfo=timezone.utc)
    window_rows = [{"scope": "BR", "category": "WEATHER", "bucket": iso(created + timedelta(minutes=5 * i)), "signals": 1, "sources": 1}
                   for i in range(12)]  # 12 sinais na hora seguinte
    out = resolve_surge_due([_open(created, threshold=10)], window_rows, _pulse_points(created, 12), NOW)
    assert len(out) == 1 and out[0]["status"] == "resolved" and out[0]["outcome"] == 1 and out[0]["observed_value"] == 12.0
    assert out[0]["brier"] == round((0.4 - 1) ** 2, 6)
    miss = resolve_surge_due([_open(created, threshold=20)], window_rows, _pulse_points(created, 12), NOW)
    assert miss[0]["outcome"] == 0


def test_void_when_collection_had_a_gap():
    created = datetime(2026, 10, 3, 9, 0, tzinfo=timezone.utc)
    out = resolve_surge_due([_open(created)], [], _pulse_points(created, MIN_COVERAGE_POINTS - 2), NOW)
    assert len(out) == 1 and out[0]["status"] == "void" and out[0]["brier"] is None  # lacuna não vira "calmaria"


def test_waits_until_the_last_window_closes_and_ignores_pulse_forecasts():
    created = datetime(2026, 10, 3, 11, 30, tzinfo=timezone.utc)
    assert resolve_surge_due([_open(created)], [], _pulse_points(created, 12), NOW) == []  # ainda não venceu
    pulse = {**_open(created), "metric": "pulse"}
    assert resolve_surge_due([pulse], [], _pulse_points(created, 12), NOW + timedelta(hours=3)) == []
