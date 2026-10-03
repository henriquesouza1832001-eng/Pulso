"""Auditoria de fontes: roda cada fonte de verdade (sem enviar nada) e mostra o que ela entrega.

Uso: py -m pulso_engine.audit                    # todas as fontes ativas
     py -m pulso_engine.audit --source g1 --source inmet-avisos
     py -m pulso_engine.audit --all              # inclui as desligadas (piloto)
Mostra, por fonte: situação, itens válidos, idade do mais novo, quantos têm lugar (UF) e as categorias mais comuns.
Serve para achar feed morto, feed parado, fonte que só traz ruído e lacuna de cobertura por estado.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable

from .collectors.news.rss import http_fetch
from .collectors.registry import URL_FETCH_ADAPTERS, build_adapter
from .config import load_sources
from .pipeline import DEFAULT_SOURCES, MAX_PARALLEL_SOURCES, STATE_WINDOW
from .processing.keyword_engine import KeywordEngine


def audit_one(src: dict, fetcher: Callable[[str], bytes], now: datetime, keywords: KeywordEngine) -> dict:
    row = {"id": src["id"], "enabled": src.get("enabled", True), "status": "OK", "items": 0, "fresh": 0,
           "newest_h": None, "with_state": 0, "categories": {}, "error": None}
    try:
        sigs = build_adapter(src, keywords, fetcher if src["adapter"] in URL_FETCH_ADAPTERS else None, lambda: now).run()
    except Exception as exc:  # noqa: BLE001 - a auditoria mostra o erro, não esconde
        row.update(status=getattr(exc, "health_status", "ERRO"), error=f"{type(exc).__name__}: {exc}"[:160])
        return row
    fresh = [s for s in sigs if (now - s.timestamp) <= STATE_WINDOW]
    row["items"], row["fresh"] = len(sigs), len(fresh)
    if sigs:
        row["newest_h"] = round((now - max(s.timestamp for s in sigs)).total_seconds() / 3600, 1)
    row["with_state"] = sum(1 for s in fresh if s.state)
    row["categories"] = dict(Counter(s.category for s in fresh).most_common(3))
    if not sigs:
        row["status"] = "VAZIO"
    elif not fresh:
        row["status"] = "PARADO"  # o feed responde, mas nada novo nas últimas 24 h
    return row


def audit(sources: list[dict], fetcher: Callable[[str], bytes] = http_fetch, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    keywords = KeywordEngine()
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_SOURCES) as pool:
        return list(pool.map(lambda s: audit_one(s, fetcher, now, keywords), sources))


def render(rows: list[dict]) -> str:
    lines = [f"{'fonte':<28} {'situação':<12} {'itens':>5} {'24h':>4} {'mais novo':>10} {'c/UF':>5}  categorias"]
    for r in rows:
        newest = f"{r['newest_h']} h" if r["newest_h"] is not None else "-"
        cats = ",".join(f"{k}:{v}" for k, v in r["categories"].items()) or (r["error"] or "")
        lines.append(f"{r['id']:<28} {r['status']:<12} {r['items']:>5} {r['fresh']:>4} {newest:>10} {r['with_state']:>5}  {cats}")
    by = Counter(r["status"] for r in rows)
    lines.append("")
    lines.append("resumo: " + ", ".join(f"{k} {v}" for k, v in by.most_common()) + f" (de {len(rows)})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pulso_engine.audit")
    ap.add_argument("--source", action="append", help="id da fonte (repita para várias)")
    ap.add_argument("--all", action="store_true", help="inclui fontes desligadas")
    args = ap.parse_args(argv)
    sources = load_sources(DEFAULT_SOURCES, only_enabled=not (args.all or args.source))
    if args.source:
        sources = [s for s in sources if s["id"] in args.source]
        if not sources:
            ap.error("nenhuma fonte com esse id")
    print(render(audit(sources)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
