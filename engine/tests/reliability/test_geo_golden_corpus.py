"""Contrato do corpus adversarial de geo; métricas serão reportadas só com amostra suficiente."""
import json
from pathlib import Path


CASES = json.loads((Path(__file__).parents[1] / "golden" / "geo_cases.json").read_text(encoding="utf-8"))["cases"]


def test_geo_golden_corpus_has_positive_negative_and_false_precision_targets():
    assert len(CASES) >= 12
    expected = [case["expected"] for case in CASES]
    assert {value["precision"] for value in expected} == {"CITY", "STATE", "UNKNOWN"}
    assert sum(value["precision"] == "UNKNOWN" for value in expected) >= 8
    ids = {case["id"] for case in CASES}
    assert {"artist", "club", "airport", "road", "river", "neighborhood", "sao-jose-ambiguous"} <= ids


def test_geo_golden_labels_do_not_claim_a_city_when_the_headline_is_ambiguous():
    for case in CASES:
        expected = case["expected"]
        if expected["precision"] == "UNKNOWN":
            assert "city" not in expected and "state" not in expected
        if expected["precision"] == "CITY":
            assert expected["city"] and expected["state"]
