"""Conversão entre a investigação do Sentinela (`research.sentinel.Investigation`) e o formato do banco/ingest.

Fica fora de `research/` de propósito: é a costura com o Worker (campo `investigations` do IngestBatch e a rota
`GET /api/admin/investigations`), mantida junto do pipeline. Sem rede e sem banco.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .research.sentinel import Investigation


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def investigation_dict(inv: Investigation) -> dict:
    """Formato do campo `investigations` do ingest (`InvestigationPoint` em contracts.ts)."""
    return {
        "id": inv.investigation_id, "scope": inv.scope, "category": inv.category, "status": inv.status,
        "started_at": _iso(inv.started_at), "last_update": _iso(inv.last_update),
        "last_anomalous_at": _iso(inv.last_anomalous_at) if inv.last_anomalous_at else None,
        "initial_anomaly": round(float(inv.initial_anomaly), 4), "anomaly": round(float(inv.anomaly), 4),
        "evidence_count": int(inv.evidence_count), "official_confirmation": bool(inv.official_confirmation),
        "reasons": list(inv.reasons)[:12],
    }


def investigation_from_row(row: dict) -> Investigation:
    """Reconstrói a investigação a partir da linha da rota admin (`reasons` vem como texto JSON; o booleano como 0/1).
    Os hashes dos sinais não são guardados: o Sentinela os reconstrói a cada rodada a partir dos sinais atuais."""
    reasons = row.get("reasons")
    if isinstance(reasons, str):
        try:
            reasons = json.loads(reasons)
        except ValueError:
            reasons = []
    started = _parse(row.get("started_at")) or datetime.now(timezone.utc)
    return Investigation(
        investigation_id=str(row["id"]), scope=str(row["scope"]), category=str(row["category"]), status=str(row["status"]),
        started_at=started, last_update=_parse(row.get("last_update")) or started,
        initial_anomaly=float(row.get("initial_anomaly") or 0), anomaly=float(row.get("anomaly") or 0),
        evidence_count=int(row.get("evidence_count") or 0), official_confirmation=bool(row.get("official_confirmation")),
        reasons=tuple(str(r) for r in (reasons if isinstance(reasons, list) else [])),
        last_anomalous_at=_parse(row.get("last_anomalous_at")),
    )
