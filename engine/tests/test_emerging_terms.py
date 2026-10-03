from datetime import datetime, timedelta, timezone

from pulso_engine.intelligence.emerging_terms import emerging_terms
from pulso_engine.models import Signal

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def sig(i, title, minutes_ago, source=None):
    ts = NOW - timedelta(minutes=minutes_ago)
    return Signal(signal_id=str(i), source_id=source or f"s{i % 5}", source_class="NEWS_HIGH", timestamp=ts, collected_at=ts,
                  title=title, category="WEATHER", hash=f"h{i}")


def background(n=60):
    return [sig(1000 + i, f"Prefeitura anuncia obra número {i} na região metropolitana", 90 + i * 20) for i in range(n)]


def test_unregistered_place_emerges_and_known_keyword_is_flagged():
    recent = [sig(i, f"Alagamento em Vilarinho deixa moradores ilhados caso {i}", 5 + i * 3) for i in range(8)]
    found = emerging_terms(background() + recent, NOW)
    by = {e.term: e for e in found}
    assert "vilarinho" in by and by["vilarinho"].known is False and by["vilarinho"].score > 0.75
    assert "alagamento" in by and by["alagamento"].known is True


def test_single_source_repetition_is_not_emerging():
    recent = [sig(i, "Vilarinho sofre com alagamento", 5 + i, source="uma-so") for i in range(10)]
    assert emerging_terms(background() + recent, NOW) == []


def test_stable_terms_do_not_emerge():
    sigs = [sig(i, "Prefeitura anuncia obra na região metropolitana", 5 + i * 25) for i in range(70)]
    assert all(e.score < 0.3 for e in emerging_terms(sigs, NOW))


def test_no_reference_no_claim():
    recent = [sig(i, f"Alagamento em Vilarinho caso {i}", 5 + i) for i in range(8)]
    assert emerging_terms(recent, NOW) == []
    assert emerging_terms([], NOW) == []
