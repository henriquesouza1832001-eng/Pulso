"""Pipeline: coletar → deduplicar → clusterizar → eventos → Pulso → lote de ingestão."""
from __future__ import annotations

import json
import sys
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from .anomaly import anomaly_score
from .baseline import ewma_baseline, hourly_counts
from .collectors.news.rss import http_fetch
from .collectors.registry import URL_FETCH_ADAPTERS, build_adapter
from .config import load_sources
from .forecast import make_nowcasts, resolve_due
from .forecast_surge import METRIC_PREFIX, make_surge_forecasts, merge_series, resolve_surge_due
from .events import build_event, dominant_category, is_publishable, iso
from .models import Signal
from .processing.clustering import cluster_signals
from .processing.geo import locate
from .series import build_series
from .processing.keyword_engine import KeywordEngine

MAX_PARALLEL_SOURCES = 8  # coletas simultâneas; limite conservador para não sobrecarregar as fontes
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


# Adaptadores cuja geografia vem da PRÓPRIA FONTE (dado estruturado), não do texto da manchete.
GEO_ADAPTERS = frozenset({"inmet", "inpe_fires", "idap_cap", "usgs", "infodengue", "reddit"})


def geo_source_ids(sources: list[dict]) -> frozenset[str]:
    """Fontes cujo lugar não se deduz do texto: feed regional (`state` na configuração) e adaptadores de dado geográfico."""
    return frozenset(s["id"] for s in sources if s.get("state") or s.get("adapter") in GEO_ADAPTERS)


def regeolocate(s: Signal, source_geo: frozenset[str] = frozenset()) -> Signal:
    """Reaplica o geolocalizador ao texto do sinal (corrige localizações antigas erradas).

    Se o texto não cita lugar e a localização do sinal veio da FONTE (estado de um feed regional, coordenadas do INPE, da
    Defesa Civil, do USGS...), ela é mantida: apagá-la faria o lugar do evento mudar de um ciclo para o outro. Para as demais
    fontes, sem lugar no texto a localização antiga (possivelmente errada) é limpa."""
    place = locate(f"{s.title}. {s.text or ''}")
    if place is None and s.source_id in source_geo:
        return s
    return replace(
        s,
        latitude=place.lat if place else None, longitude=place.lon if place else None,
        geo_precision=place.precision if place else None,  # type: ignore[arg-type]
        geo_confidence=place.confidence if place else None,
        state=place.uf if place else None, city=place.city if place else None,
    )


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
    stored: list[dict] | None = None,
    pulse_points: list[dict] | None = None,
    open_forecasts: list[dict] | None = None,
    catalog: list[dict] | None = None,
    known_events: list[dict] | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    keywords = keywords or KeywordEngine()
    signals: dict[str, Signal] = {}  # sinais coletados NESTA rodada
    health: list[dict] = []
    def collect(src: dict) -> tuple[list[Signal], str, str | None]:
        try:
            # RSS e INMET buscam uma URL com o fetcher; sensores sociais usam requisições OAuth próprias.
            got = build_adapter(src, keywords, fetcher if src["adapter"] in URL_FETCH_ADAPTERS else None, lambda: now).run()
            if got:
                return got, "ONLINE", None
            # Fonte de limiar (alerta, choque, foco): sem ocorrência é o normal, não uma falha.
            return got, *(("ONLINE", "sem ocorrências no limiar") if src.get("quiet_ok") else ("DEGRADED", "feed sem itens válidos"))
        except Exception as exc:  # uma fonte caída nunca derruba o ciclo
            detail = f"{type(exc).__name__}: {exc}"[:300]
            print(f"[warn] {src['id']}: {detail}", file=sys.stderr)
            # RATE_LIMITED/AUTH_ERROR das APIs sociais; HTTP 429 de qualquer fonte também é limite de taxa (não insistir).
            status = getattr(exc, "health_status", None) or ("RATE_LIMITED" if getattr(exc, "code", None) == 429 else "OFFLINE")
            return [], status, detail

    # Em paralelo (cada fonte é independente e espera rede): dezenas de fontes não estouram o tempo do ciclo.
    # `map` preserva a ordem das fontes, então o resultado continua determinístico.
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_SOURCES) as pool:
        collected = list(pool.map(collect, sources))
    for src, (got, status, detail) in zip(sources, collected):
        for s in got:
            signals.setdefault(s.hash, s)  # dedup por URL canônica/título
        health.append({"source_id": src["id"], "status": status,
                       "last_success": iso(now) if status == "ONLINE" else None, "detail": detail})

    # Notícia mais velha que a janela de estado não é informação nova: o feed ainda a mostra, mas a API só devolve
    # as últimas 24 h, então reenviá-la a cada ciclo reescreveria no banco linhas iguais (limite de escrita do D1)
    # e recriaria eventos que a API nem exibe. Fora do agrupamento, dos eventos e das séries.
    signals = {h: s for h, s in signals.items() if (now - s.timestamp) <= STATE_WINDOW}

    # Estado: sinais já gravados entram no agrupamento, então a história continua a mesma
    # (mesmo event_id) mesmo depois que a notícia mais antiga sai do feed.
    source_geo = geo_source_ids(catalog if catalog is not None else sources)
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
        old = regeolocate(old, source_geo)  # correções do geolocalizador valem também para sinais já gravados
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
    pulses = build_pulses(events, now)

    # Previsões: resolve as vencidas com o valor REAL e cria novas só se houver histórico suficiente.
    br_now = {"timestamp": iso(now), "score": pulses[0]["score"]}
    points = [*(pulse_points or []), br_now]
    # Série do que acabamos de coletar + a gravada; as previsões de volume usam as duas.
    series_now = build_series(list(all_signals.values()), now)
    series_rows = merge_series(history, series_now)
    pulse_open = [f for f in open_forecasts or [] if not str(f.get("metric", "")).startswith(METRIC_PREFIX)]
    # Previsão nova com id que já está aberta no Worker (o id leva a hora) não é reenviada: seria uma escrita sem efeito.
    already_open = {f["forecast_id"] for f in open_forecasts or []}
    forecasts = [
        *resolve_due(pulse_open, points, now),
        *(f for f in make_nowcasts(points, now) if f["forecast_id"] not in already_open),
        *resolve_surge_due(open_forecasts or [], series_rows, points, now),
        *(f for f in make_surge_forecasts(series_rows, now) if f["forecast_id"] not in already_open),
    ]
    events_to_send = changed_events(events, known_events)
    series_to_send = changed_series(series_now, history)
    return {
        "batch_id": uuid.uuid4().hex,
        # Com `catalog`, envia TODAS as fontes ativas (mesmo as fora da janela de interval_s) e o Worker
        # desativa as ausentes: o painel "Fontes ativas" acompanha o config/sources.json.
        "sources": [{k: s[k] for k in ("id", "name", "domain", "adapter", "source_class", "url", "state")}
                    for s in (catalog if catalog is not None else sources)],
        "catalog_complete": catalog is not None,
        "events": events_to_send,
        "events_total": len(events),
        "signals": [signal_dict(s) for s in to_send],
        "pulses": pulses,
        "source_health": health,
        "series": series_to_send,
        "forecasts": forecasts,
    }


