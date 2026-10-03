"""A costura com o banco: investigação do Sentinela <-> linha da rota admin <-> campo `investigations` do ingest."""
import json
from datetime import datetime, timezone

from pulso_engine.investigations_io import investigation_dict, investigation_from_row
from pulso_engine.research.sentinel import Investigation

T = datetime(2026, 10, 3, 15, 0, tzinfo=timezone.utc)


def inv(**kw):
    base = dict(investigation_id="inv-ab12cd34ef", scope="UF:MG", category="WEATHER", status="NEW", started_at=T, last_update=T,
                initial_anomaly=0.7312345, anomaly=0.7312345, evidence_count=12, official_confirmation=True,
                reasons=("anomalia 0.73", "sinal oficial"), last_anomalous_at=T)
    return Investigation(**{**base, **kw})


def test_dict_matches_the_ingest_contract():
    d = investigation_dict(inv())
    assert set(d) == {"id", "scope", "category", "status", "started_at", "last_update", "last_anomalous_at", "initial_anomaly",
                      "anomaly", "evidence_count", "official_confirmation", "reasons"}
    assert d["started_at"] == "2026-10-03T15:00:00Z" and d["initial_anomaly"] == 0.7312 and d["official_confirmation"] is True
    assert investigation_dict(inv(last_anomalous_at=None))["last_anomalous_at"] is None
    assert len(investigation_dict(inv(reasons=tuple(str(i) for i in range(30))))["reasons"]) == 12  # teto do Worker (zod)


def test_from_row_handles_what_the_worker_returns():
    row = {"id": "inv-ab12cd34ef", "scope": "UF:MG", "category": "WEATHER", "status": "INVESTIGATING", "started_at": "2026-10-03T15:00:00Z",
           "last_update": "2026-10-03T15:30:00Z", "last_anomalous_at": "2026-10-03T15:25:00Z", "initial_anomaly": 0.7, "anomaly": 0.8,
           "evidence_count": 9, "official_confirmation": 1, "reasons": json.dumps(["a", "b"])}  # booleano 0/1 e reasons como texto JSON
    i = investigation_from_row(row)
    assert i.reasons == ("a", "b") and i.official_confirmation is True and i.last_anomalous_at.minute == 25
    assert investigation_from_row({**row, "reasons": "isto não é json", "last_anomalous_at": None}).reasons == ()
    assert investigation_from_row({**row, "last_anomalous_at": None}).last_anomalous_at is None


def test_roundtrip_keeps_the_state_machine_inputs():
    original = inv(status="RESOLVING")
    back = investigation_from_row({**investigation_dict(original), "official_confirmation": 1, "reasons": json.dumps(list(original.reasons))})
    assert (back.status, back.scope, back.evidence_count, back.last_anomalous_at) == ("RESOLVING", "UF:MG", 12, T)
