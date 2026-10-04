"""Validação do NOISE_GATE OFF x ON (docs/reliability/NOISE_GATE_VALIDATION.md), em cima do corpus de
`pulso_engine.validation.noise_gate_corpus`. A varredura completa (todos os volumes, tabela) é o `__main__` do módulo;
aqui ficam as invariantes que não podem regredir, a 10 e 1000 itens.

- O gate NÃO pode resolver falso positivo criando falso negativo: todo positivo que passa desligado passa ligado.
- `xfail(strict=True)`: achados reais, abertos, fora do escopo do gate (QA-010, QA-011, QA-012). Quando o dono corrigir, o
  strict quebra a suíte e o marcador sai.
"""
import pytest

from pulso_engine.validation import noise_gate_corpus as C

BY_NAME = {s.name: s for s in C.scenarios()}
HARD = [f"{n}@{v}" for n in C.HARD_NEGATIVES for v in (10, 1000)]
POSITIVE = [s.name for s in BY_NAME.values() if s.group == "POSITIVE"]
QA010 = "SPORT_EVENT_SECURITY_INCIDENT@4"  # false split + categoria divergente: 4 relatos viram 3 eventos de N1


@pytest.mark.parametrize("name", HARD)
def test_gate_on_hard_negatives_never_reach_n2(name):
    m = C.measure(BY_NAME[name], gate=True)
    assert m["n2"] == 0, m
    assert m["events"] == 0 or m["gate_in_why"] or m["top"] <= 1  # o teto aparece no "POR QUE?"


@pytest.mark.parametrize("name", [
    pytest.param(n, marks=pytest.mark.xfail(strict=True, reason="QA-010: briga de torcida com feridos, 4 paráfrases -> 3 eventos N1"))
    if n == QA010 else n for n in POSITIVE])
def test_gate_on_positive_controls_reach_n2(name):
    assert C.measure(BY_NAME[name], gate=True)["n2"] >= 1


@pytest.mark.parametrize("name", POSITIVE)
def test_gate_never_loses_a_positive_that_worked_without_it(name):
    s = BY_NAME[name]
    off, on = C.measure(s, gate=False), C.measure(s, gate=True)
    assert on["n2"] >= 1 or off["n2"] == 0
    assert on["investigations"] == off["investigations"]  # o gate não mexe no Sentinela (sinais, não eventos)


def test_gate_recovers_incident_hidden_by_show_vocabulary():
    # "pane nos trens após show": com o gate, o termo operacional vence o papel de agenda e o evento é publicado.
    assert C.measure(BY_NAME["CONCERT_TRANSPORT_FAILURE@4"], gate=True)["n2"] >= 1


@pytest.mark.xfail(strict=True, reason="QA-012: em produção, o papel de agenda (PR #89) descarta 'pane nos trens após show' inteiro (0 eventos)")
def test_production_publishes_incident_in_show_vocabulary():
    assert C.measure(BY_NAME["CONCERT_TRANSPORT_FAILURE@4"], gate=False)["events"] >= 1


@pytest.mark.parametrize("name", ["CASCADE_1_5_50", "CASCADE_1_5_50_1000"])
def test_cascade_provenance_counts(name):
    on = C.measure(BY_NAME[name], gate=True)
    assert on["origin_count"] == 6 and on["independent_origin_count"] == 6
    assert on["publisher_count"] == 56
    # 1000 reposts sociais (literais, "URGENTE:", "RT") não somam nenhuma fonte com o gate
    assert on["max_sources"] <= on["publisher_count"]


@pytest.mark.xfail(strict=True, reason="QA-011: independência conta publisher, não origem (56 fontes para 1 fato); CONFIDENCE_V2 não está ligado")
def test_cascade_event_independence_is_bounded_by_origins():
    on = C.measure(BY_NAME["CASCADE_1_5_50_1000"], gate=True)
    assert on["max_sources"] <= on["independent_origin_count"]


@pytest.mark.parametrize("name", ["FALSE_MERGE", "FALSE_MERGE+CLUSTER_REFINE", "FALSE_SPLIT+CLUSTER_REFINE", "EVENT_DRIFT",
                                  "EVENT_RESURRECTION", "STALE_SENSOR", "OFFICIAL_CONFIRMATION",
                                  "OFFICIAL_DENIAL+EVENT_CONTRADICTION", "CONFLICTING_SENSORS+EVENT_CONTRADICTION",
                                  "RESOLUTION_IS_NOT_DISPUTE+EVENT_CONTRADICTION"])
@pytest.mark.parametrize("gate", [False, True])
def test_integrity_and_contradiction(name, gate):
    s = BY_NAME[name]
    assert s.passes(C.measure(s, gate)), name


def test_contradiction_lowers_confidence_and_is_explained():
    s = BY_NAME["OFFICIAL_DENIAL+EVENT_CONTRADICTION"]
    with C.flags_env(EVENT_CONTRADICTION=True):
        ev = C.execute(s.items())["events"][0]
    with C.flags_env():
        plain = C.execute(s.items())["events"][0]
    assert ev["status"] == "DISPUTED" and plain["status"] == "CONFIRMED"
    assert ev["confidence"] < plain["confidence"]
    assert any(b["key"] == "contradiction" for b in ev["score_breakdown"])


@pytest.mark.parametrize("gate", [False, True])
def test_less_coverage_never_raises_confidence(gate):
    with C.flags_env(NOISE_GATE=gate):
        curve = C.coverage_curve()
    confs = [m["max_conf"] for _, m in curve]
    assert confs == sorted(confs, reverse=True), curve
    assert curve[-1][1]["events"] == 0  # 0% de cobertura: nada observado, nada publicado (não vira "tudo normal" com evento)
