from pulso_engine.processing.event_types import active_precursors, classify

EVENTS = [
    {"title": "Chuva forte causa alagamento em Recife", "state": "PE", "alert_level": 3},
    {"title": "Megaoperação policial no Rio deixa mortos", "state": "RJ", "alert_level": 4},
    {"title": "Brasil fecha embaixada e expulsa diplomata", "state": None, "alert_level": 3},
]


def test_classify_known_types_and_ignores_noise():
    assert "chuva_extrema" in classify("Temporal e alagamento em Recife")
    assert "operacao_policial" in classify("Megaoperação policial no Complexo")
    assert "crise_diplomatica" in classify("Governo fecha embaixada em Caracas")
    assert classify("Ben Affleck fala sobre vida amorosa") == []


def test_precursors_by_scope_and_target_category():
    br = active_precursors(EVENTS, "TRAFFIC", "BR")
    assert {p["type"] for p in br} == {"chuva_extrema", "operacao_policial"}
    assert all(p["status"] == "hipótese a validar" for p in br)
    assert [p["type"] for p in active_precursors(EVENTS, "TRAFFIC", "UF:PE")] == ["chuva_extrema"]
    assert [p["type"] for p in active_precursors(EVENTS, "POLITICS", "BR")] == ["crise_diplomatica"]
    assert active_precursors([], "TRAFFIC", "BR") == []


def test_precursor_never_changes_probability():
    """O catálogo é só evidência: a probabilidade sai do histórico, com ou sem eventos ativos."""
    from tests.test_drivers import NOW, to_rows, weather_leads_traffic

    from pulso_engine.forecast_surge import make_surge_forecasts

    weather, traffic = weather_leads_traffic()
    rows = to_rows(weather, "WEATHER") + to_rows(traffic, "TRAFFIC")
    with_ev = [f for f in make_surge_forecasts(rows, NOW, EVENTS) if f["metric"] == "signals_traffic"]
    without = [f for f in make_surge_forecasts(rows, NOW, []) if f["metric"] == "signals_traffic"]
    assert with_ev and [f["probability"] for f in with_ev] == [f["probability"] for f in without]
    assert all(f["evidence"]["event_types"] for f in with_ev) and not any(f["evidence"]["event_types"] for f in without)
