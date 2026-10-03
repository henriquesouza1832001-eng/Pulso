"""Trilha de auditoria no pipeline: toda previsão NOVA ganha snapshot imutável; reenvio e flag desligada não geram nada."""
from datetime import datetime, timedelta, timezone

from pulso_engine.pipeline import chunks, run_once
from pulso_engine.validation.forecast_registry import reproduces, verify

T = datetime(2026, 10, 3, 15, 2, tzinfo=timezone.utc)


def _points():
    # 6 h de Pulso nacional a cada 5 min (o previsor de Pulso exige ~3,5 h de histórico)
    return [{"timestamp": (T - timedelta(minutes=5 * k)).strftime("%Y-%m-%dT%H:%M:%SZ"), "score": 40 + (k % 7)} for k in range(72, 0, -1)]


def _run(**kw):
    return run_once([], now=T, history=[], pulse_points=_points(), open_forecasts=kw.pop("open_forecasts", []), stored=[], known_events=[], **kw)


def test_every_new_forecast_gets_an_immutable_auditable_snapshot(monkeypatch):
    monkeypatch.delenv("PULSO_FLAG_FORECAST_REGISTRY", raising=False)
    b = _run()
    new = [f for f in b["forecasts"] if f["status"] == "open"]
    assert new and len(b["forecast_registry"]) == len(new)
    by_id = {f["forecast_id"]: f for f in new}
    for e in b["forecast_registry"]:
        assert set(e) == {"forecast_id", "created_at", "snapshot", "snapshot_hash"} and verify(e)
        assert reproduces(e, by_id[e["forecast_id"]])  # a previsão guardada bate com o que foi previsto
        assert '"flags"' in e["snapshot"] and "ewma_v1" in e["snapshot"]  # versões e flags ativas ficam registradas


def test_already_open_forecasts_are_not_registered_again_and_flag_off_means_nothing(monkeypatch):
    b = _run()
    already = [dict(f) for f in b["forecasts"] if f["status"] == "open"]
    assert _run(open_forecasts=already)["forecast_registry"] == []  # imutável: só o que ainda não existe
    monkeypatch.setenv("PULSO_FLAG_FORECAST_REGISTRY", "0")
    assert _run()["forecast_registry"] == []


def test_chunks_carry_the_registry_in_the_last_part_only():
    batch = {"batch_id": "b", "sources": [], "catalog_complete": False, "events": [{"event_id": f"ev-{i}", "title": "t"} for i in range(400)],
             "signals": [{"event_id": f"ev-{i}", "source_id": "s1", "hash": f"h{i}"} for i in range(400)], "pulses": [], "source_health": [],
             "series": [], "forecasts": [], "forecast_registry": [{"forecast_id": "fc-x"}]}
    parts = chunks(batch)
    assert [len(p["forecast_registry"]) for p in parts] == [0] * (len(parts) - 1) + [1]
