from pulso_engine.processing.importance import assess, brazil_relevant


def test_importance_ranks_disaster_above_gossip():
    assert assess("Enchente deixa 3 mortos e Defesa Civil emite alerta").is_important()
    assert not assess("Ronaldinho Gaúcho casou, famosos no casamento").is_important()
    assert assess("tem um acidente na esquina").score < 45  # contexto fraco sozinho não basta
    assert assess("enchente casou famosos").score < assess("enchente").score  # ruído penaliza


def test_foreign_events_are_dropped_but_unknown_brazilian_towns_are_kept():
    assert not brazil_relevant("Inundações e deslizamentos causam 70 mortes na Índia e no Nepal", False)
    assert brazil_relevant("Deslizamento em Petrópolis deixa mortos", False)
    assert brazil_relevant("Enchente atinge o Brasil inteiro, Brasil em alerta, como na Argentina", False)
