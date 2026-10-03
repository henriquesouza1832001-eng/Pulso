from datetime import datetime, timedelta, timezone

from pulso_engine.models import Signal
from pulso_engine.research.sentinel import Investigation
from pulso_engine.research.validator import apply_validation, find_contradictions, validate

NOW = datetime(2026, 10, 4, 6, 20, tzinfo=timezone.utc)


def sig(i, title, cls="NEWS_HIGH", source=None, text=None):
    ts = NOW - timedelta(minutes=i)
    return Signal(signal_id=str(i), source_id=source or f"s{i}", source_class=cls, timestamp=ts, collected_at=ts, title=title,
                  category="TRAFFIC", hash=f"h{i}", text=text, url=f"https://x/{i}")


def inv(status="NEW"):
    return Investigation("inv-1", "UF:MG", "TRAFFIC", status, NOW, NOW, 0.7, 0.7, 1, False, (), NOW, ())


def test_copies_are_one_origin_not_many_confirmations():
    t = "Acidente interdita BR-381 em Betim sentido Belo Horizonte"
    v = validate(inv(), [sig(i, t) for i in range(1, 6)])
    assert v.independent_sources == 1 and v.copy_ratio == 0.8
    assert v.suggested_status == "INVESTIGATING"


def test_official_confirms():
    ms = [sig(1, "Acidente interdita BR-381 em Betim", cls="OFFICIAL", source="prf")]
    v = validate(inv(), ms)
    assert v.official_confirmation and v.suggested_status == "CONFIRMED"


def test_social_only_never_confirmed():
    ms = [sig(i, f"Acidente grave na BR-381 em Betim relato {i}", cls="SOCIAL") for i in range(1, 6)]
    v = validate(inv(), ms)
    assert v.suggested_status != "CONFIRMED" and not v.official_confirmation


def test_independent_news_confirm_without_official():
    ms = [sig(1, "Colisão interdita BR-381 em Betim", source="a"), sig(2, "Capotamento bloqueia a rodovia na região de Betim", source="b", cls="NEWS_REGIONAL"),
          sig(3, "Engavetamento complica trânsito na BR 381 perto de Betim", source="c")]
    assert validate(inv(), ms).suggested_status == "CONFIRMED"


def test_contradiction_is_recorded_with_official_side():
    a = sig(1, "Rodovia totalmente fechada após acidente em Betim", source="a")
    b = sig(2, "Uma faixa interditada após acidente em Betim", source="b")
    o = sig(3, "Bloqueio parcial na rodovia após acidente", cls="OFFICIAL", source="prf")
    found = find_contradictions([a, b, o])
    assert found[0]["topic"] == "extensão do bloqueio" and found[0]["official_side"] == "b"
    v = validate(inv(), [a, b, o])
    assert v.suggested_status == "DISPUTED" and v.contradiction_score == 0.5 and v.official_confirmation


def test_same_text_matching_both_sides_is_not_a_contradiction():
    assert find_contradictions([sig(1, "Sem feridos, mas 2 mortos? polícia nega")]) == []


def test_apply_does_not_reopen_closing_investigations():
    v = validate(inv(), [sig(1, "Acidente interdita BR-381 em Betim", cls="OFFICIAL", source="prf")])
    assert apply_validation(inv("CLOSED"), v).status == "CLOSED"
    assert apply_validation(inv("RESOLVING"), v).status == "RESOLVING"
    out = apply_validation(inv("INVESTIGATING"), v)
    assert out.status == "CONFIRMED" and out.official_confirmation
