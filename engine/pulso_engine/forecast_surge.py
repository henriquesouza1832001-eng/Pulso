"""Previsões de VOLUME por categoria (NOWCAST): "haverá N ou mais sinais de <tema> na próxima hora?".

Mesma disciplina do previsor do Pulso (docs/architecture/PREDICTION.md): EXPERIMENTAL, probabilidade com
suavização de Laplace e intervalo de Wilson, registrada antes e pontuada depois (Brier), e SEM histórico
suficiente não se prevê nada.

  método    distribuição EMPÍRICA das variações hora a hora (contagem da hora seguinte menos a da hora)
            do próprio escopo x categoria, aplicada ao volume da última hora.
  cobre     qualquer categoria e escopo (BR ou UF) com atividade: clima, trânsito, saúde, política, economia...
  resolve   contando os sinais REAIS da janela, só se houver cobertura de coleta (sem lacuna disfarçada de calmaria).
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone

from .baseline import ewma_baseline, hourly_counts
from .drivers import leading_indicators
from .processing.event_types import active_precursors
from .forecast import HORIZON_MIN, VOID_AFTER_MIN, _iso, _scope_slug, _ts, brier, prob_at_least
from .series import BUCKET_MIN, bucket_start

METHOD = "signal_volume_empirical_delta"
VERSION = "1"
METRIC_PREFIX = "signals_"
MIN_PAIRS = 24  # pares de horas consecutivas exigidos (~1 dia de histórico contínuo)
MIN_ACTIVITY = 3  # sinais na última hora: sem atividade não há o que prever
MAX_SERIES = 12  # previsões por rodada, para o painel não virar ruído
MIN_COVERAGE_POINTS = 6  # pontos do Pulso na janela (cerca de 1 por ciclo de 5 min) para provar que a coleta rodou

LABELS = {
    "WEATHER": "clima", "TRAFFIC": "trânsito", "SECURITY": "segurança", "INFRASTRUCTURE": "infraestrutura",
    "PROTEST": "protestos", "POLITICS": "política", "ECONOMY": "economia", "HEALTH": "saúde",
    "INTERNATIONAL": "assuntos internacionais", "TECH": "tecnologia", "EVENT": "eventos", "EMERGENCY": "emergências",
}


def _parse_evidence(raw) -> dict:
    """A rota /api/admin/forecasts/open devolve `evidence` como texto JSON (coluna crua); o Engine reenvia a resolução
    junto com a evidência registrada, então ela precisa ser lida, e não descartada."""
    try:
        parsed = json.loads(raw) if isinstance(raw, (str, bytes)) else {}
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def merge_series(*groups: list[dict]) -> list[dict]:
    """Une linhas de série de várias origens; para a mesma (escopo, categoria, janela) vale o MAIOR valor."""
    merged: dict[tuple[str, str, str], dict] = {}
    for rows in groups:
        for r in rows:
            key = (r["scope"], r["category"], r["bucket"])
            if key not in merged or int(r["signals"]) > int(merged[key]["signals"]):
                merged[key] = r
    return list(merged.values())


def _ceil5(dt: datetime) -> datetime:
    """Próxima fronteira de janela de 5 min (o próprio instante, se já estiver alinhado)."""
    b = bucket_start(dt)
    return b if b == dt else b + timedelta(minutes=BUCKET_MIN)


def rolling_hour(rows: list[dict], scope: str, category: str, now: datetime) -> int:
    """Sinais nas 12 últimas janelas de 5 min COMPLETAS (a janela corrente ainda está aberta)."""
    end = bucket_start(now)
    start = end - timedelta(minutes=60)
    total = 0
    for r in rows:
        if r["scope"] == scope and r["category"] == category and start <= _ts(r["bucket"]) < end:
            total += int(r["signals"])
    return total


def _label(category: str) -> str:
    return LABELS.get(category, category.lower())


def _scope_text(scope: str) -> str:
    return "no Brasil" if scope == "BR" else f"em {scope.split(':')[1]}"


def make_surge_forecasts(rows: list[dict], now: datetime, events: list[dict] | None = None) -> list[dict]:
    """Novas previsões de volume. [] se não houver histórico (nunca se inventa)."""
    now = now.astimezone(timezone.utc)
    candidates = sorted({(r["scope"], r["category"]) for r in rows if r["category"] != "OTHER"})
    scored = []
    for scope, category in candidates:
        current = rolling_hour(rows, scope, category, now)
        if current >= MIN_ACTIVITY:
            scored.append((current, scope, category))
    scored.sort(reverse=True)
    out: list[dict] = []
    for current, scope, category in scored[:MAX_SERIES]:
        counts = hourly_counts(rows, scope, category, now, hours=72)
        base = ewma_baseline(counts)
        if not base.valid or len(counts) - 1 < MIN_PAIRS:
            continue
        deltas = [float(b - a) for a, b in zip(counts, counts[1:])]
        # Dois "espaços" por série e por hora, com id ESTÁVEL (o limiar muda a cada ciclo porque o volume muda; um id com o
        # limiar criaria uma previsão nova a cada rodada). A primeira da hora vale; as seguintes já estão abertas.
        slots = {"x15": max(math.ceil(current * 1.5), current + 3)}
        high = math.ceil(base.mean + 2 * base.std)
        if high > current and high != slots["x15"]:
            slots["hi"] = high
        for slot, t in slots.items():
            p, lo, hi, k = prob_at_least(float(current), deltas, float(t))
            out.append({
                "forecast_id": f"fc-surge-{_scope_slug(scope)}-{category.lower()}-{slot}-h{HORIZON_MIN}-{now.strftime('%Y%m%d%H')}",
                "kind": "NOWCAST",
                "question": f"Haverá {t} ou mais sinais de {_label(category)} {_scope_text(scope)} na próxima hora?",
                "scope": scope, "metric": f"{METRIC_PREFIX}{category.lower()}", "comparator": "gte", "threshold": float(t),
                "method": METHOD, "method_version": VERSION,
                "probability": round(p, 4), "interval_low": round(lo, 4), "interval_high": round(hi, 4),
                "horizon_minutes": HORIZON_MIN,
                "created_at": _iso(now), "resolves_at": _iso(now + timedelta(minutes=HORIZON_MIN)),
                "evidence": {
                    "current_hour_signals": current, "baseline_mean": round(base.mean, 2), "baseline_std": round(base.std, 2),
                    "history_hours": base.hours, "pairs": len(deltas), "hits": k,
                    "leading_indicators": leading_indicators(rows, category, scope, now),  # contexto; não altera p
                    # tipos de evento ativos que a hipótese editorial liga a esta categoria (config/event_types.json); só contexto
                    "event_types": active_precursors(events or [], category.upper(), scope),
                    "note": "variações hora a hora observadas no próprio histórico de sinais deste tema e escopo",
                },
                "status": "open", "outcome": None, "observed_value": None, "resolved_at": None, "brier": None,
            })
    return out


def resolve_surge_due(open_forecasts: list[dict], rows: list[dict], points: list[dict], now: datetime) -> list[dict]:
    """Resolve as previsões de volume vencidas com a contagem REAL; anula as sem cobertura de coleta."""
    now = now.astimezone(timezone.utc)
    pulse_times = [_ts(p["timestamp"]) for p in points]
    out: list[dict] = []
    for f in open_forecasts:
        if not str(f.get("metric", "")).startswith(METRIC_PREFIX):
            continue
        due = _ts(f["resolves_at"])
        created = _ts(f["created_at"])
        start = _ceil5(created)
        end = start + timedelta(minutes=HORIZON_MIN)
        if now < end + timedelta(minutes=BUCKET_MIN):  # espera a última janela fechar
            continue
        evidence = f["evidence"] if isinstance(f["evidence"], dict) else _parse_evidence(f["evidence"])
        base = {**f, "evidence": evidence}
        category = f["metric"][len(METRIC_PREFIX):].upper()
        covered = sum(1 for t in pulse_times if start <= t < end) >= MIN_COVERAGE_POINTS
        if covered:
            observed = sum(int(r["signals"]) for r in rows
                           if r["scope"] == f["scope"] and r["category"] == category and start <= _ts(r["bucket"]) < end)
            outcome = int(observed >= f["threshold"]) if f["comparator"] == "gte" else int(observed <= f["threshold"])
            out.append({**base, "status": "resolved", "outcome": outcome, "observed_value": float(observed),
                        "resolved_at": _iso(now), "brier": round(brier(f["probability"], outcome), 6)})
        elif (now - due).total_seconds() > VOID_AFTER_MIN * 60:
            out.append({**base, "status": "void", "outcome": None, "observed_value": None,
                        "resolved_at": _iso(now), "brier": None})
    return out
