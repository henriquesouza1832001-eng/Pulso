import random

from pulso_engine.backtest import walk_forward


def bursty_series(n=400, seed=7):
    """Volume horário com nível lento que oscila e rajadas ocasionais (processo com memória)."""
    rng = random.Random(seed)
    level, out = 8.0, []
    for _ in range(n):
        level = max(1.0, 0.85 * level + 0.15 * 8 + rng.gauss(0, 1.5))
        burst = rng.random() < 0.06
        out.append(max(0, round(rng.gauss(level * (2.2 if burst else 1.0), 1.5))))
    return out


def test_model_beats_coin_flip_and_is_not_worse_than_base_rate():
    r = walk_forward(bursty_series())
    assert r.n > 300
    assert r.brier_model < r.brier_coin  # melhor que "50%"
    assert r.brier_model <= r.brier_base_rate * 1.05  # não pior que a frequência histórica (tolerância de 5%)


def test_probabilities_are_calibrated_where_there_is_data():
    r = walk_forward(bursty_series(n=900, seed=3))
    assert r.reliability
    for predicted, observed, n in r.reliability:
        if n >= 40:  # só faixas com amostra suficiente
            assert abs(predicted - observed) < 0.2, (predicted, observed, n)


def test_too_short_history_returns_empty_result():
    r = walk_forward([5, 6, 7, 8])
    assert r.n == 0 and r.reliability == []
