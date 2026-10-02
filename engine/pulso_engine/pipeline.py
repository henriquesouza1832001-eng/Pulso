"""Pipeline: coletar → deduplicar → clusterizar → eventos → Pulso → lote de ingestão."""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .collectors.news.rss import RssAdapter, http_fetch
from .config import load_sources
from .events import build_event, is_publishable, iso
from .models import Signal
from .processing.clustering import cluster_signals
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


def run_once(
    sources: list[dict],
    fetcher: Callable[[str], bytes] = http_fetch,
    now: datetime | None = None,
    keywords: KeywordEngine | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    keywords = keywords or KeywordEngine()
    signals: dict[str, Signal] = {}
    health: list[dict] = []
    for src in sources:
        if src.get("adapter") != "rss":
            continue
        try:
            got = RssAdapter(src, keywords, fetcher, lambda: now).run()
            status, detail = ("ONLINE", None) if got else ("DEGRADED", "feed sem itens válidos")
            for s in got:
                signals.setdefault(s.hash, s)  # dedup por URL canônica/título
        except Exception as exc:  # uma fonte caída nunca derruba o ciclo
            got, status, detail = [], "OFFLINE", f"{type(exc).__name__}: {exc}"[:300]
            print(f"[warn] {src['id']}: {detail}", file=sys.stderr)
        health.append({"source_id": src["id"], "status": status,
                       "last_success": iso(now) if got else None, "detail": detail})

    clusters = [c for c in cluster_signals(list(signals.values())) if is_publishable(c)]
    events = [build_event(c, now) for c in clusters]
    event_signals = [s for c in clusters for s in c.signals]
    return {
        "batch_id": uuid.uuid4().hex,
        "sources": [{k: s[k] for k in ("id", "name", "domain", "adapter", "source_class", "url", "state")} for s in sources],
        "events": events,
        "signals": [signal_dict(s) for s in event_signals],
        "pulses": build_pulses(events, now),
        "source_health": health,
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
         "source_health": batch["source_health"] if i == len(parts) - 1 else []}
        for i, p in enumerate(parts)
    ]


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Roda uma rodada do Engine do PULSO.")
    ap.add_argument("--config", type=Path, default=DEFAULT_SOURCES)
    ap.add_argument("--push", action="store_true", help="envia ao Worker (exige PULSO_API_URL e PULSO_INGEST_TOKEN)")
    args = ap.parse_args(argv)

    sources = load_sources(args.config)  # valida o protocolo; fonte fora do protocolo não roda
    batch = run_once(sources)
    print(f"sinais={len(batch['signals'])} eventos={len(batch['events'])} "
          f"BR={batch['pulses'][0]['score']} nivel={batch['pulses'][0]['alert_level']}")
    for h in batch["source_health"]:
        print(f"  {h['source_id']:<16} {h['status']:<9} {h['detail'] or ''}")
    for e in sorted(batch["events"], key=lambda e: -e["pulse"])[:8]:
        print(f"  [{e['pulse']:>3}] {e['category']:<14} fontes={e['source_count']} conf={e['confidence']:>3} {e['title'][:70]}")
    if args.push:
        from .client import push_batch
        for part in chunks(batch):
            print("  push:", push_batch(part))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
