from datetime import datetime, timedelta, timezone

from pulso_engine.anomaly import anomaly_score, zscore
from pulso_engine.baseline import MIN_HOURS, Baseline, ewma_baseline, hourly_counts
from pulso_engine.models import Signal
from pulso_engine.pipeline import chunks, run_once
from pulso_engine.series import build_series, bucket_start

NOW = datetime(2026, 10, 3, 12, 30, tzinfo=timezone.utc)


def rows(per_hour: list[int], scope="BR", cat="WEATHER"):
    """Gera linhas de série de 5 min: per_hour[0] é a hora mais antiga, terminando na hora anterior a NOW."""
    out = []
    start = NOW.replace(minute=0, second=0, microsecond=0) - timedelta(hours=len(per_hour))
    for i, n in enumerate(per_hour):
        out.append({"scope": scope, "category": cat, "bucket": (start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "signals": n, "sources": 1})
    return out


def sig(minutes_ago: int, state="MG", cat="WEATHER", src="a", i=0) -> Signal:
    ts = NOW - timedelta(minutes=minutes_ago)
    return Signal(signal_id=f"s{i}", source_id=src, source_class="NEWS_HIGH", timestamp=ts, collected_at=NOW,
                  title=f"t{i}", category=cat, state=state, hash=f"h{i}")


def test_bucket_rounds_down_to_5_minutes():
    assert bucket_start(datetime(2026, 10, 3, 12, 37, 59, tzinfo=timezone.utc)).minute == 35


def test_series_counts_per_scope_category_and_distinct_sources():
    s = [sig(2, i=1, src="a"), sig(3, i=2, src="b"), sig(1, i=3, src="a"), sig(2, i=4, cat="OTHER")]
    pts = {(p["scope"], p["category"]): p for p in build_series(s, NOW)}
    assert pts[("BR", "WEATHER")]["signals"] == 3 and pts[("BR", "WEATHER")]["sources"] == 2
    assert ("UF:MG", "WEATHER") in pts
    assert not any(p["category"] == "OTHER" for p in pts.values())  # sem categoria não entra


def test_baseline_invalid_without_enough_history_so_no_fake_anomaly():
    base = ewma_baseline(hourly_counts(rows([2, 3, 2]), "BR", "WEATHER", NOW))
    assert not base.valid and base.hours < MIN_HOURS
    assert anomaly_score(500, base) == 0.0


def test_flat_history_then_spike_is_anomalous():
    base = ewma_baseline(hourly_counts(rows([3] * 24), "BR", "WEATHER", NOW))
    assert base.valid and 2.9 < base.mean < 3.1
    assert anomaly_score(3, base) == 0.0  # normal
    assert anomaly_score(40, base) == 1.0  # muito acima
    assert anomaly_score(7, base) == 1.0  # +4 desvios = saturação
    assert 0 < anomaly_score(5, base) < 1.0  # +2 desvios = anomalia moderada


def test_below_normal_is_not_anomaly_and_zscore_is_signed():
    base = Baseline(mean=10, std=2, hours=24)
    assert anomaly_score(2, base) == 0.0 and zscore(2, base) < 0


def test_current_hour_is_excluded_from_baseline():
    r = rows([3] * 24) + [{"scope": "BR", "category": "WEATHER", "bucket": "2026-10-03T12:05:00Z", "signals": 999, "sources": 1}]
    assert max(hourly_counts(r, "BR", "WEATHER", NOW)) == 3


def test_run_once_uses_history_and_emits_series():
    import pulso_engine.pipeline as pl  # noqa: F401
    from tests.test_pipeline import rss, src  # reutiliza utilitários

    titles = [f"Temporal causa alagamento em Belo Horizonte relato {k} bairro" for k in range(6)]
    feeds = {f"https://s{n}.com/rss": rss((titles[n], f"https://s{n}.com/{n}", 5 + n)) for n in range(3)}
    feeds = {u: b.replace(b"2026", b"2026") for u, b in feeds.items()}
    sources = [src(f"s{n}") for n in range(3)]
    now = datetime(2026, 10, 2, 20, 0, tzinfo=timezone.utc)
    calm = [{"scope": "UF:MG", "category": "WEATHER", "bucket": (now.replace(minute=0) - timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "signals": 0 if h % 2 else 1, "sources": 1} for h in range(1, 30)]
    with_hist = run_once(sources, lambda u: feeds[u], now, history=calm)
    without = run_once(sources, lambda u: feeds[u], now, history=[])
    ev_h, ev_n = with_hist["events"][0], without["events"][0]
    assert ev_h["pulse"] > ev_n["pulse"]  # a anomalia vs. baseline aumentou o Pulso
    assert any(b["key"] == "anomaly" for b in ev_h["score_breakdown"])
    assert not any(b["key"] == "anomaly" for b in ev_n["score_breakdown"])
    assert with_hist["series"] and chunks(with_hist)[-1]["series"]
