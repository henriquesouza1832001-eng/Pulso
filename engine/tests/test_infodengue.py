import json
from datetime import datetime, timezone

import pytest

from pulso_engine.collectors.official.infodengue import CAPITALS, InfoDengueAdapter

NOW = datetime(2026, 10, 3, 4, 0, tzinfo=timezone.utc)
SRC = {"id": "infodengue-capitais", "adapter": "infodengue", "source_class": "OFFICIAL", "url": "https://info.dengue.mat.br/api/alertcity"}


def week(se, nivel, est=120.0, inc=15.2, rt=1.3):
    return {"SE": se, "nivel": nivel, "casos_est": est, "casos_est_min": 90, "casos_est_max": 160, "p_inc100k": inc, "Rt": rt,
            "municipio_nome": "x"}


def run(levels, **src):
    """levels: {geocode: [linhas]}; capitais fora do mapa devolvem lista vazia."""
    def fetch(url):
        code = int(url.split("geocode=")[1].split("&")[0])
        return json.dumps(levels.get(code, [])).encode()
    return InfoDengueAdapter({**SRC, **src}, None, fetch, lambda: NOW).run()


def test_capitals_table_is_complete_and_unique():
    assert len(CAPITALS) == 27
    assert len({code for _, code in CAPITALS.values()}) == 27
    assert all(1_000_000 <= code <= 5_999_999 for _, code in CAPITALS.values())


def test_signal_only_for_orange_or_red_in_the_latest_week():
    bh, recife, manaus = CAPITALS["MG"][1], CAPITALS["PE"][1], CAPITALS["AM"][1]
    sigs = run({
        bh: [week(202637, 1), week(202638, 3)],        # semana mais recente laranja -> sinal
        recife: [week(202638, 2)],                      # amarelo -> não
        manaus: [week(202638, 4), week(202639, 1)],     # a MAIS RECENTE (39) é verde, mesmo com a 38 vermelha -> não
    })
    assert [s.state for s in sigs] == ["MG"]
    s = sigs[0]
    assert s.category == "HEALTH" and s.source_class == "OFFICIAL" and s.city == "Belo Horizonte"
    assert "alerta laranja" in s.title and "semana epidemiológica 38" in s.title
    assert "Casos estimados na semana: 120 (intervalo 90–160)" in s.text and "alerta modelado" in s.text
    assert s.latitude is not None and s.timestamp == NOW


def test_threshold_is_configurable_and_hash_is_stable_per_week_and_level():
    bh = CAPITALS["MG"][1]
    low = {bh: [week(202638, 2)]}
    assert run(low) == [] and len(run(low, min_level=2)) == 1
    a = run({bh: [week(202638, 3, est=100.0)]})[0]
    b = run({bh: [week(202638, 3, est=140.0)]})[0]
    c = run({bh: [week(202639, 3)]})[0]
    assert a.hash == b.hash and a.hash != c.hash  # mesma semana e nível = mesmo sinal; semana nova = sinal novo


def test_one_failing_capital_does_not_break_the_others_but_total_failure_is_an_error():
    bh = CAPITALS["MG"][1]

    def fetch(url):
        if f"geocode={bh}" not in url:
            raise OSError("fora do ar")
        return json.dumps([week(202638, 4)]).encode()

    sigs = InfoDengueAdapter(SRC, None, fetch, lambda: NOW).run()
    assert [s.state for s in sigs] == ["MG"] and "vermelho" in sigs[0].title

    def down(url):
        raise OSError("tudo fora do ar")

    with pytest.raises(OSError):
        InfoDengueAdapter(SRC, None, down, lambda: NOW).run()
    assert InfoDengueAdapter(SRC, None, lambda u: b"[]", lambda: NOW).run() == []  # sem dados: sem sinal
