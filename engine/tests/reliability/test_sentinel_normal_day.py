"""Ataque de operação: volume normal e fontes diversas não devem parecer incidente."""
from datetime import datetime, timedelta, timezone

from pulso_engine.models import Signal
from pulso_engine.radar import analyze


NOW = datetime(2026, 10, 3, 16, tzinfo=timezone.utc)


def _normal_history(scope: str) -> list[dict]:
    return [
        {
            "scope": scope,
            "category": "WEATHER",
            "source_class": "NEWS_HIGH",
            "hour": (NOW.replace(minute=0) - timedelta(hours=hour)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            # 120/h corresponde exatamente a 30 sinais numa janela de 15 min.
            "signals": 120,
            "sources": 10,
            "duplicates": 0,
        }
        for hour in range(1, 24 * 10)
    ]


def _routine_burst() -> list[Signal]:
    classes = ("NEWS_HIGH", "NEWS_REGIONAL", "SOCIAL")
    return [
        Signal(
            signal_id=f"routine-{index}",
            source_id=f"routine-source-{index}",
            source_class=classes[index % len(classes)],
            timestamp=NOW - timedelta(minutes=index % 15),
            collected_at=NOW,
            title="Boletim rotineiro sem impacto",
            category="WEATHER",
            hash=f"routine-{index}",
            state="MG",
        )
        for index in range(30)
    ]


def test_normal_high_volume_three_source_types_currently_opens_two_false_investigations():
    """Caracterização P1: diversidade é gatilho mesmo com anomalia zero.

    A correção deve mudar esta expectativa para nenhuma investigação e manter
    o cenário como regressão de falso positivo operacional.
    """
    result = analyze(_routine_burst(), _normal_history("BR") + _normal_history("UF:MG"), [], NOW)
    assert {candidate.score for candidate in result["candidates"]} == {0.0}
    assert {(item.scope, item.category) for item in result["investigations"]} == {("BR", "WEATHER"), ("UF:MG", "WEATHER")}
    assert all(item.reasons == ("3 tipos de fonte",) for item in result["investigations"])
