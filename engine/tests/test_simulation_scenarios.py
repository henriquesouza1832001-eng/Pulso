import json

import pytest

from pulso_engine.backtest_events import backtest_event, false_positive_rate
from pulso_engine.intelligence.signatures import rank_signatures, sensor_of
from pulso_engine.radar import analyze
from pulso_engine.simulation import SCENARIOS, main, to_json

ALL = [f() for f in SCENARIOS.values()]


@pytest.mark.parametrize("sc", ALL, ids=lambda s: s.name)
def test_sentinel_behaves_as_expected(sc):
    out = analyze(sc.signals, sc.obs_rows, [], sc.t0)
    mine = [i for i in out["investigations"] if i.scope == sc.scope and i.category == sc.category]
    assert bool(mine) is sc.expect_detection
    if sc.expect_detection:
        assert mine[0].status == "NEW" and mine[0].reasons


@pytest.mark.parametrize("sc", [s for s in ALL if s.expect_detection], ids=lambda s: s.name)
def test_event_scenarios_give_positive_lead_time(sc):
    r = backtest_event(sc.signals, sc.obs_rows, sc.scope, sc.category, sc.t0)
    assert r["detected_before_t0"] and r["lead_time_min"] >= 10
    assert all(not c["triggered"] for c in r["checkpoints"] if c["offset_min"] <= -60)  # nada antes do primeiro sensor


def test_normal_day_has_no_false_positive_and_never_triggers():
    sc = SCENARIOS["normal_day"]()
    quiet = [sc.t0 - __import__("datetime").timedelta(minutes=30 * k) for k in range(1, 9)]
    assert false_positive_rate(sc.signals, sc.obs_rows, sc.scope, sc.category, quiet)["false_positives"] == 0


def test_flood_signature_matches_with_leading_sensor_first():
    sc = SCENARIOS["flood_bh"]()
    observed = [(sensor_of(s), s.timestamp.timestamp()) for s in sc.signals]
    ranked = {r["event_type"]: r for r in rank_signatures(observed, "WEATHER")}
    # a assinatura é ambígua entre FLOOD/LANDSLIDE/STORM (sensores compartilhados); FLOOD tem de estar entre as candidatas
    assert "FLOOD" in ranked and ranked["FLOOD"]["leading_before_confirming"] is True and ranked["FLOOD"]["lead_seconds"] > 0


def test_scenarios_are_deterministic_and_export_valid_json(capsys):
    assert [s.hash for s in SCENARIOS["flood_bh"]().signals] == [s.hash for s in SCENARIOS["flood_bh"]().signals]
    data = json.loads(to_json(SCENARIOS["flood_bh"]()))
    assert data["name"] == "flood_bh" and data["expect_detection"] is True and len(data["signals"]) == 35
    assert main(["blackout_sp"]) == 0 and json.loads(capsys.readouterr().out)["scope"] == "UF:SP"
    assert main(["nope"]) == 2