PULSE_RESEND_DELTA = 3  # o Pulso só é reescrito se mudou ao menos isto (o frescor o faz cair a cada ciclo)


def changed_events(events: list[dict], known: list[dict] | None) -> list[dict]:
    """Só o que é novo ou mudou de forma relevante. O D1 gratuito limita as linhas escritas por dia: reenviar
    centenas de eventos iguais a cada 5 min estouraria o limite. Sem resumo (`known` vazio) envia tudo (seguro)."""
    if not known:
        return events
    by_id = {k["event_id"]: k for k in known}
    out = []
    for e in events:
        k = by_id.get(e["event_id"])
        if (k is None or k["alert_level"] != e["alert_level"] or k["status"] != e["status"]
                or k["signal_count"] != e["signal_count"] or k["source_count"] != e["source_count"]
                or abs(k["pulse"] - e["pulse"]) >= PULSE_RESEND_DELTA):
            out.append(e)
    return out


def changed_series(series_now: list[dict], stored: list[dict] | None) -> list[dict]:
    """Só as janelas novas ou com contagem maior que a gravada (o Worker já guarda o MAIOR valor visto)."""
    if not stored:
        return series_now
    have = {(r["scope"], r["category"], r["bucket"]): int(r["signals"]) for r in stored}
    return [r for r in series_now if int(r["signals"]) > have.get((r["scope"], r["category"], r["bucket"]), -1)]


def select_sources(batch: dict, now: datetime, full_every_min: int = 30, slot_min: int = 5,
                   extra_ids: frozenset[str] | set[str] = frozenset()) -> None:
    """Catálogo COMPLETO só no horário de revisão (a cada `full_every_min` min); nos demais ciclos, só as fontes
    dos sinais enviados e das linhas de saúde enviadas (as chaves estrangeiras exigem que existam) e sem desativar
    nenhuma outra."""
    if now.minute % full_every_min < slot_min:
        return
    used = {g["source_id"] for g in batch["signals"]} | set(extra_ids)
    batch["sources"] = [s for s in batch["sources"] if s["id"] in used]
    batch["catalog_complete"] = False


