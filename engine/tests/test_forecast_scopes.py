from datetime import datetime, timedelta, timezone

from pulso_engine.forecast import MIN_PAIRS
from pulso_engine.forecast_scopes import make_scope_nowcasts, resolve_scope_due

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def points(base, n=MIN_PAIRS + 14, step=5):
    out = []
    for i in range(n):
        t = NOW - timedelta(minutes=step * (n - 1 - i))
        out.append({"timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "score": base + (i % 7)})
    return out


def test_only_scopes_with_history_and_relevant_pulse_forecast():
    data = {"BR": points(40), "UF:MG": points(50), "UF:SP": points(5), "UF:RJ": points(60, n=10)}
    fc = make_scope_nowcasts(data, NOW)
    scopes = {f["scope"] for f in fc}
    assert scopes == {"BR", "UF:MG"}  # SP: Pulso baixo; RJ: histórico curto
    assert all(f["status"] == "open" and 0 < f["probability"] < 1 for f in fc)
    assert len({f["forecast_id"] for f in fc}) == len(fc)


def test_cap_keeps_the_most_intense_scopes_and_never_drops_br():
    data = {"BR": points(30)} | {f"UF:{u}": points(20 + i * 3) for i, u in enumerate("AB CD EF GH IJ KL MN OP".replace(" ", "")[::2])}
    fc = make_scope_nowcasts(data, NOW, max_scopes=2)
    scopes = {f["scope"] for f in fc}
    assert "BR" in scopes and len(scopes - {"BR"}) <= 2


def test_stale_history_does_not_forecast():
    old = [{**p, "timestamp": (datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00")) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")} for p in points(50)]
    assert make_scope_nowcasts({"UF:MG": old}, NOW) == []


def test_each_forecast_resolves_with_its_own_scope_series():
    created = NOW - timedelta(minutes=60)
    open_fc = [{"forecast_id": "a", "scope": "UF:MG", "threshold": 50.0, "comparator": "gte", "probability": 0.4,
                "resolves_at": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "evidence": {}, "created_at": created.strftime("%Y-%m-%dT%H:%M:%SZ")},
               {"forecast_id": "b", "scope": "UF:SP", "threshold": 50.0, "comparator": "gte", "probability": 0.4,
                "resolves_at": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "evidence": {}, "created_at": created.strftime("%Y-%m-%dT%H:%M:%SZ")}]
    data = {"UF:MG": [{"timestamp": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "score": 70}],
            "UF:SP": [{"timestamp": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "score": 10}]}
    res = {f["forecast_id"]: f for f in resolve_scope_due(open_fc, data, NOW)}
    assert res["a"]["outcome"] == 1 and res["b"]["outcome"] == 0  # MG não resolve com o Pulso de SP
