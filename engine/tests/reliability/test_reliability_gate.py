from datetime import datetime, timezone

from pulso_engine.validation.reliability_gate import ReliabilityGate, ReliabilityMetrics


def metrics(samples=500, brier=0.2, fpr=0.1, recall=0.75, calibration=0.08):
    return ReliabilityMetrics(samples=samples, brier=brier, false_positive_rate=fpr, recall=recall, calibration_error=calibration)


def test_gate_returns_insufficient_data_without_a_pass():
    report = ReliabilityGate().evaluate("v2", metrics(samples=199), metrics(samples=199, brier=0.1))
    assert report.gate == "INSUFFICIENT_DATA" and report.reasons == ("insufficient_samples",)


def test_gate_passes_all_documented_rules_and_report_is_serializable():
    report = ReliabilityGate().evaluate("event_escalation_v2", metrics(), metrics(brier=0.16, fpr=0.105, recall=0.78, calibration=0.06),
                                       datetime(2026, 10, 3, tzinfo=timezone.utc))
    assert report.gate == "PASS" and report.delta["brier_skill"] == 0.2
    assert report.to_dict()["generated_at"].endswith("+00:00")


def test_gate_rejects_false_positive_regression_even_with_better_brier():
    report = ReliabilityGate().evaluate("v2", metrics(), metrics(brier=0.15, fpr=0.30, recall=0.78, calibration=0.06))
    assert report.gate == "FAIL" and "false_positive_regression" in report.reasons


def test_gate_rejects_recall_and_calibration_regressions():
    report = ReliabilityGate().evaluate("v2", metrics(), metrics(brier=0.15, fpr=0.1, recall=0.60, calibration=0.09))
    assert report.gate == "FAIL"
    assert set(report.reasons) == {"recall_regression", "calibration_regression"}
