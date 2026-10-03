import json
from datetime import datetime, timezone

from pulso_engine.collectors.registry import build_adapter
from pulso_engine.processing.importance import assess

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
SRC = {"id": "x-impacto", "adapter": "x", "source_class": "SOCIAL", "url": "https://api.x.com/2/tweets/search/recent"}

BODY = {
    "data": [
        {"id": "1", "text": "Enchente em Blumenau: 3 mortos e dezenas de desabrigados, Defesa Civil em alerta", "created_at": "2026-10-02T11:40:00Z", "author_id": "u1"},
        {"id": "2", "text": "Ronaldinho Gaúcho casou! Veja os famosos no casamento", "created_at": "2026-10-02T11:50:00Z", "author_id": "u2"},
        {"id": "3", "text": "Deslizamento em Petrópolis atinge casas", "created_at": "2026-10-02T11:55:00Z", "author_id": "u3"},
        {"id": "4", "text": "bom dia, hoje o dia está lindo", "created_at": "2026-10-02T11:56:00Z", "author_id": "u2"},
    ],
    "includes": {"users": [{"id": "u1", "username": "defesacivil_sc", "verified": True}, {"id": "u3", "username": "fulano", "verified": False}]},
}


def run(body):
    return build_adapter(SRC, None, lambda url: json.dumps(body).encode(), lambda: NOW).run()


def test_importance_ranks_disaster_above_gossip():
    assert assess("Enchente deixa 3 mortos e Defesa Civil emite alerta").is_important()
    assert not assess("Ronaldinho Gaúcho casou, famosos no casamento").is_important()
    assert assess("tem um acidente na esquina").score < 45  # contexto fraco sozinho não basta
    assert assess("enchente casou famosos").score < assess("enchente").score  # ruído penaliza


def test_x_keeps_only_important_signals():
    sigs = run(BODY)
    assert {s.url.rsplit("/", 1)[1] for s in sigs} == {"1", "3"}


def test_x_signal_fields_and_privacy():
    by_id = {s.url.rsplit("/", 1)[1]: s for s in run(BODY)}
    verified, anon = by_id["1"], by_id["3"]
    assert verified.source_class == "SOCIAL_VERIFIED" and verified.author == "defesacivil_sc"
    assert anon.source_class == "SOCIAL" and anon.author is None  # sem perfil de pessoa comum
    assert verified.reliability > anon.reliability
    assert verified.timestamp <= NOW


def test_x_empty_response_is_not_an_error():
    assert run({"meta": {"result_count": 0}}) == []


def test_foreign_events_are_dropped_but_unknown_brazilian_towns_are_kept():
    from pulso_engine.processing.importance import brazil_relevant
    assert not brazil_relevant("Inundações e deslizamentos causam 70 mortes na Índia e no Nepal", False)
    assert brazil_relevant("Deslizamento em Petrópolis deixa mortos", False)
    assert brazil_relevant("Enchente atinge o Brasil inteiro, Brasil em alerta, como na Argentina", False)
