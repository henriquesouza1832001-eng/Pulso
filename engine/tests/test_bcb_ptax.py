import json
from datetime import datetime, timezone

from pulso_engine.collectors.official.bcb_ptax import BcbPtaxAdapter
from pulso_engine.pipeline import run_once

NOW = datetime(2026, 10, 2, 18, 0, tzinfo=timezone.utc)  # 15:00 em Brasília
SRC = {"id": "bcb-ptax", "adapter": "bcb_ptax", "source_class": "OFFICIAL", "url": "https://olinda/PTAX/CotacaoDolarPeriodo"}


def body(*quotes):
    return json.dumps({"value": [{"cotacaoCompra": v - 0.0006, "cotacaoVenda": v, "dataHoraCotacao": t} for t, v in quotes]}).encode()


def run(*quotes, now=NOW, src=SRC):
    return BcbPtaxAdapter(src, None, lambda url: body(*quotes), lambda: now).run()


def test_shock_emits_one_official_economy_signal():
    (s,) = run(("2026-10-02 13:03:16.256632", 5.4900), ("2026-10-01 13:10:35.4469", 5.2079))
    assert s.category == "ECONOMY" and s.source_class == "OFFICIAL" and s.state is None
    assert s.title.startswith("Dólar sobe 5,4%") and "R$ 5,49" in s.title and "Banco Central" in s.title
    assert "R$ 5,2079" in s.text and s.timestamp == datetime(2026, 10, 2, 16, 3, 16, tzinfo=timezone.utc)


def test_drop_uses_the_right_verb_and_calm_day_emits_nothing():
    (s,) = run(("2026-10-02 13:03:16.256632", 5.00), ("2026-10-01 13:10:35.4469", 5.20))
    assert s.title.startswith("Dólar cai 3,8%")
    assert run(("2026-10-02 13:03:16.256632", 5.2238), ("2026-10-01 13:10:35.4469", 5.2079)) == []  # +0,3%: sem choque


def test_stale_quote_bad_rows_and_short_history_are_ignored():
    old = ("2026-09-25 13:03:16.256632", 5.60), ("2026-09-24 13:10:35.4469", 5.20)
    assert run(*old) == []  # choque antigo (mais de 48 h): não é notícia de agora
    assert run(("2026-10-02 13:03:16.256632", 5.5)) == []
    assert run(("lixo", 1.0), ("2026-10-02 13:03:16.256632", 5.5), ("2026-10-01 13:10:35.4469", 5.2))[0].category == "ECONOMY"


def test_hash_is_stable_per_quote_day_and_threshold_is_configurable():
    a = run(("2026-10-02 13:03:16.256632", 5.60), ("2026-10-01 13:10:35.4469", 5.20))[0]
    b = run(("2026-10-02 13:03:16.256632", 5.61), ("2026-10-01 13:10:35.4469", 5.20))[0]
    assert a.hash == b.hash
    assert run(("2026-10-02 13:03:16.256632", 5.2238), ("2026-10-01 13:10:35.4469", 5.2079), src={**SRC, "min_pct": 0.2})


def test_threshold_sources_are_online_not_degraded_when_nothing_happens():
    def fetch(url):
        return body(("2026-10-02 13:03:16.256632", 5.2238), ("2026-10-01 13:10:35.4469", 5.2079))
    base = {"name": "BCB", "domain": "bcb.gov.br", "state": None, **SRC}
    quiet = run_once([{**base, "quiet_ok": True}], fetcher=fetch, now=NOW)["source_health"][0]
    loud = run_once([base], fetcher=fetch, now=NOW)["source_health"][0]
    assert quiet["status"] == "ONLINE" and quiet["last_success"] is not None and "sem ocorrências" in quiet["detail"]
    assert loud["status"] == "DEGRADED" and loud["last_success"] is None
