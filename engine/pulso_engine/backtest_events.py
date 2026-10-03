"""Backtest de EVENTOS e lead time: o PULSO teria detectado? Quando? Quantos falsos positivos?

Reconstrói o que o Sentinela enxergaria em T-6h, T-3h, T-1h, T-30m, T-10m, T0 e T+30m de um evento histórico usando SÓ
os sinais publicados até cada instante (sem espiar o futuro), roda o mesmo detector do ciclo real e informa o primeiro
instante em que o gatilho dispararia. Lead time = T0 (a grande notícia) - primeiro disparo. Sem disparo antes de T0 o
lead time é None: o sistema não se atribui antecedência que não teve.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .models import Signal
from .research.sentinel import SentinelConfig, detect_candidates, should_investigate

CHECKPOINTS_MIN = (-360, -180, -60, -30, -10, 0, 30)


def _cell(signals: list[Signal], obs_rows: list[dict], scope: str, category: str, at: datetime, cfg: SentinelConfig):
    seen = [s for s in signals if s.timestamp <= at]
    for c in detect_candidates(seen, obs_rows, at, cfg):
        if c.scope == scope and c.category == category:
            go, reasons = should_investigate(c, cfg)
            return c, go, reasons, seen
    return None, False, (), seen


def backtest_event(signals: list[Signal], obs_rows: list[dict], scope: str, category: str, t0: datetime,
                   cfg: SentinelConfig = SentinelConfig(), checkpoints: tuple[int, ...] = CHECKPOINTS_MIN) -> dict:
    steps, first = [], None
    for off in checkpoints:
        at = t0 + timedelta(minutes=off)
        c, go, reasons, seen = _cell(signals, obs_rows, scope, category, at, cfg)
        classes = sorted({s.source_class for s in seen if s.category == category and at - s.timestamp <= timedelta(hours=1)})
        steps.append({"offset_min": off, "triggered": go, "anomaly": c.score if c else 0.0, "reasons": list(reasons),
                      "source_classes": classes, "signals_1h": c.signal_count if c else 0})
        if go and first is None:
            first = off
    lead = -first if first is not None and first < 0 else None
    return {"scope": scope, "category": category, "t0": t0.strftime("%Y-%m-%dT%H:%M:%SZ"), "checkpoints": steps,
            "first_trigger_offset_min": first, "lead_time_min": lead, "detected_before_t0": lead is not None,
            "detected_at_all": first is not None}


def false_positive_rate(signals: list[Signal], obs_rows: list[dict], scope: str, category: str, quiet_times: list[datetime],
                        cfg: SentinelConfig = SentinelConfig()) -> dict:
    """Em instantes SEM evento (controle), quantas vezes o gatilho disparou. Janelas sem sinal contam como negativas."""
    fired = sum(1 for t in quiet_times if _cell(signals, obs_rows, scope, category, t, cfg)[1])
    return {"windows": len(quiet_times), "false_positives": fired,
            "false_positive_rate": round(fired / len(quiet_times), 4) if quiet_times else None}


def dataset_rows(backtest: dict, event_id: str | None = None, outcome: str | None = None) -> list[dict]:
    """Linhas do dataset histórico (§39) a partir de um backtest: instante, escopo, categoria, valor, anomalia, resultado."""
    return [{"timestamp": s["offset_min"], "t0": backtest["t0"], "location": backtest["scope"], "category": backtest["category"],
             "value": s["signals_1h"], "anomaly": s["anomaly"], "triggered": s["triggered"], "event_id": event_id,
             "event_outcome": outcome, "lead_time": backtest["lead_time_min"]} for s in backtest["checkpoints"]]
