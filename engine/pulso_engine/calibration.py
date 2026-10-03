"""Calibração das previsões resolvidas: Brier, curva de confiabilidade, precision, recall e taxa de falso positivo.

Função pura sobre previsões já resolvidas (`status == "resolved"`, `outcome` 0/1, `probability`). Agrupa por método E
versão (uma versão nova recomeça do zero e do selo EXPERIMENTAL). Uma previsão é "positiva" quando a probabilidade
prevista é >= `cutoff` (0,5 por padrão); isso mede a utilidade como alarme, enquanto Brier e a curva medem a calibração.
"""
from __future__ import annotations

MIN_RESOLVED = 100  # abaixo disso o método continua EXPERIMENTAL (mesmo limiar da API)
BINS = 5


def _rate(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def calibration_report(forecasts: list[dict], cutoff: float = 0.5, bins: int = BINS) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = {}
    for f in forecasts:
        if f.get("status") == "resolved" and f.get("outcome") in (0, 1):
            groups.setdefault((f["method"], str(f["method_version"])), []).append(f)
    out = []
    for (method, version), fs in sorted(groups.items()):
        n = len(fs)
        tp = sum(1 for f in fs if f["probability"] >= cutoff and f["outcome"] == 1)
        fp = sum(1 for f in fs if f["probability"] >= cutoff and f["outcome"] == 0)
        fn = sum(1 for f in fs if f["probability"] < cutoff and f["outcome"] == 1)
        tn = n - tp - fp - fn
        curve = []
        for b in range(bins):
            lo, hi = b / bins, (b + 1) / bins
            cell = [f for f in fs if lo <= f["probability"] < hi or (b == bins - 1 and f["probability"] == 1.0)]
            if cell:
                curve.append({"predicted": round(sum(f["probability"] for f in cell) / len(cell), 4),
                              "observed": round(sum(f["outcome"] for f in cell) / len(cell), 4), "n": len(cell)})
        out.append({
            "method": method, "method_version": version, "resolved": n,
            "brier": round(sum((f["probability"] - f["outcome"]) ** 2 for f in fs) / n, 6),
            "precision": _rate(tp, tp + fp), "recall": _rate(tp, tp + fn), "false_positive_rate": _rate(fp, fp + tn),
            "cutoff": cutoff, "calibration_curve": curve,
            "experimental": n < MIN_RESOLVED,  # sempre explícito: método sem acertos suficientes não é "fato"
        })
    return out
