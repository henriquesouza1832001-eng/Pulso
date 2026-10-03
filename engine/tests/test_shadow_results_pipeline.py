"""V1 x V2 x desfecho: as linhas de shadow_results precisam CHEGAR ao lote enviado ao Worker (já houve perda silenciosa por colisão de edições)."""
from datetime import datetime, timezone

import pytest

from pulso_engine import pipeline
from pulso_engine.pipeline import chunks, run_once

T = datetime(2026, 10, 3, 15, 2, tzinfo=timezone.utc)
ROW = {"item_id": "fc-x", "method": "pulse_empirical_delta", "scope": "BR", "p_v1": 0.4, "p_v2": 0.6, "outcome": 1}


def _run():
    return run_once([], now=T, history=[], pulse_points=[], open_forecasts=[], stored=[], known_events=[])


def test_flag_off_sends_an_empty_list_and_never_computes(monkeypatch):
    monkeypatch.delenv("PULSO_FLAG_FORECAST_V2_SHADOW", raising=False)
    monkeypatch.setattr(pipeline, "shadow_rows", lambda forecasts: pytest.fail("flag desligada: não deveria calcular"))
    assert _run()["shadow_results"] == []


def test_flag_on_puts_the_rows_in_the_batch(monkeypatch):
    monkeypatch.setenv("PULSO_FLAG_FORECAST_V2_SHADOW", "1")
    monkeypatch.setattr(pipeline, "shadow_rows", lambda forecasts: [ROW])
    assert _run()["shadow_results"] == [ROW]


def test_rows_survive_chunking_in_the_last_part_only():
    batch = {"batch_id": "b", "sources": [], "catalog_complete": False, "events": [{"event_id": f"ev-{i}", "title": "t"} for i in range(400)],
             "signals": [{"event_id": f"ev-{i}", "source_id": "s1", "hash": f"h{i}"} for i in range(400)], "pulses": [], "source_health": [],
             "series": [], "forecasts": [], "shadow_results": [ROW]}
    parts = chunks(batch)
    assert len(parts) > 1 and [len(p["shadow_results"]) for p in parts] == [0] * (len(parts) - 1) + [1]


def test_calibrators_survive_chunking_in_the_last_part_only():
    batch = {"batch_id": "b", "sources": [], "catalog_complete": False, "events": [{"event_id": f"ev-{i}", "title": "t"} for i in range(400)],
             "signals": [{"event_id": f"ev-{i}", "source_id": "s1", "hash": f"h{i}"} for i in range(400)], "pulses": [], "source_health": [],
             "series": [], "forecasts": [], "calibrators": [{"id": "cal-platt-v1"}]}
    parts = chunks(batch)
    assert len(parts) > 1 and [len(p["calibrators"]) for p in parts] == [0] * (len(parts) - 1) + [1]
