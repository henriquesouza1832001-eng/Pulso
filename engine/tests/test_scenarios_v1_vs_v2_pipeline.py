"""Ponta a ponta V1 x V2 sobre os cenários simulados: roda `run_once` completo (sinais gravados + observações) com as flags V2
desligadas e ligadas e compara. O V1 é a referência: o V2 só pode acrescentar informação, nunca criar alarme num dia normal."""
import pytest

from pulso_engine.pipeline import run_once, signal_dict
from pulso_engine.simulation import SCENARIOS

V2_FLAGS = ("SEASONAL_BASELINE_V2", "CLUSTER_REFINE")


def run(sc, monkeypatch, v2):
    for f in V2_FLAGS:
        monkeypatch.setenv(f"PULSO_FLAG_{f}", "1" if v2 else "0")
    stored = [signal_dict(s) for s in sc.signals]
    return run_once([], now=sc.t0, stored=stored, obs_rows=sc.obs_rows, active_investigations=[])


def top(batch):
    return max(batch["events"], key=lambda e: e["pulse"], default=None)


@pytest.mark.parametrize("name", ["flood_bh", "blackout_sp", "traffic_collapse_rj"])
def test_event_scenarios_v2_never_scores_below_v1_and_sees_the_anomaly(name, monkeypatch):
    sc = SCENARIOS[name]()
    v1, v2 = run(sc, monkeypatch, False), run(sc, monkeypatch, True)
    assert top(v1) is not None and top(v2) is not None
    assert top(v2)["pulse"] >= top(v1)["pulse"]  # anomalia sazonal só soma pontos (V1 sem histórico em `series` não enxerga)
    assert any(b["key"] == "anomaly" for b in top(v2)["score_breakdown"])
    assert not any(b["key"] == "anomaly" for b in top(v1)["score_breakdown"])  # V1 sem série: nada afirmado
    # o Sentinela (shadow) abre a mesma investigação nos dois: independe das flags V2
    assert {(i["scope"], i["category"]) for i in v1["investigations"]} == {(i["scope"], i["category"]) for i in v2["investigations"]}
    assert any(i["scope"] == sc.scope and i["category"] == sc.category for i in v2["investigations"])


def test_normal_day_v2_does_not_invent_alarm(monkeypatch):
    sc = SCENARIOS["normal_day"]()
    v1, v2 = run(sc, monkeypatch, False), run(sc, monkeypatch, True)
    assert v2["investigations"] == [] and v1["investigations"] == []
    for batch in (v1, v2):
        assert all(e["alert_level"] <= 2 for e in batch["events"])
        assert all(not any(b["key"] == "anomaly" for b in e["score_breakdown"]) for e in batch["events"])


def test_breakdown_still_sums_to_score_in_v2(monkeypatch):
    for name in ("flood_bh", "blackout_sp"):
        for e in run(SCENARIOS[name](), monkeypatch, True)["events"]:
            assert sum(b["points"] for b in e["score_breakdown"]) == e["pulse"]
