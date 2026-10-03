"""Context engine: feriados ajustam a expectativa de "normal" (baseline/anomalia), nunca viram confirmação de nada.

Um feriado nacional tem tráfego e notícias de domingo: comparar uma terça-feira feriado com as terças normais geraria falsa
anomalia (ou esconderia uma real). Aqui o feriado é tratado como DOMINGO para escolher o histórico comparável. Os feriados
vêm da BrasilAPI (`/api/feriados/v1/<ano>`, aberta, sem autenticação; ficha em docs/sources/SOURCES.md): `parse_holidays` é
puro e `fetch_holidays` recebe o `fetcher` por injeção, então os testes rodam sem rede. Atrás da flag `CONTEXT_ENGINE`.
Sem calendário carregado o comportamento é o do baseline sazonal normal (sem inventar contexto).
"""
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, datetime

from ..baseline import BR_TZ, MIN_DATA_HOURS, MIN_SAMPLES_DOW_HOUR, MIN_SAMPLES_HOUR, SeasonalBaseline, INSUFFICIENT, _mean_std, seasonal_hourly

BRASILAPI_HOLIDAYS = "https://brasilapi.com.br/api/feriados/v1/{year}"
SUNDAY = 6


def parse_holidays(raw: bytes | str) -> dict[date, str]:
    """Resposta da BrasilAPI (lista de {date, name, type}) -> {data: nome}. Entrada malformada devolve {} (nunca derruba)."""
    try:
        items = json.loads(raw)
        return {date.fromisoformat(i["date"]): str(i.get("name", "")) for i in items if isinstance(i, dict) and "date" in i}
    except (ValueError, TypeError, KeyError):
        return {}


def fetch_holidays(years: list[int], fetcher: Callable[[str], bytes]) -> dict[date, str]:
    """Baixa os feriados dos anos pedidos. Falha em um ano não derruba os outros (esse ano fica sem calendário)."""
    out: dict[date, str] = {}
    for y in years:
        try:
            out.update(parse_holidays(fetcher(BRASILAPI_HOLIDAYS.format(year=y))))
        except Exception:  # noqa: BLE001 - fonte externa: calendário ausente = sem contexto, não erro
            continue
    return out


def effective_weekday(dt: datetime, holidays: dict[date, str]) -> int:
    """Dia da semana de Brasília (0 = segunda); feriado conta como domingo."""
    local = dt.astimezone(BR_TZ)
    return SUNDAY if local.date() in holidays else local.weekday()


def day_context(dt: datetime, holidays: dict[date, str]) -> dict:
    local = dt.astimezone(BR_TZ)
    return {"date": local.date().isoformat(), "holiday": holidays.get(local.date()), "weekday": local.weekday(),
            "effective_weekday": effective_weekday(dt, holidays)}


def contextual_baseline(rows: list[dict], scope: str, category: str, at: datetime, holidays: dict[date, str]) -> SeasonalBaseline:
    """Como `baseline.seasonal_baseline`, mas feriado vale por domingo, tanto em `at` quanto no histórico. Sem feriados
    carregados é idêntico ao sazonal comum; histórico insuficiente continua INSUFICIENTE (nada é inventado)."""
    series = seasonal_hourly(rows, scope, category, at)
    if not series or sum(1 for v in series.values() if v > 0) < max(MIN_DATA_HOURS, len(series) // 3):
        return INSUFFICIENT
    local = at.astimezone(BR_TZ)
    target_wd = effective_weekday(at, holidays)
    same_hour = [(h, v) for h, v in series.items() if h.astimezone(BR_TZ).hour == local.hour]
    same_slot = [v for h, v in same_hour if effective_weekday(h, holidays) == target_wd]
    for basis, values, minimum in (("dow_hour", same_slot, MIN_SAMPLES_DOW_HOUR), ("hour", [v for _, v in same_hour], MIN_SAMPLES_HOUR)):
        if len(values) >= minimum:
            mean, std = _mean_std(values)
            return SeasonalBaseline(mean, std, len(values), basis, sum(1 for v in values if v > 0), tuple(values))
    return INSUFFICIENT

