"""Achados da revisão focada no pipeline (2026-10-03): cada um vira um teste que falha sem a correção."""
import json
from datetime import datetime, timedelta, timezone

from pulso_engine.pipeline import DEFAULT_SOURCES, chunks, health_due, is_due, select_health

T0 = datetime(2026, 10, 3, 0, 0, tzinfo=timezone.utc)


def real_sources():
    return [s for s in json.loads(DEFAULT_SOURCES.read_text(encoding="utf-8")) if s.get("enabled", True)]


# ---- 1) o deslocamento por fonte não pode tirar a fonte do seu horário de saúde ---------------------------------------------------
def test_every_active_source_reports_online_health_regularly_with_the_real_config():
    sources = real_sources()
    ticks = 12 * 12  # 12 horas de rodadas de 5 min
    reports = {s["id"]: [] for s in sources}
    for k in range(ticks):
        now = T0 + timedelta(minutes=5 * k)
        for s in sources:
            if is_due(s, now) and health_due(s, now):
                reports[s["id"]].append(k)
    for s in sources:
        r = reports[s["id"]]
        assert r, f"{s['id']} nunca reporta saúde"
        gaps = [b - a for a, b in zip(r, r[1:])]
        limit = max(6, s["interval_s"] // 300) + 2  # ~30 min, ou o intervalo da fonte se for mais lento
        assert all(g <= limit for g in gaps), (s["id"], gaps)


def test_health_is_only_reported_on_rounds_where_the_source_actually_runs():
    for s in real_sources():
        for k in range(144):
            now = T0 + timedelta(minutes=5 * k)
            if health_due(s, now):
                assert is_due(s, now), (s["id"], k)  # saúde sem rodada seria linha inventada


def test_select_health_with_sources_keeps_problems_always_and_online_only_on_the_sources_own_turn():
    srcs = [{"id": "a", "interval_s": 600}, {"id": "b", "interval_s": 600}]
    ah = {"source_id": "a", "status": "ONLINE"}
    bh = {"source_id": "b", "status": "ONLINE"}
    off = {"source_id": "b", "status": "OFFLINE"}
    rounds = [T0 + timedelta(minutes=5 * k) for k in range(12)]
    a_turns = [k for k, n in enumerate(rounds) if select_health([ah], n, sources=srcs)]
    assert a_turns and len(a_turns) <= 3  # só no horário dela, não em toda rodada
    assert all(select_health([off], n, sources=srcs) == [off] for n in rounds)  # problema vai sempre
    unknown = [{"source_id": "fantasma", "status": "ONLINE"}]
    assert select_health(unknown, rounds[0], sources=srcs) == []  # fonte fora do catálogo não relata


# ---- 2) o excedente de sinais de um evento enorme não pode se perder ---------------------------------------------------------------
def test_signals_beyond_the_per_part_cap_of_a_single_event_are_still_sent():
    sigs = [{"event_id": "ev-1", "hash": f"h{i}", "source_id": "s"} for i in range(1100)]
    batch = {"batch_id": "b", "sources": [], "catalog_complete": False, "events": [{"event_id": "ev-1"}], "signals": sigs,
             "pulses": [], "source_health": [], "series": [], "forecasts": []}
    parts = chunks(batch, max_signals=450)
    sent = [g["hash"] for p in parts for g in p["signals"]]
    assert sorted(sent) == sorted(g["hash"] for g in sigs)  # 1100 de 1100; antes só 450
    assert all(len(p["signals"]) <= 450 for p in parts)
    assert parts[0]["events"] and not any(p["events"] for p in parts[1:])  # o evento vai antes dos seus sinais extras (FK)


# ---- 3) conteúdo de fonte metrics_only fora do log mesmo na rodada em que ela não está na vez ------------------------------------
def test_metrics_only_content_stays_out_of_the_log_even_when_that_source_is_not_due(tmp_path, monkeypatch, capsys):
    from pulso_engine import client, pipeline
    cfg = tmp_path / "s.json"

    def src(i, display):
        return {"id": i, "name": i, "domain": f"{i}.com", "adapter": "rss", "source_class": "NEWS_HIGH", "url": f"https://{i}.com/rss",
                "state": None, "enabled": True, "access": "public_feed", "terms_url": "https://x/t", "interval_s": 300,
                "retention_days": 90, "display": display, "reviewed_by": "x", "reviewed_at": "2026-10-03"}

    cfg.write_text(json.dumps([src("normal", "headline_link"), src("reservada", "metrics_only")]), encoding="utf-8")
    # nesta rodada SÓ a fonte normal está na vez; a metrics_only (ativa no catálogo) não
    monkeypatch.setattr(pipeline, "is_due", lambda s, now: s["id"] == "normal")
    ev = {"event_id": "ev-1", "title": "TITULO QUE PODE VIR DE FONTE RESERVADA", "category": "SECURITY", "pulse": 40, "confidence": 50,
          "source_count": 2, "alert_level": 2, "state": None}
    batch = {"batch_id": "b", "sources": [], "catalog_complete": True, "events": [ev], "events_total": 1, "signals": [],
             "pulses": [{"scope": "BR", "score": 40, "alert_level": 2}], "source_health": [], "series": [], "forecasts": []}
    monkeypatch.setattr(pipeline, "run_once", lambda *a, **k: batch)
    for name in ("fetch_history", "fetch_pulse_history", "fetch_open_forecasts", "fetch_signals", "fetch_event_digest"):
        monkeypatch.setattr(client, name, lambda *a, **k: [])
    monkeypatch.setattr(client, "push_batch", lambda part, *a, **k: {"ok": True})
    assert pipeline.main(["--config", str(cfg), "--push"]) == 0
    out = capsys.readouterr().out
    assert "TITULO QUE PODE VIR" not in out and "categorias:" in out  # antes: imprimia o título (log público)
