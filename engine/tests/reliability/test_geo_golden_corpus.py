"""Contrato do corpus adversarial de geo; métricas serão reportadas só com amostra suficiente."""
import json
from pathlib import Path

from pulso_engine.processing.geo import locate
from pulso_engine.processing.geo_v2 import resolve


CASES = json.loads((Path(__file__).parents[1] / "golden" / "geo_cases.json").read_text(encoding="utf-8"))["cases"]


def test_geo_golden_corpus_has_positive_negative_and_false_precision_targets():
    assert len(CASES) >= 12
    expected = [case["expected"] for case in CASES]
    assert {value["precision"] for value in expected} == {"CITY", "STATE", "UNKNOWN", "DISPUTED"}
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


def geo_metrics(resolver):
    """Métricas explícitas do corpus editorial; não são evidência histórica de produção."""
    answers = [(case["expected"], resolver(case["text"])) for case in CASES]
    city = [(expected, answer) for expected, answer in answers if expected["precision"] == "CITY"]
    state = [(expected, answer) for expected, answer in answers if expected["precision"] in {"CITY", "STATE"}]
    unknown = [(expected, answer) for expected, answer in answers if expected["precision"] == "UNKNOWN"]
    disputed = [(expected, answer) for expected, answer in answers if expected["precision"] == "DISPUTED"]
    return {
        "city_accuracy": sum(bool(answer and answer.city == expected["city"] and answer.uf == expected["state"]) for expected, answer in city) / len(city),
        "state_accuracy": sum(bool(answer and answer.uf == expected["state"]) for expected, answer in state) / len(state),
        "unknown_rate": sum(answer is None for _, answer in answers) / len(answers),
        "false_precision_rate": sum(answer is not None for _, answer in unknown) / len(unknown),
        "disputed_city_rate": sum(answer is not None for _, answer in disputed) / len(disputed),
    }


def test_geo_v2_meets_the_current_adversarial_city_and_false_precision_regression_gate():
    v1, v2 = geo_metrics(locate), geo_metrics(resolve)
    assert v2["city_accuracy"] == 1.0
    assert v2["false_precision_rate"] == 0.0
    assert v2["city_accuracy"] > v1["city_accuracy"]
    assert v2["false_precision_rate"] <= v1["false_precision_rate"]
    # Rio Branco é deliberadamente DISPUTED: a resolução por dominância é
    # exposta como tal, não contada como acerto nem como falso positivo.
    assert v2["disputed_city_rate"] == 1.0
