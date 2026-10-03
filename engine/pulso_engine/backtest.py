"""Backtest em janela deslizante (walk-forward) do previsor de volume.

Para cada hora t, usa SÓ o passado (contagens até t) para prever "a hora t+1 terá >= T sinais?" e compara com o
que de fato ocorreu. Mede o erro (Brier) contra dois previsores ingênuos e devolve a curva de calibração.
Serve para provar que o método aprende algo do histórico e para recalibrar com dados reais depois que a coleta
acumular semanas. Em dados sintéticos prova a MECÂNICA; só dados reais provam acurácia (docs/architecture/PREDICTION.md).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .forecast import prob_at_least


@dataclass(frozen=True)
class BacktestResult:
    n: int
    brier_model: float
    brier_base_rate: float  # ingênuo 1: sempre a frequência histórica do evento
    brier_coin: float  # ingênuo 2: sempre 0,5
    reliability: list[tuple[float, float, int]]  # (prob. média prevista, frequência observada, n) por faixa

    @property
    def skill(self) -> float:
        """Ganho sobre o ingênuo da frequência: > 0 = melhor que ele; 0 = igual."""
        return 1 - self.brier_model / self.brier_base_rate if self.brier_base_rate else 0.0


def threshold_for(current: int) -> int:
    return max(math.ceil(current * 1.5), current + 3)


def walk_forward(counts: list[int], min_pairs: int = 24, bins: int = 5) -> BacktestResult:
    preds: list[tuple[float, int]] = []
    for t in range(min_pairs, len(counts) - 1):
        past = counts[: t + 1]
        deltas = [float(b - a) for a, b in zip(past, past[1:])]
        current = counts[t]
        thr = threshold_for(current)
        p, _, _, _ = prob_at_least(float(current), deltas, float(thr))
        preds.append((p, int(counts[t + 1] >= thr)))
    if not preds:
        return BacktestResult(0, 0.0, 0.0, 0.0, [])
    n = len(preds)
    # Referência ingênua JUSTA: a taxa de acerto observada ATÉ aquele ponto (com Laplace), sem espiar o futuro. Usar a
    # taxa da amostra inteira deixaria a referência otimista e o `skill` subestimado.
    hits_before = [0] * n
    for i in range(1, n):
        hits_before[i] = hits_before[i - 1] + preds[i - 1][1]
    bs = lambda f: sum((f(i) - o) ** 2 for i, (_, o) in enumerate(preds)) / n  # noqa: E731
    brier_model = sum((p - o) ** 2 for p, o in preds) / n
    rel = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        cell = [(p, o) for p, o in preds if lo <= p < hi or (b == bins - 1 and p == 1.0)]
        if cell:
            rel.append((sum(p for p, _ in cell) / len(cell), sum(o for _, o in cell) / len(cell), len(cell)))
    return BacktestResult(n, brier_model, bs(lambda i: (hits_before[i] + 1) / (i + 2)), bs(lambda i: 0.5), rel)
