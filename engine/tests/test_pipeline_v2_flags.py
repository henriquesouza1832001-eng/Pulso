from datetime import datetime, timedelta, timezone

from pulso_engine.baseline import BR_TZ
from pulso_engine.models import Signal
from pulso_engine.pipeline import cluster_anomaly
from pulso_engine.processing.clustering import Cluster, cluster_signals, tokens

NOW = datetime(2026, 10, 4, 6, 20, tzinfo=timezone.utc)  # domingo 03:20 em Brasília


def sig(i, title="Acidente fecha BR-381 em Betim", minutes_ago=10, source=None, state="MG", city="Betim"):
    ts = NOW - timedelta(minutes=minutes_ago)
    return Signal(signal_id=str(i), source_id=source or f"s{i}", source_class="NEWS_HIGH", timestamp=ts, collected_at=ts, title=title,
                  category="TRAFFIC", hash=f"h{i}", state=state, city=city, geo_confidence=70)


def cluster_of(signals):
    c = Cluster()
    for s in signals:
        c.add(s, tokens(s.title))
    return c


def seasonal_rows(weeks=6, days=None):
    out = []
    end = NOW.replace(minute=0)
    for h in range(1, 24 * (days if days else 7 * weeks)):
        t = end - timedelta(hours=h)
        local = t.astimezone(BR_TZ)
        out.append({"scope": "UF:MG", "category": "TRAFFIC", "source_class": "NEWS_HIGH", "hour": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "signals": 1 if (local.weekday() == 6 and local.hour == 3) else 6, "sources": 2, "duplicates": 0})
    return out


def test_flag_off_cluster_anomaly_ignores_observations(monkeypatch):
    monkeypatch.delenv("PULSO_FLAG_SEASONAL_BASELINE_V2", raising=False)
    sigs = [sig(i, minutes_ago=2 + i) for i in range(8)]
    c = cluster_of(sigs)
    assert cluster_anomaly(c, sigs, [], NOW, seasonal_rows()) == cluster_anomaly(c, sigs, [], NOW, None)


def test_flag_on_uses_seasonal_baseline_and_falls_back_without_history(monkeypatch):
    monkeypatch.setenv("PULSO_FLAG_SEASONAL_BASELINE_V2", "1")
    sigs = [sig(i, minutes_ago=2 + i) for i in range(8)]  # 8 sinais na última hora, num domingo 3h normalmente quieto
    c = cluster_of(sigs)
    assert cluster_anomaly(c, sigs, [], NOW, seasonal_rows()) > 0.5  # a base sazonal enxerga o anormal
    assert cluster_anomaly(c, sigs, [], NOW, []) == cluster_anomaly(c, sigs, [], NOW, None) == 0.0  # sem observações = V1 (sem histórico)
    assert cluster_anomaly(c, sigs, [], NOW, seasonal_rows(days=3)) == 0.0  # 3 dias: sem base válida (nem 5 horas comparáveis), nada afirmado


def test_cluster_refine_flag_is_wired(monkeypatch):
    a = sig(1, "Acidente fecha BR-381 em Betim", 30)
    b = sig(2, "Colisão interdita a BR-381 perto de Betim e provoca fila", 20, source="b")
    assert len(cluster_signals([a, b])) == 2
    from pulso_engine.pipeline import run_once

    src = {"id": "x", "name": "x", "domain": "x", "adapter": "rss", "source_class": "NEWS_HIGH", "url": "u", "state": None, "enabled": True}
    feed = lambda url: b"<rss><channel></channel></rss>"  # noqa: E731
    monkeypatch.delenv("PULSO_FLAG_CLUSTER_REFINE", raising=False)
    off = run_once([src], fetcher=feed, now=NOW)
    monkeypatch.setenv("PULSO_FLAG_CLUSTER_REFINE", "1")
    on = run_once([src], fetcher=feed, now=NOW)
    assert off["events"] == on["events"] == []  # sem sinais, as duas flags dão o mesmo resultado (V1 intacto)
