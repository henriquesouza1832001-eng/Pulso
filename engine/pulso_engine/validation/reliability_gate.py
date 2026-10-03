"""Portão puro para decidir se um candidato pode avançar fora da produção."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum

from .report import CandidateModelReport


class CandidateState(str, Enum):
    SHADOW = "SHADOW"
    EXPERIMENTAL = "EXPERIMENTAL"
    CANARY = "CANARY"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class ReliabilityMetrics:
    samples: int
    brier: float | None
    false_positive_rate: float | None = None
    recall: float | None = None
    calibration_error: float | None = None
    precision: float | None = None
    f1: float | None = None
    coverage: float | None = None
    median_lead_time_min: float | None = None


@dataclass(frozen=True)
class ReliabilityGateConfig:
    minimum_samples: int = 200
    minimum_brier_improvement: float = 0.05
    maximum_relative_fpr_regression: float = 0.10
    maximum_relative_recall_regression: float = 0.05
    calibration_must_not_regress: bool = True


class ReliabilityGate:
    def __init__(self, config: ReliabilityGateConfig = ReliabilityGateConfig()) -> None:
        self.config = config

    def evaluate(self, candidate_name: str, baseline: ReliabilityMetrics, candidate: ReliabilityMetrics,
                 generated_at: datetime | None = None) -> CandidateModelReport:
        samples = min(baseline.samples, candidate.samples)
        if samples < self.config.minimum_samples:
            return self._report(candidate_name, samples, baseline, candidate, GateStatus.INSUFFICIENT_DATA,
                                ("insufficient_samples",), generated_at)

        reasons: list[str] = []
        improvement = self._brier_improvement(baseline.brier, candidate.brier)
        if improvement is None or improvement < self.config.minimum_brier_improvement:
            reasons.append("brier_improvement")
        if self._fpr_regressed(baseline.false_positive_rate, candidate.false_positive_rate):
            reasons.append("false_positive_regression")
        if self._recall_regressed(baseline.recall, candidate.recall):
            reasons.append("recall_regression")
        if self.config.calibration_must_not_regress and self._worsened(baseline.calibration_error, candidate.calibration_error):
            reasons.append("calibration_regression")
        return self._report(candidate_name, samples, baseline, candidate,
                            GateStatus.FAIL if reasons else GateStatus.PASS, tuple(reasons), generated_at)

    def _report(self, candidate_name: str, samples: int, baseline: ReliabilityMetrics, candidate: ReliabilityMetrics,
                status: GateStatus, reasons: tuple[str, ...], generated_at: datetime | None) -> CandidateModelReport:
        improvement = self._brier_improvement(baseline.brier, candidate.brier)
        delta = None if baseline.brier is None or candidate.brier is None else candidate.brier - baseline.brier
        return CandidateModelReport(candidate=candidate_name, samples=samples, baseline=asdict(baseline),
                                    candidate_metrics=asdict(candidate),
                                    delta={"brier": None if delta is None else round(delta, 6),
                                           "brier_skill": None if improvement is None else round(improvement, 6)}, gate=status.value,
                                    reasons=reasons, generated_at=generated_at)

    def _brier_improvement(self, baseline: float | None, candidate: float | None) -> float | None:
        return None if baseline is None or candidate is None or baseline <= 0 else (baseline - candidate) / baseline

    def _fpr_regressed(self, baseline: float | None, candidate: float | None) -> bool:
        if baseline is None or candidate is None:
            return False
        return candidate > 0 if baseline == 0 else candidate > baseline * (1 + self.config.maximum_relative_fpr_regression)

    def _recall_regressed(self, baseline: float | None, candidate: float | None) -> bool:
        return baseline is not None and candidate is not None and candidate < baseline * (1 - self.config.maximum_relative_recall_regression)

    @staticmethod
    def _worsened(baseline: float | None, candidate: float | None) -> bool:
        return baseline is not None and candidate is not None and candidate > baseline
