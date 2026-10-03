"""Pipeline: coletar → deduplicar → clusterizar → eventos → Pulso → lote de ingestão."""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .anomaly import anomaly_score
from .baseline import ewma_baseline, hourly_counts
from .collectors.news.rss import http_fetch
from .collectors.registry import build_adapter
from .config import load_sources
from .events import build_event, dominant_category, is_publishable, iso
from .models import Signal
from .processing.clustering import cluster_signals
from .series import build_series
from .processing.keyword_engine import KeywordEngine

DEFAULT_SOURCES = Path(__file__).resolve().parent.parent / "config" / "sources.json"


def national_level(score: int, events: list[dict]) -> int:
    if any(e["alert_level"] == 5 for e in events):
        return 5
    return 1 if score < 30 else 2 if score < 55 else 3 if score < 75 else 4  # nacional só chega a 4 sem nível 5 de evento


def aggregate(events: list[dict]) -> int:
    """Pulso agregado: eventos mais intensos pesam mais; cada EVENTO conta uma vez (não cada matéria)."""
    top = sorted((e["pulse"] for e in events), reverse=True)[:10]
    if not top:
        return 0
    weights = [len(top) - i for i in range(len(top))]
    return round(sum(p * w for p, w in zip(top, weights)) / sum(weights))


def build_pulses(events: list[dict], now: datetime) -> list[dict]:
    br = aggregate(events)
    pulses = [{"scope": "BR", "timestamp": iso(now), "score": br, "alert_level": national_level(br, events),
               # Sem histórico no Engine ainda: não fabricamos variação.
               "contributors": []}]
    by_state: dict[str, list[dict]] = {}
    for e in events:
        if e["state"]:
            by_state.setdefault(e["state"], []).append(e)
    for uf, evs in by_state.items():
        score = aggregate(evs)
        pulses.append({"scope": f"UF:{uf}", "timestamp": iso(now), "score": score,
                       "alert_level": national_level(score, evs), "contributors": []})
    return pulses


def cluster_anomaly(cluster, all_signals: list[Signal], history: list[dict], now: datetime) -> float:
    """Anomalia do tema no escopo do evento: atividade da última hora vs. baseline histórico."""
    sigs = cluster.signals
    category = dominant_category(sigs)
    state = next((s.state for s in sigs if s.state), None)
    scope = f"UF:{state}" if state else "BR"
    base = ewma_baseline(hourly_counts(history, scope, category, now))
    # Mesma régua do baseline: todos os sinais do tema no escopo, na última hora.
    current = sum(
        1 for s in all_signals
        if s.category == category and (scope == "BR" or s.state == state) and (now - s.timestamp).total_seconds() <= 3600
    )
    return anomaly_score(float(current), base)


