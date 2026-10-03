"""Relatório serializável do Reliability Gate, sem persistência nem integração."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class CandidateModelReport:
    candidate: str
    samples: int
    baseline: dict[str, Any]
    candidate_metrics: dict[str, Any]
    delta: dict[str, float | None]
    gate: str  # PASS | FAIL | INSUFFICIENT_DATA
    reasons: tuple[str, ...]
    generated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["reasons"] = list(self.reasons)
        data["generated_at"] = self.generated_at.isoformat() if self.generated_at else None
        return data
