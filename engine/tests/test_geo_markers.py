import pytest

from pulso_engine.processing.geo import locate, state_place


@pytest.mark.parametrize("text,uf,precision", [
    ("Governo paulista anuncia corte", "SP", "STATE"),
    ("Alesp aprova projeto", "SP", "STATE"),
    ("TRE-MG cassa prefeito", "MG", "STATE"),
    ("Prefeito carioca é investigado", "RJ", "CITY"),
    ("Deputados sul-mato-grossenses se reúnem", "MS", "STATE"),
    ("Bancada mato-grossense", "MT", "STATE"),
    ("Eleitores potiguares vão às urnas", "RN", "STATE"),
    ("Protesto em Curitiba contra governador gaúcho", "PR", "CITY"),  # cidade explícita vence o gentílico
])
def test_state_political_markers(text, uf, precision):
    place = locate(text)
    assert place is not None and (place.uf, place.precision) == (uf, precision)


@pytest.mark.parametrize("text", ["Fluminense vence o Flamengo", "Correio Braziliense", "Alepo é bombardeada", "Tremor de terra"])
def test_ambiguous_markers_not_located(text):
    assert locate(text) is None


def test_state_place():
    assert state_place("SP").uf == "SP" and state_place("SP").precision == "STATE"
    assert state_place("XX") is None
