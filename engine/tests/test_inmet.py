import json
from datetime import datetime, timezone

import pytest

from pulso_engine.collectors.official.inmet import InmetAdapter
from pulso_engine.config import DEFAULT_SOURCES_PATH, load_sources
from pulso_engine.pipeline import run_once

NOW = datetime(2026, 10, 3, 15, 0, tzinfo=timezone.utc)  # 12h em Brasília


def alert(i, sev, kind="Tempestade", estados="Bahia,Sergipe", inicio="2026-10-03 09:00", fim="2026-10-03 23:59", **kw):
    return {"id": i, "severidade": sev, "descricao": kind, "estados": estados, "inicio": inicio, "fim": fim,
            "riscos": ["Chuva entre 50 e 100 mm/dia, ventos de 60-100 km/h."], "encerrado": False, **kw}


def source(**kw):
    src = next(s for s in load_sources(DEFAULT_SOURCES_PATH, only_enabled=False) if s["id"] == "inmet-avisos")
    return {**src, **kw}


def run(alerts, **kw):
    payload = json.dumps({"hoje": alerts, "futuro": [alert(99, "Grande Perigo")]}).encode()
    return InmetAdapter(source(**kw), fetcher=lambda url: payload, now=lambda: NOW).run()


def test_one_signal_per_state_official_and_located():
    sigs = run([alert(1, "Perigo")])
    assert [s.state for s in sigs] == ["BA", "SE"]
    assert all(s.source_class == "OFFICIAL" and s.geo_precision == "STATE" and s.category == "WEATHER" for s in sigs)
    assert len({s.hash for s in sigs}) == 2 and sigs[0].text.startswith("Chuva entre")
    assert sigs[0].timestamp == datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)  # 09:00 BRT


def test_only_impactful_and_current():
    sigs = run([alert(1, "Perigo Potencial"), alert(2, "Grande Perigo", estados="Paraná"),
                alert(3, "Perigo", fim="2026-10-03 08:00"), alert(4, "Perigo", encerrado=True)])
    assert [(s.state, s.category) for s in sigs] == [("PR", "EMERGENCY")]  # amarelo, vencido, encerrado e futuro fora


def test_min_severity_configurable():
    assert len(run([alert(1, "Perigo Potencial")], min_severity="Perigo Potencial")) == 2
    with pytest.raises(ValueError):
        InmetAdapter(source(min_severity="Vermelho"))


def test_each_state_becomes_its_own_event_on_the_map():
    payload = json.dumps({"hoje": [alert(1, "Perigo", kind="Acumulado de Chuva", estados="Minas Gerais,Espírito Santo,Rio de Janeiro")]}).encode()
    batch = run_once([source()], fetcher=lambda url: payload, now=NOW)
    assert sorted(e["state"] for e in batch["events"]) == ["ES", "MG", "RJ"]
    assert all(e["status"] == "CONFIRMED" for e in batch["events"])  # fonte oficial confirma