def is_due(src: dict, now: datetime, tick_s: int = 300) -> bool:
    """O agendador roda a cada 5 min; fonte com interval_s maior só roda na sua janela.

    Sem estado: a janela é derivada do relógio (ex.: 900 s → rodadas de :00, :15, :30, :45).
    """
    every = max(1, int(src.get("interval_s", tick_s)) // tick_s)
    return int(now.timestamp()) // tick_s % every == 0


def run_once(
    sources: list[dict],
    fetcher: Callable[[str], bytes] = http_fetch,
    now: datetime | None = None,
    keywords: KeywordEngine | None = None,
    history: list[dict] | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    keywords = keywords or KeywordEngine()
    signals: dict[str, Signal] = {}
    health: list[dict] = []
    for src in sources:
        try:
            # O fetcher RSS recebe uma URL; sensores sociais usam requisições OAuth próprias.
            got = build_adapter(src, keywords, fetcher if src["adapter"] == "rss" else None, lambda: now).run()
            status, detail = ("ONLINE", None) if got else ("DEGRADED", "feed sem itens válidos")
            for s in got:
                signals.setdefault(s.hash, s)  # dedup por URL canônica/título
        except Exception as exc:  # uma fonte caída nunca derruba o ciclo
            status = getattr(exc, "health_status", "OFFLINE")  # RATE_LIMITED/AUTH_ERROR das APIs
            got, detail = [], f"{type(exc).__name__}: {exc}"[:300]
            print(f"[warn] {src['id']}: {detail}", file=sys.stderr)
        health.append({"source_id": src["id"], "status": status,
                       "last_success": iso(now) if got else None, "detail": detail})

    clusters = [c for c in cluster_signals(list(signals.values())) if is_publishable(c)]
    history = history or []
    events = [build_event(c, now, cluster_anomaly(c, list(signals.values()), history, now)) for c in clusters]
    event_signals = [s for c in clusters for s in c.signals]
    return {
        "batch_id": uuid.uuid4().hex,
        "sources": [{k: s[k] for k in ("id", "name", "domain", "adapter", "source_class", "url", "state")} for s in sources],
        "events": events,
        "signals": [signal_dict(s) for s in event_signals],
        "pulses": build_pulses(events, now),
        "source_health": health,
        "series": build_series(list(signals.values()), now),
    }


def signal_dict(s: Signal) -> dict:
    return {
        "signal_id": s.signal_id, "source_id": s.source_id, "source_class": s.source_class,
        "timestamp": iso(s.timestamp), "collected_at": iso(s.collected_at), "title": s.title, "text": s.text,
        "url": s.url, "category": s.category, "latitude": s.latitude, "longitude": s.longitude,
        "geo_precision": s.geo_precision, "geo_confidence": s.geo_confidence, "reliability": s.reliability,
        "event_id": s.event_id, "hash": s.hash, "canonical_url": s.canonical_url, "author": s.author,
        "state": s.state, "city": s.city,
    }


def chunks(batch: dict, max_events: int = 150, max_signals: int = 450) -> list[dict]:
    """Divide o lote nos limites do Worker; pulsos, fontes e saúde vão no último."""
    sigs_by_event: dict[str, list[dict]] = {}
    for g in batch["signals"]:
        sigs_by_event.setdefault(g["event_id"], []).append(g)
    parts: list[dict] = []
    cur_e: list[dict] = []
    cur_s: list[dict] = []
    for e in batch["events"]:
        es = sigs_by_event.get(e["event_id"], [])
        if cur_e and (len(cur_e) >= max_events or len(cur_s) + len(es) > max_signals):
            parts.append({"events": cur_e, "signals": cur_s})
            cur_e, cur_s = [], []
        cur_e.append(e)
        cur_s.extend(es[:max_signals])
    parts.append({"events": cur_e, "signals": cur_s})
    return [
        {"batch_id": f"{batch['batch_id']}-{i}", "sources": batch["sources"],
         "events": p["events"], "signals": p["signals"],
         "pulses": batch["pulses"] if i == len(parts) - 1 else [],
         "source_health": batch["source_health"] if i == len(parts) - 1 else [],
         "series": batch["series"] if i == len(parts) - 1 else []}
        for i, p in enumerate(parts)
    ]


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Roda uma rodada do Engine do PULSO.")
    ap.add_argument("--config", type=Path, default=DEFAULT_SOURCES)
    ap.add_argument("--push", action="store_true", help="envia ao Worker (exige PULSO_API_URL e PULSO_INGEST_TOKEN)")
    ap.add_argument("--source", action="append", metavar="ID",
                    help="piloto: roda só estas fontes, mesmo desativadas (proibido com --push)")
    ap.add_argument("--respect-interval", action="store_true",
                    help="com --source: roda a fonte só na sua janela de interval_s (piloto agendado)")
    args = ap.parse_args(argv)

    if args.source:
        sources = [s for s in load_sources(args.config, only_enabled=False) if s["id"] in args.source]
        if missing := set(args.source) - {s["id"] for s in sources}:
            ap.error(f"fonte(s) inexistente(s): {', '.join(sorted(missing))}")
        if args.push and any(not s.get("enabled", True) for s in sources):
            ap.error("fonte desativada só roda em piloto, sem --push (COLLECTION_PROTOCOL.md §3)")
        if args.respect_interval:
            now = datetime.now(timezone.utc)
            sources = [s for s in sources if is_due(s, now)]
            if not sources:
                print("nenhuma fonte na janela de interval_s; nada a fazer")
                return 0
    else:
        now = datetime.now(timezone.utc)
        # valida o protocolo; fonte fora do protocolo não roda
        sources = [s for s in load_sources(args.config) if is_due(s, now)]
    from .client import fetch_history
    history = fetch_history() if args.push else []  # baseline só com histórico real
    batch = run_once(sources, history=history)
    print(f"sinais={len(batch['signals'])} eventos={len(batch['events'])} "
          f"BR={batch['pulses'][0]['score']} nivel={batch['pulses'][0]['alert_level']}")
    for h in batch["source_health"]:
        print(f"  {h['source_id']:<16} {h['status']:<9} {h['detail'] or ''}")
    if any(s["display"] == "metrics_only" for s in sources):
        # Conteúdo de fonte metrics_only não aparece em log (os logs do Actions são públicos).
        cats: dict[str, int] = {}
        for g in batch["signals"]:
            cats[g["category"]] = cats.get(g["category"], 0) + 1
        print("  categorias:", ", ".join(f"{k}={v}" for k, v in sorted(cats.items())) or "-")
        return 0
    for e in sorted(batch["events"], key=lambda e: -e["pulse"])[:8]:
        print(f"  [{e['pulse']:>3}] {e['category']:<14} fontes={e['source_count']} conf={e['confidence']:>3} {e['title'][:70]}")
    if args.push:
        from .client import push_batch
        for part in chunks(batch):
            print("  push:", push_batch(part))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
