from datetime import datetime, timezone

from pulso_engine.intelligence.driver_validator import (affects_forecast, correlation_is_credible, evaluate, next_state,
                                                        registry_row)
from pulso_engine.validation import forecast_registry as reg
from pulso_engine.validation.metrics import (base_rate_reference, brier, calibration_error, classification,
                                             lead_time_summary, log_loss)
from pulso_engine.validation.shadow_compare import promotion_gate, shadow_row

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def test_metrics_basic_values_and_empty_is_none():
    assert brier([(1.0, 1), (0.0, 0)]) == 0 and brier([(0.5, 1)]) == 0.25 and brier([]) is None
    assert log_loss([(0.5, 1)]) == round(0.693147, 6) and log_loss([]) is None
    assert calibration_error([(0.9, 1)] * 9 + [(0.9, 0)]) == 0.0
    assert classification([(0.9, 1), (0.9, 0), (0.1, 1), (0.1, 0)]) == {"precision": 0.5, "recall": 0.5, "f1": 0.5, "fpr": 0.5}
    assert base_rate_reference([1, 0]) == 0.25


def test_lead_time_summary_counts_undetected():
    s = lead_time_summary([30, 10, None, 50])
    assert s["detected"] == 3 and s["coverage"] == 0.75 and s["median"] == 30 and s["events"] == 4
    assert lead_time_summary([None])["median"] is None


def rows(n, v2_better=True, scope="BR"):
    """V1 fraco (0,6/0,4); V2 bem calibrado: 0,8/0,2 acertando 80% das vezes (calibração, FPR e recall não pioram)."""
    out = []
    for i in range(n):
        grp, k = i % 2, (i // 2) % 5
        o = (1 if k else 0) if grp else (0 if k else 1)
        p1 = 0.6 if grp else 0.4
        p2 = (0.8 if grp else 0.2) if v2_better else p1
        out.append(shadow_row(f"f{i}", scope, "m", p1, p2, o))
    return out


def test_gate_blocks_small_samples_and_passes_clear_improvement():
    small = promotion_gate(rows(50))
    assert not small["passed"] and "INSUFFICIENT_DATA" in small["reasons"][0]
    ok = promotion_gate(rows(300))
    assert ok["passed"], ok["reasons"]
    assert ok["summary"]["gain_vs_v1"] > 0.15


def test_gate_blocks_no_improvement_and_scope_regression():
    flat = promotion_gate(rows(300, v2_better=False))
    assert not flat["passed"] and any("Brier sobre o V1" in r for r in flat["reasons"])
    mixed = rows(300) + [shadow_row(f"x{i}", "UF:MG", "m", 0.5, 0.9 if i % 2 == 0 else 0.1, i % 2) for i in range(40)]
    # em MG o V2 inverte o desfecho (pior que o V1): regressão por escopo
    assert any("UF:MG" in r for r in promotion_gate(mixed)["reasons"])


def test_registry_is_immutable_and_reproducible():
    fc = {"forecast_id": "fc-1", "probability": 0.62, "method": "pulse_empirical_delta", "method_version": "1", "scope": "BR", "threshold": 60.0}
    e = reg.build_entry(fc, {"current_score": 55.0, "pairs": 80}, NOW, "m1", "f1", "b1", {"PULSE_V2": False})
    assert reg.verify(e) and reg.reproduces(e, fc)
    assert not reg.reproduces(e, {**fc, "probability": 0.7})
    tampered = {**e, "snapshot": e["snapshot"].replace("0.62", "0.99")}
    assert not reg.verify(tampered)
    assert reg.new_entries([e], {"fc-1"}) == [] and reg.new_entries([e], set()) == [e]


def test_registry_defaults_to_current_flags():
    fc = {"forecast_id": "fc-2", "probability": 0.5, "method": "m", "method_version": "1", "scope": "BR", "threshold": 50.0}
    assert '"PULSE_V2":false' in reg.build_entry(fc, {}, NOW, "m", "f", "b")["snapshot"]


def test_false_driver_is_rejected_for_small_sample():
    assert not correlation_is_credible(0.95, 10)  # alta, mas só 10 pares
    assert not correlation_is_credible(0.2, 60)  # amostra ok, correlação fraca = ruído
    assert correlation_is_credible(0.6, 96)


def samples(n, better=True):
    out = []
    for i in range(n):
        o = i % 2
        out.append((0.5, (0.75 if o else 0.25) if better else 0.5, o))
    return out


def test_driver_lifecycle_and_only_active_affects_forecast():
    ev = evaluate(samples(150))
    assert ev["gain"] > 0.5
    assert next_state("TESTING", ev, True)[0] == "ACTIVE"
    assert next_state("CANDIDATE", evaluate(samples(20)), True)[0] == "TESTING"
    assert next_state("ACTIVE", evaluate(samples(150, better=False)), True)[0] == "DEGRADED"
    assert next_state("TESTING", ev, False)[0] == "CANDIDATE"
    assert next_state("DISABLED", ev, True)[0] == "DISABLED"
    assert affects_forecast("ACTIVE") and not any(affects_forecast(s) for s in ("CANDIDATE", "TESTING", "DEGRADED", "DISABLED"))


def test_registry_row_for_spurious_driver_stays_candidate():
    row = registry_row("WEATHER", "TRAFFIC", "BR", 2, 0.95, 10, samples(150))
    assert row["state"] == "CANDIDATE" and "sustentação" in row["reason"]
    good = registry_row("WEATHER", "TRAFFIC", "BR", 2, 0.6, 96, samples(150), "TESTING")
    assert good["state"] == "ACTIVE" and good["brier_with"] < good["brier_without"]
