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


@pytest.mark.parametrize("text,uf,city", [
    ("Homem é morto a tiros ao lado da filha em Ariquemes, RO", "RO", "Ariquemes"),
    ("Jovem é morta em SP após disparos", "SP", None),
    ("Deputado do PL (SP) apresenta projeto", "SP", None),
    ("Capotamento deixa ferido em Apucarana", "PR", "Apucarana"),
    ("Chuva forte em Campinas", "SP", "Campinas"),
    ("Duque de Caxias registra tiroteio", "RJ", "Duque de Caxias"),
    ("Enchente em Santos deixa desabrigados", "SP", "Santos"),
    ("Prefeito de Contagem é cassado", "MG", "Contagem"),
    ("Toledo, PR, decreta emergência", "PR", "Toledo"),
])
def test_interior_cities_and_uf_codes(text, uf, city):
    place = locate(text)
    assert place is not None and (place.uf, place.city, place.precision) == (uf, city, "STATE")


@pytest.mark.parametrize("text", [
    "Renan Santos diz que seguirá usando a música", "Santos vence o Corinthians", "Contagem de votos começa às 17h",
    "Suzano anuncia lucro", "PT anuncia candidatura", "Lula pede ao TSE suspensão",
])
def test_ambiguous_city_names_need_context(text):
    assert locate(text) is None
