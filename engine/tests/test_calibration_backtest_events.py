from datetime import datetime, timedelta, timezone

from pulso_engine.backtest_events import backtest_event, dataset_rows, false_positive_rate
from pulso_engine.calibration import calibration_report
from pulso_engine.models import Signal

T0 = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def fc(p, outcome, method="m", version="1", status="resolved"):
    return {"method": method, "method_version": version, "probability": p, "outcome": outcome, "status": status}


def test_calibration_metrics_and_experimental_flag():
    fs = [fc(0.9, 1), fc(0.8, 1), fc(0.7, 0), fc(0.2, 0), fc(0.1, 1), fc(0.3, 0)]
    r = calibration_report(fs)[0]
    assert r["resolved"] == 6 and r["experimental"] is True
    assert r["precision"] == round(2 / 3, 4) and r["recall"] == round(2 / 3, 4) and r["false_positive_rate"] == round(1 / 3, 4)
    assert abs(r["brier"] - sum((p - o) ** 2 for p, o in [(0.9, 1), (0.8, 1), (0.7, 0), (0.2, 0), (0.1, 1), (0.3, 0)]) / 6) < 1e-5
    assert sum(c["n"] for c in r["calibration_curve"]) == 6


def test_groups_by_method_and_version_and_ignores_unresolved():
    fs = [fc(0.5, 1, version="1"), fc(0.5, 0, version="2"), fc(0.5, 1, status="open"), {"method": "m", "method_version": "1", "probability": 0.5, "status": "void", "outcome": None}]
    assert [(r["method_version"], r["resolved"]) for r in calibration_report(fs)] == [("1", 1), ("2", 1)]


def test_experimental_clears_with_enough_resolved():
    assert calibration_report([fc(0.6, i % 2) for i in range(100)])[0]["experimental"] is False


def sig(i, minutes_before_t0, cls="NEWS_HIGH", source=None):
    ts = T0 - timedelta(minutes=minutes_before_t0)
    return Signal(signal_id=str(i), source_id=source or f"s{i}", source_class=cls, timestamp=ts, collected_at=ts, title="t",
                  category="WEATHER", hash=f"h{i}", state="MG")


def history(per_hour=3, days=10):
    end = T0.replace(minute=0)
    return [{"scope": "BR", "category": "WEATHER", "source_class": "NEWS_HIGH", "hour": (end - timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "signals": per_hour, "sources": 2, "duplicates": 0} for i in range(1, 24 * days)]


def test_early_sensor_gives_lead_time_and_no_future_peeking():
    # sensor oficial 47 min antes do T0 e salva de notícias só perto do T0
    sigs = [sig(1, 47, "OFFICIAL", "inmet")] + [sig(10 + i, 5 + i % 4, source=f"n{i}") for i in range(30)]
    r = backtest_event(sigs, history(), "BR", "WEATHER", T0)
    assert r["detected_before_t0"] and r["first_trigger_offset_min"] == -30 and r["lead_time_min"] == 30
    before = [c for c in r["checkpoints"] if c["offset_min"] <= -60]
    assert not any(c["triggered"] for c in before)  # em T-1h o sinal oficial ainda não tinha acontecido


def test_undetected_event_has_no_lead_time():
    r = backtest_event([sig(1, 5, source="a")], history(), "BR", "WEATHER", T0)
    assert r["lead_time_min"] is None and not r["detected_before_t0"]


def test_false_positive_rate_on_quiet_windows():
    quiet = [T0 - timedelta(hours=h) for h in range(2, 8)]
    r = false_positive_rate([], history(), "BR", "WEATHER", quiet)
    assert r == {"windows": 6, "false_positives": 0, "false_positive_rate": 0.0}


def test_dataset_rows_shape():
    r = backtest_event([sig(1, 47, "OFFICIAL", "inmet")], history(), "BR", "WEATHER", T0)
    rows = dataset_rows(r, "ev-1", "CONFIRMED")
    assert len(rows) == 7 and {"timestamp", "location", "category", "value", "anomaly", "event_id", "event_outcome", "lead_time"} <= set(rows[0])
