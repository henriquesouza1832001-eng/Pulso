"""PULSO Sentinela (núcleo determinístico): detecta candidatos a anomalia, decide se investiga e mantém o ESTADO das
investigações. Sem LLM, sem rede: estatística (baseline, z-score, tendência) + regras configuráveis.

Fluxo: `detect_candidates` (escopo x categoria com atividade fora do normal) -> `should_investigate` (gatilho) ->
`advance` (abre, atualiza ou encerra investigações, sem duplicar as já ativas). Deep search e validação (passos 6 e 7)
alimentam `evidence`/estado depois; aqui nasce o objeto que elas usam.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

from ..anomaly import window_anomaly
from ..baseline import ewma_baseline, seasonal_baseline, seasonal_hourly
from ..intelligence.trends import window_metrics
from ..models import Signal

STATES = ("NEW", "INVESTIGATING", "CORRELATING", "WAITING_CONFIRMATION", "CONFIRMED", "DISPUTED", "RESOLVING", "CLOSED")


@dataclass(frozen=True)
class SentinelConfig:
    """Todos os valores configuráveis (nenhum número mágico escondido)."""
    anomaly_score: float = 0.65
    source_type_count: int = 3
    min_signals_for_types: int = 3  # tipos de fonte só disparam com volume mínimo (2 sinais de 3 tipos não é nada)
    emerging_term_score: float = 0.75
    official_signal: bool = True
    window_min: int = 15
    context_window_min: int = 60
    resolve_after_min: int = 90  # sem atividade anormal por este tempo: RESOLVING
    close_after_min: int = 180  # e depois de mais este tempo: CLOSED
    dedup_window_min: int = 360  # reaproveita investigação ativa no mesmo escopo/categoria dentro desta janela


@dataclass(frozen=True)
class Candidate:
    scope: str
    category: str
    score: float
    z: float
    basis: str
    signal_count: int
    source_type_count: int
    official_signal: bool
    emerging_term_score: float = 0.0
    signal_hashes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Investigation:
    investigation_id: str
    scope: str  # BR | UF:MG
    category: str
    status: str
    started_at: datetime
    last_update: datetime
    initial_anomaly: float
    anomaly: float  # última medida
    evidence_count: int
    official_confirmation: bool
    reasons: tuple[str, ...] = ()
    last_anomalous_at: datetime | None = None
    signal_hashes: tuple[str, ...] = field(default=())


def _id(scope: str, category: str, at: datetime) -> str:
    return "inv-" + hashlib.sha1(f"{scope}|{category}|{at.strftime('%Y%m%d%H')}".encode()).hexdigest()[:10]


def _baseline(rows: list[dict], scope: str, category: str, now: datetime):
    """Sazonal quando houver histórico; senão EWMA das horas observadas; senão inválido (nunca finge normal)."""
    seasonal = seasonal_baseline(rows, scope, category, now)
    if seasonal.valid:
        return seasonal
    return ewma_baseline(list(seasonal_hourly(rows, scope, category, now).values()))


def detect_candidates(signals: list[Signal], obs_rows: list[dict], now: datetime,
                      cfg: SentinelConfig = SentinelConfig(), emerging: dict[tuple[str, str], float] | None = None,
                      duplicates_by_hash: dict[str, int] | None = None) -> list[Candidate]:
    """Um candidato por (escopo, categoria) com atividade recente. O gatilho é decidido em `should_investigate`."""
    cells: dict[tuple[str, str], list[Signal]] = {}
    for s in signals:
        if s.category == "OTHER" or s.timestamp > now:
            continue
        for scope in ["BR"] + ([f"UF:{s.state}"] if s.state else []):
            cells.setdefault((scope, s.category), []).append(s)
    out = []
    for (scope, cat), sigs in sorted(cells.items()):
        win = window_metrics(sigs, now, cfg.window_min, duplicates_by_hash)
        ctx = window_metrics(sigs, now, cfg.context_window_min, duplicates_by_hash)
        if not win.signal_count and not ctx.signal_count:
            continue
        an = window_anomaly(win.signal_count, cfg.window_min, _baseline(obs_rows, scope, cat, now))
        recent = tuple(sorted(s.hash for s in sigs if now - s.timestamp <= timedelta(minutes=cfg.context_window_min)))
        out.append(Candidate(scope, cat, an["score"], an["z"], an["basis"], ctx.signal_count, ctx.source_type_count,
                             ctx.official_confirmation, (emerging or {}).get((scope, cat), 0.0), recent))
    return out


def should_investigate(c: Candidate, cfg: SentinelConfig = SentinelConfig()) -> tuple[bool, tuple[str, ...]]:
    """Gatilho (§25): anomalia, diversidade de tipos de fonte, sinal oficial ou termo emergente. Devolve os motivos."""
    reasons = []
    if c.score >= cfg.anomaly_score:
        reasons.append(f"anomalia {c.score:.2f} (z {c.z:.1f}, base {c.basis})")
    if c.source_type_count >= cfg.source_type_count and c.signal_count >= cfg.min_signals_for_types:
        reasons.append(f"{c.source_type_count} tipos de fonte")
    if cfg.official_signal and c.official_signal:
        reasons.append("sinal oficial")
    if c.emerging_term_score >= cfg.emerging_term_score:
        reasons.append(f"termo emergente {c.emerging_term_score:.2f}")
    return bool(reasons), tuple(reasons)


def find_active(active: list[Investigation], scope: str, category: str, now: datetime,
                cfg: SentinelConfig = SentinelConfig()) -> Investigation | None:
    """Evita pesquisa repetida (§54): investigação não encerrada da mesma categoria e escopo dentro da janela de tempo.
    BR e UF são escopos distintos de propósito: uma anomalia só em MG não cobre o país, e vice-versa."""
    for inv in active:
        if inv.status == "CLOSED" or inv.category != category or inv.scope != scope:
            continue
        if now - inv.last_update <= timedelta(minutes=cfg.dedup_window_min):
            return inv
    return None


def advance(active: list[Investigation], candidates: list[Candidate], now: datetime,
            cfg: SentinelConfig = SentinelConfig()) -> list[Investigation]:
    """Novo estado das investigações: abre as novas, atualiza as existentes e esfria/encerra as sem atividade anormal.
    Devolve só as que MUDARAM (escrita condicional no banco)."""
    changed: dict[str, Investigation] = {}
    for c in candidates:
        go, reasons = should_investigate(c, cfg)
        if not go:
            continue
        existing = find_active(active, c.scope, c.category, now, cfg)
        if existing is not None:
            hashes = tuple(sorted(set(existing.signal_hashes) | set(c.signal_hashes)))
            changed[existing.investigation_id] = replace(
                existing, last_update=now, last_anomalous_at=now, anomaly=c.score, signal_hashes=hashes,
                evidence_count=len(hashes), official_confirmation=existing.official_confirmation or c.official_signal,
                status="INVESTIGATING" if existing.status in ("NEW", "RESOLVING") else existing.status,
                reasons=tuple(dict.fromkeys(existing.reasons + reasons)),
            )
        else:
            inv = Investigation(_id(c.scope, c.category, now), c.scope, c.category, "NEW", now, now, c.score, c.score,
                                len(c.signal_hashes), c.official_signal, reasons, now, c.signal_hashes)
            changed[inv.investigation_id] = inv
    for inv in active:  # esfriamento: sem atividade anormal por tempo suficiente
        if inv.investigation_id in changed or inv.status == "CLOSED":
            continue
        quiet = now - (inv.last_anomalous_at or inv.last_update)
        if inv.status != "RESOLVING" and quiet >= timedelta(minutes=cfg.resolve_after_min):
            changed[inv.investigation_id] = replace(inv, status="RESOLVING", last_update=now)
        elif inv.status == "RESOLVING" and quiet >= timedelta(minutes=cfg.resolve_after_min + cfg.close_after_min):
            changed[inv.investigation_id] = replace(inv, status="CLOSED", last_update=now)
    return sorted(changed.values(), key=lambda i: i.investigation_id)
