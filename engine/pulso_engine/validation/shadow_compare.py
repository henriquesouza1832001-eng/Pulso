"""Shadow compare: grava V1 x V2 x desfecho por previsão e aplica o PORTÃO DE PROMOÇÃO (docs/engineering/ENGINE_V2_PLAN.md §5).

O V2 roda em paralelo, sem afetar nada visível; cada linha guarda o que o V1 e o V2 previram e o que aconteceu. Nenhum V2
é promovido sem passar TODAS as condições: amostras, ganho de Brier sobre V1 e sobre o ingênuo, FPR e recall sob controle,
calibração sem piora e sem regressão grande por escopo. Falhar o portão devolve os motivos (nada de "quase passou").
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .metrics import base_rate_reference, brier, calibration_error, classification

MIN_SAMPLES = 200
MIN_BRIER_GAIN = 0.05  # 5% sobre o V1 E sobre o ingênuo
MAX_FPR_WORSENING = 0.10  # relativo
MAX_RECALL_DROP = 0.05  # absoluto
MAX_SCOPE_REGRESSION = 0.15  # um escopo com >= MIN_SCOPE_SAMPLES não pode ficar >15% pior em Brier
MIN_SCOPE_SAMPLES = 30


@dataclass(frozen=True)
class ShadowRow:
    item_id: str  # forecast_id ou event_id
    scope: str
    method: str
    p_v1: float
    p_v2: float
    outcome: int  # 0/1, só linhas já resolvidas entram na comparação


def shadow_row(item_id: str, scope: str, method: str, p_v1: float, p_v2: float, outcome: int) -> dict:
    """Linha pronta para gravar (dict simples; escrita condicional fica por conta de quem grava: id imutável)."""
    return {"item_id": item_id, "scope": scope, "method": method, "p_v1": round(p_v1, 4), "p_v2": round(p_v2, 4), "outcome": int(outcome)}


def _pairs(rows: list[dict], key: str) -> list[tuple[float, int]]:
    return [(r[key], r["outcome"]) for r in rows if r.get("outcome") in (0, 1)]


def compare(rows: list[dict]) -> dict:
    v1, v2 = _pairs(rows, "p_v1"), _pairs(rows, "p_v2")
    base = base_rate_reference([o for _, o in v1])
    b1, b2 = brier(v1), brier(v2)
    return {"samples": len(v1), "brier_v1": b1, "brier_v2": b2, "brier_baseline": base,
            "gain_vs_v1": round(1 - b2 / b1, 4) if b1 else None, "gain_vs_baseline": round(1 - b2 / base, 4) if base else None,
            "calibration_error_v1": calibration_error(v1), "calibration_error_v2": calibration_error(v2),
            "v1": classification(v1), "v2": classification(v2)}


def promotion_gate(rows: list[dict], min_samples: int = MIN_SAMPLES) -> dict:
    """{'passed': bool, 'reasons': [...], 'summary': compare(...)}. `reasons` lista TUDO que falhou."""
    s = compare(rows)
    reasons: list[str] = []
    if s["samples"] < min_samples:
        reasons.append(f"amostras insuficientes ({s['samples']} < {min_samples}): INSUFFICIENT_DATA")
    else:
        if s["gain_vs_v1"] is None or s["gain_vs_v1"] < MIN_BRIER_GAIN:
            reasons.append(f"ganho de Brier sobre o V1 < {MIN_BRIER_GAIN:.0%} ({s['gain_vs_v1']})")
        if s["gain_vs_baseline"] is None or s["gain_vs_baseline"] < MIN_BRIER_GAIN:
            reasons.append(f"ganho de Brier sobre o ingênuo < {MIN_BRIER_GAIN:.0%} ({s['gain_vs_baseline']})")
        f1, f2 = s["v1"]["fpr"], s["v2"]["fpr"]
        if f1 is not None and f2 is not None and f2 > f1 * (1 + MAX_FPR_WORSENING) and f2 > f1:
            reasons.append(f"FPR piorou além de {MAX_FPR_WORSENING:.0%} ({f1} -> {f2})")
        r1, r2 = s["v1"]["recall"], s["v2"]["recall"]
        if r1 is not None and (r2 is None or r2 < r1 - MAX_RECALL_DROP):
            reasons.append(f"recall caiu mais de {MAX_RECALL_DROP:.0%} ({r1} -> {r2})")
        e1, e2 = s["calibration_error_v1"], s["calibration_error_v2"]
        if e1 is not None and e2 is not None and e2 > e1:
            reasons.append(f"erro de calibração piorou ({e1} -> {e2})")
        by_scope: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            by_scope[r["scope"]].append(r)
        for scope, rs in sorted(by_scope.items()):
            if len(rs) < MIN_SCOPE_SAMPLES:
                continue
            sb1, sb2 = brier(_pairs(rs, "p_v1")), brier(_pairs(rs, "p_v2"))
            if sb1 and sb2 > sb1 * (1 + MAX_SCOPE_REGRESSION):
                reasons.append(f"regressão em {scope}: Brier {sb1} -> {sb2}")
    return {"passed": not reasons, "reasons": reasons, "summary": s}
