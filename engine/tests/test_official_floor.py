from datetime import datetime, timedelta, timezone

from pulso_engine.events import OFFICIAL_ALERT_FLOOR, build_event
from pulso_engine.models import Signal
from pulso_engine.pipeline import run_once
from pulso_engine.processing.clustering import Cluster

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
ALERTS = frozenset({"defesa-civil-idap", "inmet-avisos"})


def cluster(source_id, category, cls="OFFICIAL", n=1):
    c = Cluster()
    for i in range(n):
        s = Signal(signal_id=f"s{i}", source_id=source_id, source_class=cls, timestamp=NOW - timedelta(minutes=5), collected_at=NOW,
                   title="Defesa Civil: Corridas de massa (extremo) em Manaus/AM", category=category, hash=f"h{i}", state="AM",
                   latitude=-3.1, longitude=-60.0, geo_confidence=70)
        c.add(s, frozenset())
    return c


def test_official_extreme_alert_never_stays_below_level_3_and_says_why():
    plain = build_event(cluster("defesa-civil-idap", "EMERGENCY"), NOW)  # sem a marcação de fonte de alerta
    ev = build_event(cluster("defesa-civil-idap", "EMERGENCY"), NOW, alert_sources=ALERTS)
    assert plain["alert_level"] < OFFICIAL_ALERT_FLOOR  # o score sozinho ainda não enxerga o perigo declarado
    assert ev["alert_level"] == OFFICIAL_ALERT_FLOOR
    assert ev["pulse"] == plain["pulse"]  # o piso não mexe no score
    extra = [b for b in ev["score_breakdown"] if b["key"] == "official_alert"]
    assert extra and extra[0]["points"] == 0 and "extremo" in extra[0]["label"]
    assert sum(b["points"] for b in ev["score_breakdown"]) == ev["pulse"]  # o "POR QUE?" continua somando o score


def test_floor_is_only_for_extreme_alerts_from_alert_sources():
    assert build_event(cluster("defesa-civil-idap", "WEATHER"), NOW, alert_sources=ALERTS)["alert_level"] < 3  # severidade menor
    assert build_event(cluster("gov-mdr", "EMERGENCY"), NOW, alert_sources=ALERTS)["alert_level"] < 3  # comunicado oficial qualquer
    assert build_event(cluster("g1", "EMERGENCY", cls="NEWS_HIGH"), NOW, alert_sources=ALERTS)["alert_level"] < 3  # notícia


def test_floor_never_lowers_a_higher_level():
    ev = build_event(cluster("defesa-civil-idap", "EMERGENCY", n=8), NOW, alert_sources=ALERTS)
    assert ev["alert_level"] >= OFFICIAL_ALERT_FLOOR


def test_pipeline_applies_it_from_the_alert_source_flag_in_the_config():
    xml = ("<rss><channel><item><title>Defesa Civil: desabamento deixa soterrados e desabrigados em Manaus</title>"
           "<link>https://x/a</link><pubDate>Sat, 03 Oct 2026 11:50:00 GMT</pubDate></item></channel></rss>").encode()

    def src(flag):
        return {"id": "defesa-civil-idap", "name": "DC", "domain": "mdr.gov.br", "state": None, "adapter": "rss",
                "source_class": "OFFICIAL", "url": "https://x/rss", **({"alert_source": True} if flag else {})}

    with_flag = run_once([src(True)], fetcher=lambda u: xml, now=NOW)["events"]
    without = run_once([src(False)], fetcher=lambda u: xml, now=NOW)["events"]
    assert with_flag and with_flag[0]["category"] == "EMERGENCY" and with_flag[0]["alert_level"] == OFFICIAL_ALERT_FLOOR
    assert without and without[0]["alert_level"] < OFFICIAL_ALERT_FLOOR
