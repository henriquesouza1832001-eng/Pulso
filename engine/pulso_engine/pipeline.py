"""Pipeline: coletar → deduplicar → clusterizar → eventos → Pulso → lote de ingestão."""
from __future__ import annotations

import json
import sys
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
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


STATE_WINDOW = timedelta(hours=24)  # quanto histórico entra no agrupamento


def signal_from_row(r: dict) -> Signal | None:
    """Reconstrói um Signal a partir de uma linha gravada (rota /api/admin/signals)."""
    try:
        def ts(v: str) -> datetime:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))

        return Signal(
            signal_id=r["signal_id"], source_id=r["source_id"], source_class=r["source_class"],
            timestamp=ts(r["timestamp"]), collected_at=ts(r["collected_at"]), title=r["title"],
            category=r.get("category") or "OTHER", text=r.get("text"), url=r.get("url"),
            latitude=r.get("latitude"), longitude=r.get("longitude"), geo_precision=r.get("geo_precision"),
            geo_confidence=r.get("geo_confidence"), reliability=r.get("reliability") or 50,
            event_id=r.get("event_id"), hash=r["hash"], canonical_url=r.get("canonical_url"),
            author=r.get("author"), state=r.get("state"), city=r.get("city"),
        )
    except (KeyError, ValueError, TypeError):
        return None  # linha corrompida nunca derruba o ciclo


def choose_event_id(cluster, prior_ids: dict[str, str]) -> str | None:
    """Reaproveita o id de evento mais frequente entre os membros já gravados (empate: o menor id)."""
    counts = Counter(prior_ids[s.hash] for s in cluster.signals if s.hash in prior_ids)
    if not counts:
        return None
    best = max(counts.values())
    return min(i for i, n in counts.items() if n == best)


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


def run_once(
    sources: list[dict],
    fetcher: Callable[[str], bytes] = http_fetch,
    now: datetime | None = None,
    keywords: KeywordEngine | None = None,
    history: list[dict] | None = None,
    stored: list[dict] | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    keywords = keywords or KeywordEngine()
    signals: dict[str, Signal] = {}  # sinais coletados NESTA rodada
    health: list[dict] = []
    for src in sources:
        try:
            got = build_adapter(src, keywords, fetcher, lambda: now).run()
            status, detail = ("ONLINE", None) if got else ("DEGRADED", "feed sem itens válidos")
            for s in got:
                signals.setdefault(s.hash, s)  # dedup por URL canônica/título
        except Exception as exc:  # uma fonte caída nunca derruba o ciclo
            got, status, detail = [], "OFFLINE", f"{type(exc).__name__}: {exc}"[:300]
            print(f"[warn] {src['id']}: {detail}", file=sys.stderr)
        health.append({"source_id": src["id"], "status": status,
                       "last_success": iso(now) if got else None, "detail": detail})

    # Estado: sinais já gravados entram no agrupamento, então a história continua a mesma
    # (mesmo event_id) mesmo depois que a notícia mais antiga sai do feed.
    prior_ids: dict[str, str] = {}
    known_ids: dict[str, str | None] = {}  # hash -> event_id já gravado (None = gravado sem evento)
    all_signals: dict[str, Signal] = {}
    for row in stored or []:
        old = signal_from_row(row)
        if old is None:
            continue
        known_ids[old.hash] = old.event_id  # mesmo fora da janela: já está no banco, não reenviar
        if (now - old.timestamp) > STATE_WINDOW:
            continue
        if old.event_id:
            prior_ids[old.hash] = old.event_id
        all_signals[old.hash] = old
    all_signals.update(signals)  # o dado fresco prevalece sobre o gravado

    history = history or []
    events: list[dict] = []
    for cluster in cluster_signals(list(all_signals.values())):
        if not is_publishable(cluster):
            for s in cluster.signals:
                object.__setattr__(s, "event_id", None)
            continue
        events.append(build_event(
            cluster, now, cluster_anomaly(cluster, list(all_signals.values()), history, now),
            event_id=choose_event_id(cluster, prior_ids),
        ))

    # Só enviamos o que é novo ou mudou de evento; o resto já está gravado.
    to_send = [s for h, s in all_signals.items() if h not in known_ids or known_ids[h] != s.event_id]
    return {
        "batch_id": uuid.uuid4().hex,
        "sources": [{k: s[k] for k in ("id", "name", "domain", "adapter", "source_class", "url", "state")} for s in sources],
        "events": events,
        "signals": [signal_dict(s) for s in to_send],
        "pulses": build_pulses(events, now),
        "source_health": health,
        "series": build_series(list(all_signals.values()), now),
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
    # Sinais sem evento (ex.: matéria isolada de tema irrelevante): gravados para o estado, em lotes próprios.
    orphans = sigs_by_event.get(None, [])
    for i in range(0, len(orphans), max_signals):
        parts.append({"events": [], "signals": orphans[i:i + max_signals]})
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
    args = ap.parse_args(argv)

    sources = load_sources(args.config)  # valida o protocolo; fonte fora do protocolo não roda
    from .client import fetch_history, fetch_signals
    # Histórico (baseline) e sinais gravados (agrupamento com estado): só com dado real do Worker.
    history = fetch_history() if args.push else []
    stored = fetch_signals() if args.push else []
    batch = run_once(sources, history=history, stored=stored)
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