def select_health(health: list[dict], now: datetime, full_every_min: int = 30, slot_min: int = 5) -> list[dict]:
    """Saúde: o que NÃO está ONLINE vai sempre (alerta imediato); o que está ONLINE só a cada `full_every_min`
    minutos (uma rodada), para não reescrever dezenas de linhas iguais a cada ciclo."""
    if now.minute % full_every_min < slot_min:
        return health
    return [h for h in health if h["status"] != "ONLINE"]


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
    # Sinais sem evento (matéria isolada de tema irrelevante) E sinais de um evento que não foi reenviado (nada mudou nele,
    # mas o sinal é novo ou trocou de evento): gravados em lotes próprios. O evento já existe no banco (chave estrangeira).
    sent_events = {e["event_id"] for e in batch["events"]}
    orphans = [g for g in batch["signals"] if g["event_id"] is None or g["event_id"] not in sent_events]
    for i in range(0, len(orphans), max_signals):
        parts.append({"events": [], "signals": orphans[i:i + max_signals]})
    return [
        # Fontes só na PRIMEIRA parte (os sinais das partes seguintes dependem delas, e reenviar o catálogo em
        # cada parte reescreveria dezenas de linhas iguais).
        {"batch_id": f"{batch['batch_id']}-{i}", "sources": batch["sources"] if i == 0 else [],
         "catalog_complete": batch["catalog_complete"] if i == 0 else False,
         "events": p["events"], "signals": p["signals"],
         "pulses": batch["pulses"] if i == len(parts) - 1 else [],
         "source_health": batch["source_health"] if i == len(parts) - 1 else [],
         "series": batch["series"] if i == len(parts) - 1 else [],
         "forecasts": batch.get("forecasts", []) if i == len(parts) - 1 else []}
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
        catalog = None  # piloto/rodada parcial nunca desativa outras fontes no Worker
    else:
        now = datetime.now(timezone.utc)
        # valida o protocolo; fonte fora do protocolo não roda
        catalog = load_sources(args.config)
        sources = [s for s in catalog if is_due(s, now)]
    from .client import (WorkerAuthError, WorkerUnavailable, fetch_event_digest, fetch_history, fetch_open_forecasts,
                         fetch_pulse_history, fetch_signals)
    # Histórico (baseline), sinais gravados (estado) e previsões abertas: só com dado real do Worker.
    # Janelas mínimas que bastam (o D1 gratuito limita as linhas LIDAS por dia): 36 h de séries (a previsão de
    # volume precisa de > 25 h) e 24 h do Pulso (o previsor exige ~3,5 h).
    history = fetch_history(hours=36) if args.push else []
    pulse_points = fetch_pulse_history(hours=24) if args.push else []
    open_forecasts = fetch_open_forecasts() if args.push else []
    # Sinais e resumo de eventos gravados são ESTRITOS: se o Worker falhar, "fora do ar" não pode virar "banco vazio"
    # (o ciclo recriaria e reenviaria tudo e estouraria o orçamento de escrita do D1). Pula o ciclo; a próxima recolhe o mesmo.
    stored, known_events = [], []
    if args.push:
        try:
            stored = fetch_signals(strict=True)
            known_events = fetch_event_digest(strict=True)
        except WorkerUnavailable as exc:
            print(f"[aviso] Worker indisponível ({exc}): ciclo pulado para não reenviar tudo; a próxima rodada recolhe os mesmos itens.",
                  file=sys.stderr)
            return 0
        except WorkerAuthError as exc:
            print(f"[erro] {exc}", file=sys.stderr)
            return 1
    batch = run_once(sources, history=history, stored=stored, pulse_points=pulse_points, open_forecasts=open_forecasts,
                     catalog=catalog, known_events=known_events)
    print(f"sinais={len(batch['signals'])} eventos={len(batch['events'])}/{batch['events_total']} "
          f"BR={batch['pulses'][0]['score']} nivel={batch['pulses'][0]['alert_level']}")
    for h in batch["source_health"]:
        print(f"  {h['source_id']:<16} {h['status']:<9} {h['detail'] or ''}")
    if any(s["display"] == "metrics_only" for s in sources):
        # Conteúdo de fonte metrics_only não aparece em log (os logs do Actions são públicos).
        cats: dict[str, int] = {}
        for g in batch["signals"]:
            cats[g["category"]] = cats.get(g["category"], 0) + 1
        print("  categorias:", ", ".join(f"{k}={v}" for k, v in sorted(cats.items())) or "-")
        ufs: dict[str, int] = {}
        for g in batch["signals"]:
            ufs[g["state"] or "sem_UF"] = ufs.get(g["state"] or "sem_UF", 0) + 1
        print("  estados:", ", ".join(f"{k}={v}" for k, v in sorted(ufs.items())) or "-")
    else:
        for e in sorted(batch["events"], key=lambda e: -e["pulse"])[:8]:
            print(f"  [{e['pulse']:>3}] {e['category']:<14} fontes={e['source_count']} conf={e['confidence']:>3} {e['title'][:70]}")
    # (antes, uma fonte metrics_only ATIVA encerrava a rodada aqui e NADA era enviado: a ingestão parava em silêncio)
    if args.push:
        from .client import push_batch
        now_push = datetime.now(timezone.utc)
        batch["source_health"] = select_health(batch["source_health"], now_push)
        # as linhas de saúde enviadas também precisam das suas fontes registradas (chave estrangeira)
        select_sources(batch, now_push, extra_ids={h["source_id"] for h in batch["source_health"]})
        for part in chunks(batch):
            print("  push:", push_batch(part))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
