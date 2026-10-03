"""Achados da SEGUNDA revisão independente (2026-10-03): cada um vira um teste que falha sem a correção."""
from datetime import datetime, timedelta, timezone

from pulso_engine.baseline import Baseline, ewma_baseline
from pulso_engine.models import Signal
from pulso_engine.pipeline import assign_event_ids, is_due
from pulso_engine.processing.clustering import Cluster
from pulso_engine.processing.geo import locate
from pulso_engine.processing.importance import brazil_relevant

T = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


# ---- 1) um id de evento por grupo, sem repetição, mesmo quando um evento gravado se divide ------------------------------
def cluster_of(*hashes, t0=0):
    c = Cluster()
    for i, h in enumerate(hashes):
        c.add(Signal(signal_id=h, source_id="s", source_class="NEWS_HIGH", timestamp=T + timedelta(minutes=t0 + i), collected_at=T,
                     title="t", hash=h), frozenset())
    return c


def test_a_split_event_does_not_give_the_same_id_to_two_groups():
    prior = {"a1": "ev-X", "a2": "ev-X", "a3": "ev-X", "b1": "ev-X"}  # o evento ev-X se dividiu em dois grupos
    big, small = cluster_of("a1", "a2", "a3"), cluster_of("b1", "n1", t0=5)
    ids = assign_event_ids([small, big], prior)
    assert ids[1] == "ev-X" and ids[0] is None  # fica com quem tem mais membros; o outro ganha id novo
    assert len({i for i in ids if i}) == len([i for i in ids if i])  # nenhum id repetido


def test_unrelated_prior_ids_are_kept_and_ties_go_to_the_oldest_group():
    assert assign_event_ids([cluster_of("a"), cluster_of("b")], {"a": "ev-1", "b": "ev-2"}) == ["ev-1", "ev-2"]
    tie = assign_event_ids([cluster_of("b1", t0=10), cluster_of("a1", t0=0)], {"a1": "ev-X", "b1": "ev-X"})
    assert tie == [None, "ev-X"]  # empate de membros: o grupo de sinal mais antigo mantém o id


# ---- 2) fonte muito lenta tem janela de duas rodadas (uma rodada atrasada não a faz perder 6 h) ------------------------
def test_very_slow_sources_run_in_two_consecutive_ticks():
    src = {"interval_s": 21600}
    base = datetime(2026, 10, 3, 6, 0, tzinfo=timezone.utc)  # fronteira de 6 h
    assert is_due(src, base) and is_due(src, base + timedelta(minutes=5))      # as duas rodadas da janela
    assert not is_due(src, base + timedelta(minutes=10)) and not is_due(src, base + timedelta(hours=3))
    quick = {"interval_s": 900}  # fontes de 15 min continuam com janela de uma rodada
    assert is_due(quick, base) and not is_due(quick, base + timedelta(minutes=5)) and is_due(quick, base + timedelta(minutes=15))


# ---- 3) nomes de cidade que também são pessoa/palavra só com contexto -----------------------------------------------------
def test_ambiguous_interior_city_names_need_context():
    for text in ["acidente de Marília Mendonça", "Picos de calor passam de 40 graus", "os patos do lago morreram",
                 "Olinda Dias lança livro", "Timon e Pumbaa voltam ao cinema", "em Marília Mendonça fez shows"]:
        assert locate(text) is None, text
    assert locate("chuva forte em Marília deixa desabrigados").uf == "SP"
    assert locate("prefeitura de Picos decreta emergência").uf == "PI"
    assert locate("temporal em Olinda derruba árvores").uf == "PE"
    assert locate("Patos, PB registra calor").uf == "PB"


# ---- 4) palavras brasileiras comuns não podem virar "outro país" -----------------------------------------------------------
def test_common_portuguese_words_and_brazilian_cities_are_not_foreign():
    for text in ["Franca registra chuva forte e deixa desabrigados", "A ira dos moradores cresce após o alagamento",
                 "O preço do peru de Natal sobe", "chuva forte atinge Franca"]:
        assert brazil_relevant(text, False), text
    for text in ["tempestade deixa mortos na França", "terremoto no Peru deixa feridos", "ataque no Irã deixa mortos",
                 "inundações na Índia e no Nepal"]:
        assert not brazil_relevant(text, False), text


# ---- 6) baseline esparso (quase só zeros) não vale como "normal" ---------------------------------------------------------
def test_sparse_history_is_not_a_valid_baseline_but_a_real_one_is():
    sparse = [0] * 11 + [3]  # 12 horas, só 1 com sinal: pode ser lacuna de coleta
    assert not ewma_baseline(sparse).valid
    assert not ewma_baseline([0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0]).valid  # 2 horas com dado em 16
    steady = [4, 5, 3, 6, 4, 5, 4, 3, 5, 6, 4, 5]
    assert ewma_baseline(steady).valid
    quiet_night = [0, 0, 0, 1, 2, 3, 4, 5, 4, 3, 2, 1, 0, 0]  # calmaria legítima mas com dados em boa parte das horas
    assert ewma_baseline(quiet_night).valid
    assert Baseline(1.0, 1.0, 20).valid is False  # sem data_hours informado: não presume validade
