"""Cenários simulados e reproduzíveis para o Sentinela (§64): normal_day, flood_bh, blackout_sp, traffic_collapse_rj.

Determinísticos (sem aleatoriedade): o mesmo cenário gera sempre os mesmos sinais. Servem para rodar o motor e verificar o
comportamento esperado, nunca como dado real. Exporte para JSON com `py -m pulso_engine.simulation <cenario>`.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .models import Signal

T0 = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)  # domingo 12:00 em Brasília


@dataclass(frozen=True)
class Scenario:
    name: str
    t0: datetime  # "grande notícia" (ou o instante de referência, no dia normal)
    scope: str
    category: str
    signals: list[Signal]
    obs_rows: list[dict]  # histórico horário (signal_observations) das últimas 3 semanas
    expect_detection: bool  # o Sentinela DEVE investigar este cenário?
    note: str


def _sig(i: int, minutes_before: float, source: str, cls: str, category: str, state: str | None, title: str) -> Signal:
    ts = T0 - timedelta(minutes=minutes_before)
    return Signal(signal_id=f"sim-{i}", source_id=source, source_class=cls, timestamp=ts, collected_at=ts, title=title,
                  category=category, hash=f"sim-{i}", state=state, city=None, url=f"https://exemplo.invalid/{i}")


def _history(scope: str, category: str, per_hour: int = 3, days: int = 21) -> list[dict]:
    end = T0.replace(minute=0)
    return [{"scope": scope, "category": category, "source_class": "NEWS_HIGH",
             "hour": (end - timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ"), "signals": per_hour + (h % 3 == 0),
             "sources": 2, "duplicates": 0} for h in range(1, 24 * days)]


def _burst(start_id: int, n: int, first_min: float, last_min: float, category: str, state: str, title: str, cls="NEWS_REGIONAL") -> list[Signal]:
    step = (first_min - last_min) / max(1, n - 1)
    return [_sig(start_id + i, first_min - i * step, f"{cls.lower()}-{i % 9}", cls, category, state, f"{title} relato {i}") for i in range(n)]


def normal_day() -> Scenario:
    sigs = [_sig(i, 10 + i * 25, f"g{i}", "NEWS_HIGH", "WEATHER", "MG", f"Previsão do tempo para a semana {i}") for i in range(3)]
    return Scenario("normal_day", T0, "UF:MG", "WEATHER", sigs, _history("UF:MG", "WEATHER") + _history("BR", "WEATHER"), False,
                    "volume dentro do normal: nenhuma investigação")


def flood_bh() -> Scenario:
    sigs = [_sig(1, 47, "inmet-avisos", "OFFICIAL", "WEATHER", "MG", "INMET: aviso de chuvas intensas para Belo Horizonte"),
            _sig(2, 31, "bhtrans-simulado", "TRAFFIC_PROVIDER", "TRAFFIC", "MG", "Trânsito lento na avenida Cristiano Machado em Belo Horizonte"),
            _sig(3, 25, "bluesky-clima", "SOCIAL", "WEATHER", "MG", "Chuva forte alaga rua em Venda Nova"),
            _sig(4, 18, "defesa-civil-idap", "OFFICIAL", "WEATHER", "MG", "Defesa Civil alerta para alagamento em Belo Horizonte"),
            _sig(5, 8, "jornal-local", "NEWS_REGIONAL", "WEATHER", "MG", "Alagamento atinge Venda Nova e Vilarinho"),
            *_burst(10, 30, 14, 0, "WEATHER", "MG", "Alagamento em Belo Horizonte deixa vias interditadas")]
    return Scenario("flood_bh", T0, "UF:MG", "WEATHER", sigs, _history("UF:MG", "WEATHER") + _history("BR", "WEATHER"), True,
                    "sensor oficial 47 min antes da grande notícia; o Sentinela deve investigar com antecedência")


def blackout_sp() -> Scenario:
    sigs = [_sig(1, 40, "ons-ear", "OFFICIAL", "INFRASTRUCTURE", "SP", "ONS: perda de carga no subsistema Sudeste"),
            *_burst(10, 6, 30, 20, "INFRASTRUCTURE", "SP", "Moradores relatam falta de energia em São Paulo", "SOCIAL"),
            *_burst(30, 28, 15, 0, "INFRASTRUCTURE", "SP", "Apagão atinge zona sul de São Paulo")]
    return Scenario("blackout_sp", T0, "UF:SP", "INFRASTRUCTURE", sigs, _history("UF:SP", "INFRASTRUCTURE", 2) + _history("BR", "INFRASTRUCTURE", 2), True,
                    "sinal oficial de energia antes da onda de notícias")


def traffic_collapse_rj() -> Scenario:
    sigs = [_sig(1, 35, "inmet-avisos", "OFFICIAL", "WEATHER", "RJ", "INMET: chuva forte no Rio de Janeiro"),
            *_burst(10, 8, 28, 12, "TRAFFIC", "RJ", "Trânsito parado na Avenida Brasil", "TRAFFIC_PROVIDER"),
            *_burst(30, 30, 14, 0, "TRAFFIC", "RJ", "Engarrafamento histórico no Rio de Janeiro")]
    return Scenario("traffic_collapse_rj", T0, "UF:RJ", "TRAFFIC", sigs, _history("UF:RJ", "TRAFFIC") + _history("BR", "TRAFFIC"), True,
                    "trânsito anômalo precedido de aviso de chuva (categoria diferente)")


SCENARIOS = {f.__name__: f for f in (normal_day, flood_bh, blackout_sp, traffic_collapse_rj)}


def to_json(sc: Scenario) -> str:
    return json.dumps({
        "name": sc.name, "t0": sc.t0.strftime("%Y-%m-%dT%H:%M:%SZ"), "scope": sc.scope, "category": sc.category,
        "expect_detection": sc.expect_detection, "note": sc.note, "observations": sc.obs_rows,
        "signals": [{"hash": s.hash, "source_id": s.source_id, "source_class": s.source_class, "category": s.category,
                     "state": s.state, "title": s.title, "timestamp": s.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")} for s in sc.signals],
    }, ensure_ascii=False, indent=1)


def main(argv: list[str] | None = None) -> int:
    name = (argv if argv is not None else sys.argv[1:])[:1]
    if not name or name[0] not in SCENARIOS:
        print("uso: py -m pulso_engine.simulation <" + "|".join(SCENARIOS) + ">", file=sys.stderr)
        return 2
    print(to_json(SCENARIOS[name[0]]()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
