"""Radar: ponto de entrada do ciclo do Sentinela (`python -m pulso_engine.radar`).

`analyze` é a camada de análise pura (tendências, anomalias, Sentinela) que roda DEPOIS da coleta/dedup/geo e ANTES do
envio; `pipeline.run_once` continua o núcleo de coleta, agrupamento, pontuação e previsão. A integração de `analyze` ao
`run_once` fica com quem mantém o pipeline (ver docs/research/SPEC_05_SENTINEL.md). Sem LLM no caminho crítico.
"""
from __future__ import annotations

from datetime import datetime

from .intelligence.trends import trends
from .models import Signal
from .research.sentinel import Investigation, SentinelConfig, advance, detect_candidates, should_investigate


def analyze(signals: list[Signal], obs_rows: list[dict], active: list[Investigation], now: datetime,
            cfg: SentinelConfig = SentinelConfig(), duplicates_by_hash: dict[str, int] | None = None,
            emerging: dict[tuple[str, str], float] | None = None) -> dict:
    """Devolve candidatos, motivos de disparo, tendência nacional e SÓ as investigações que mudaram."""
    candidates = detect_candidates(signals, obs_rows, now, cfg, emerging, duplicates_by_hash)
    return {
        "candidates": candidates,
        "triggered": [(c.scope, c.category, should_investigate(c, cfg)[1]) for c in candidates if should_investigate(c, cfg)[0]],
        "trends_br": trends(signals, now, duplicates_by_hash),
        "investigations": advance(active, candidates, now, cfg),
    }


def main(argv: list[str] | None = None) -> int:
    from .pipeline import main as pipeline_main  # a coleta e o envio seguem no pipeline

    return pipeline_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
