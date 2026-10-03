import random
from datetime import datetime, timedelta, timezone

from pulso_engine.drivers import aligned_hourly, best_lead, leading_indicators, pearson
from pulso_engine.forecast_surge import make_surge_forecasts

NOW = datetime(2026, 10, 3, 12, 2, tzinfo=timezone.utc)
END = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def to_rows(counts, category, scope="BR", end=END):
    n, rows = len(counts), []
    for i, total in enumerate(counts):
        start = end - timedelta(hours=n - i)
        for b in range(12):
            share = total // 12 + (1 if b < total % 12 else 0)
            if share:
                rows.append({"scope": scope, "category": category, "bucket": iso(start + timedelta(minutes=5 * b)),
                             "signals": share, "sources": 2})
    return rows


def weather_leads_traffic(n=96, lag=2, seed=5, last_weather=None):
    rng = random.Random(seed)
    weather = [max(0, round(rng.gauss(6, 2) + (14 if rng.random() < 0.12 else 0))) for _ in range(n)]
    if last_weather is not None:
        weather[-1] = last_weather
    traffic = [max(0, round(3 + 0.7 * weather[i - lag] + rng.gauss(0, 1))) if i >= lag else 3 for i in range(n)]
    return weather, traffic


def test_pearson_basics():
    assert abs(pearson([1, 2, 3, 4], [2, 4, 6, 8]) - 1) < 1e-9
    assert pearson([1, 1, 1], [1, 2, 3]) == 0.0  # série constante não correlaciona
    assert pearson([1, 2], [1, 2]) == 0.0  # amostra pequena demais


def test_best_lead_finds_the_true_lag():
    weather, traffic = weather_leads_traffic(lag=2)
    lag, r = best_lead(weather, traffic)
    assert lag == 2 and r > 0.6


def test_leading_indicator_reported_when_leader_is_elevated_now():
    weather, traffic = weather_leads_traffic(last_weather=40)
    rows = to_rows(weather, "WEATHER") + to_rows(traffic, "TRAFFIC")
    # a hora corrente (aberta) com muito clima: janelas fechadas das últimas 12 colunas de 5 min
    rows += [{"scope": "BR", "category": "WEATHER", "bucket": iso(END - timedelta(minutes=5 * i)), "signals": 6, "sources": 3}
             for i in range(1, 13)]
    out = leading_indicators(rows, "TRAFFIC", "BR", NOW)
    assert out and out[0]["category"] == "WEATHER" and out[0]["lag_hours"] == 2 and out[0]["current_z"] >= 1


def test_no_indicator_when_leader_is_calm_or_history_is_short():
    weather, traffic = weather_leads_traffic()
    calm = to_rows(weather, "WEATHER") + to_rows(traffic, "TRAFFIC")
    assert leading_indicators([r for r in calm if r["bucket"] < iso(END - timedelta(minutes=60))], "TRAFFIC", "BR", NOW) == []
    short = to_rows(weather[-10:], "WEATHER") + to_rows(traffic[-10:], "TRAFFIC")
    assert aligned_hourly(short, "BR", {"WEATHER", "TRAFFIC"}, NOW) is None  # cobertura insuficiente
    assert leading_indicators(short, "TRAFFIC", "BR", NOW) == []


def test_forecast_evidence_carries_leading_indicators_without_changing_probability():
    weather, traffic = weather_leads_traffic(last_weather=40)
    rows = to_rows(weather, "WEATHER") + to_rows(traffic, "TRAFFIC")
    rows += [{"scope": "BR", "category": "WEATHER", "bucket": iso(END - timedelta(minutes=5 * i)), "signals": 6, "sources": 3}
             for i in range(1, 13)]
    traffic_fc = [f for f in make_surge_forecasts(rows, NOW) if f["metric"] == "signals_traffic"]
    assert traffic_fc
    assert all("leading_indicators" in f["evidence"] for f in traffic_fc)
    assert any(f["evidence"]["leading_indicators"] for f in traffic_fc)
    assert all(0 < f["probability"] < 1 for f in traffic_fc)
