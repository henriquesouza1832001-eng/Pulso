from datetime import datetime, timedelta, timezone

from pulso_engine.models import Signal
from pulso_engine.research.deep_search import DeepSearchBudget, deep_search
from pulso_engine.research.query_expansion import expand, place_terms, seed_terms
from pulso_engine.research.sentinel import Investigation

NOW = datetime(2026, 10, 4, 6, 20, tzinfo=timezone.utc)


def sig(i, title, cat="WEATHER", state="MG", city="Belo Horizonte", minutes_ago=10, cls="NEWS_HIGH", source=None):
    ts = NOW - timedelta(minutes=minutes_ago)
    return Signal(signal_id=str(i), source_id=source or f"s{i}", source_class=cls, timestamp=ts, collected_at=ts, title=title,
                  category=cat, hash=f"h{i}", state=state, city=city, url=f"https://x/{i}")


def inv(hashes, scope="UF:MG", cat="WEATHER"):
    return Investigation("inv-1", scope, cat, "NEW", NOW, NOW, 0.7, 0.7, len(hashes), False, ("anomalia",), NOW, tuple(hashes))


def test_expand_needs_place_and_caps():
    assert expand("WEATHER", []) == []
    qs = expand("TRAFFIC", ["Betim", "Contagem"], ["colisão"])
    assert len(qs) <= 12 and qs[0].term == "colisão" and {q.place for q in qs[:2]} == {"Betim", "Contagem"}
    assert len({q.text for q in qs}) == len(qs)


def test_seed_and_place_terms_from_signals():
    members = [sig(1, "Alagamento em Venda Nova", city="Venda Nova"), sig(2, "Enchente e alagamento", city="Venda Nova")]
    assert seed_terms("WEATHER", members)[0] == "alagamento"
    assert place_terms("UF:MG", members)[:2] == ["Venda Nova", "MG"]


def test_finds_new_independent_evidence_only_in_related_categories():
    members = [sig(1, "Alagamento em Venda Nova", city="Venda Nova")]
    pool = members + [
        sig(2, "Chuva causa alagamento em Venda Nova", cat="WEATHER", source="b"),
        sig(3, "Interdição na avenida por alagamento Venda Nova", cat="TRAFFIC", source="c"),
        sig(4, "Dólar sobe com alagamento Venda Nova no texto", cat="ECONOMY", source="d"),
        sig(5, "Alagamento em Venda Nova", state="SP", source="e"),
    ]
    res = deep_search(inv(["h1"]), pool, NOW, DeepSearchBudget(), members)
    assert {e["signal_hash"] for e in res.evidence} == {"h2", "h3"}  # sem a própria, sem economia, sem outra UF


def test_budget_caps_and_reports_skipped():
    members = [sig(1, "Alagamento em Venda Nova", city="Venda Nova")]
    b = DeepSearchBudget(max_queries_cycle=3)
    res = deep_search(inv(["h1"]), members, NOW, b, members)
    assert len(res.queries) == 3 and res.skipped_by_budget > 0 and b.used_cycle == 3
    again = deep_search(inv(["h1"]), members, NOW, b, members)
    assert again.queries == () and again.skipped_by_budget > 0  # teto do ciclo esgotado


def test_old_signals_ignored():
    members = [sig(1, "Alagamento em Venda Nova", city="Venda Nova")]
    old = sig(2, "Alagamento em Venda Nova", minutes_ago=24 * 60, source="b")
    res = deep_search(inv(["h1"]), members + [old], NOW, DeepSearchBudget(), members)
    assert res.evidence == ()


def test_no_place_no_search():
    m = [sig(1, "Alagamento", city=None)]
    res = deep_search(inv(["h1"], scope="BR"), m, NOW, DeepSearchBudget(), m)
    assert res.queries == () and res.evidence == ()
