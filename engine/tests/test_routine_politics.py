from datetime import datetime, timezone

from pulso_engine.events import ROUTINE_SEVERITY_CAP, stats_for
from pulso_engine.models import Signal
from pulso_engine.processing.importance import assess

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def sig(i, title, src):
    return Signal(signal_id=f"s{i}", source_id=src, source_class="NEWS_HIGH", timestamp=NOW, collected_at=NOW, title=title, text="",
                  url=f"https://x/{i}", category="POLITICS", reliability=70, hash=f"h{i}", canonical_url=f"https://x/{i}")


def test_campaign_rally_is_routine_but_disruption_is_not():
    assert assess("Comício de candidato reúne milhares na Avenida Paulista").routine
    assert assess("Carreata e caminhada marcam o último dia de campanha").routine
    assert not assess("Comício termina em tumulto e deixa feridos").routine
    assert not assess("Atirador abre fogo durante comício e deixa mortos").routine
    assert not assess("Senado aprova projeto de lei sobre segurança").routine


def test_routine_event_severity_is_capped_and_real_news_is_not():
    rally = stats_for([sig(1, "Comício de candidato reúne milhares em SP", "a"), sig(2, "Comício agita centro de SP com carreata", "b")], NOW)
    assert rally.severity <= ROUTINE_SEVERITY_CAP
    violent = stats_for([sig(3, "Comício termina em tumulto com feridos em SP", "a"), sig(4, "Tumulto em comício deixa feridos em SP", "b")], NOW)
    assert violent.severity > ROUTINE_SEVERITY_CAP
