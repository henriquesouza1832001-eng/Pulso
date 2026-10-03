"""Geo V2 (gazetteer IBGE): município certo, nunca o centro da capital, e 'não sei' quando é ambíguo."""
import json
from pathlib import Path

import pytest

from pulso_engine.processing import geo_v2
from pulso_engine.processing.geo_v2 import DATA, resolve

ROWS = json.loads(DATA.read_text(encoding="utf-8"))
BY_ID = {r["ibge_id"]: r for r in ROWS}


def test_dataset_is_complete_and_sourced():
    assert len(ROWS) == 5571 and len({r["ibge_id"] for r in ROWS}) == 5571
    assert {r["uf"] for r in ROWS} == set(geo_v2.UFS)
    assert all(-34 <= r["latitude"] <= 6 and -74 <= r["longitude"] <= -28 for r in ROWS)  # dentro do Brasil
    meta = json.loads(Path(str(DATA).replace(".json", ".meta.json")).read_text(encoding="utf-8"))
    assert meta["count"] == 5571 and "IBGE" in meta["license"] and meta["sha256"] and meta["sources"]


def test_interior_city_is_not_placed_at_the_state_capital():
    r = resolve("Temporal derruba árvores e alaga ruas em Ribeirão das Neves")
    assert (r.city, r.uf, r.geo_precision) == ("Ribeirão das Neves", "MG", "CITY")
    bh = BY_ID["3106200"]
    assert (r.latitude, r.longitude) != (bh["latitude"], bh["longitude"])
    assert abs(r.latitude - bh["latitude"]) < 1 and r.latitude != round(bh["latitude"], 4)  # perto de BH, mas é outro ponto
    r = resolve("Incêndio atinge mata em Brumadinho (MG), diz Bombeiros")
    assert (r.city, r.uf) == ("Brumadinho", "MG") and "UF MG citada junto ao nome" in r.geo_evidence


def test_common_words_are_not_cities_without_place_context():
    assert resolve("a serra estava coberta de neblina no natal") is None  # minúsculas
    assert resolve("Serra de Petrópolis registra neblina").city == "Petrópolis"  # "Serra" sozinha não é o município; Petrópolis (com "de") é
    assert resolve("Governo anuncia nova política de segurança") is None


def test_ambiguous_names_need_a_disambiguator_and_never_guess():
    assert resolve("Chuva forte em Bom Jesus deixa desabrigados") is None  # 4+ estados, nenhum domina
    assert resolve("Chuva forte em Bom Jesus (RS) deixa desabrigados").uf == "RS"
    assert resolve("Chuva forte em Bom Jesus, PB").uf == "PB"
    r = resolve("Chuva forte em Bom Jesus deixa desabrigados", source_state="PI")
    assert r.uf == "PI" and any("fonte regional" in e for e in r.geo_evidence)


def test_homonym_resolved_by_population_is_flagged_and_less_confident():
    r = resolve("Obras em Rio Branco afetam o trânsito")  # AC (390 mil) x MT (4 mil)
    assert (r.uf, r.ambiguous) == ("AC", True)
    explicit = resolve("Obras em Rio Branco (AC) afetam o trânsito")
    assert explicit.ambiguous is False and explicit.geo_confidence > r.geo_confidence


def test_confidence_reflects_evidence():
    assert resolve("Itaúna sofre com chuva forte") is None  # nome simples sem preposição de lugar nem UF: não localiza
    mid = resolve("Acidente em Itaúna deixa feridos")
    strong = resolve("Acidente em Itaúna, MG, deixa feridos", source_state="MG")
    assert strong.geo_confidence > mid.geo_confidence and strong.geo_confidence <= 95


def test_alias_and_all_caps_headline():
    assert resolve("Alagamento em Floripa interdita a Beira-Mar").uf == "SC"
    assert resolve("ACIDENTE GRAVE EM ITAÚNA, MG, DEIXA FERIDOS").city == "Itaúna"


def test_the_one_city_without_mesh_is_flagged():
    r = resolve("Chuva em Boa Esperança do Norte, MT")
    assert r.uf == "MT" and any("aproximada" in e for e in r.geo_evidence)
