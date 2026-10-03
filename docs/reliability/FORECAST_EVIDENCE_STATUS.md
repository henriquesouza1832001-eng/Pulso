# Forecast Evidence Status — 2026-10-03

## Executive result

The Forecast infrastructure is suitable for accumulating auditable prospective predictions, but there is not yet enough resolved real-world data to claim predictive skill. The correct conclusion is:

`PREDICTIVE EVIDENCE = INSUFFICIENT_DATA`

Forecast V2 remains `SHADOW / EXPERIMENTAL`. No tuning, V3 work, or promotion was performed.

## Baseline

- Engine: **795 passed**, 24 known compliance warnings, 113.77 s.
- Worker: **145 passed** in 13 files.
- Typecheck: **PASS**.
- Build and Worker dry-run: **PASS**; only the existing large-chunk warning and Wrangler's `@types/node` advisory were emitted.
- Registry/temporal focused tests after this change: **28 passed**.

## Temporal integrity

**PASS locally.** Replay rejects future outcome fields, keeps chronological order, rejects naive timestamps, and binds registry snapshots to an explicit UTC `data_cutoff`. The evidence is simulation-level; a long prospective corpus is not yet available.

## Forecast infrastructure

**PARTIAL → strengthened.** Every new registry snapshot now preserves explicit `forecast_at`, `data_cutoff`, `scope`, optional `event_id`, horizon, raw/calibrated probability, coverage, missingness, abstention, feature/model/calibrator versions, baseline version, flags, features, and a deterministic `snapshot_hash`. Outcome and resolution fields are intentionally excluded from the immutable snapshot and are appended later in the forecast record.

The Worker still stores the snapshot as an immutable hash-guarded registry row. Re-sending an existing `forecast_id` does not replace its snapshot.

## Outcome semantics

Resolved forecasts use outcome `0` or `1`. Open forecasts have no outcome. A forecast that cannot be observed in the resolution window is `void` with `outcome = null`; it is not treated as a negative. `UNKNOWN`/`UNRESOLVED` remain reporting-level states to be added if the external outcome resolver needs to distinguish them from the current void state.

## Metrics and baselines

The evaluation modules support base-rate reference, Brier/Brier Skill, log loss, ECE, precision, recall, FPR, lead time, coverage and abstention. Empty or statistically undefined samples return `None`/`INSUFFICIENT_DATA`; they are never converted to zero. Comparisons can include base rate, seasonal, anomaly-only, V1, V2 raw and V2 calibrated, but no winner is asserted without an adequate sample.

## Coverage, missingness and abstention

Coverage is propagated into V2 snapshots and low coverage can produce `INSUFFICIENT_DATA`/abstention. Existing tests cover full, partial and critical coverage, stale sensors and missing evidence. Missingness is retained as metadata; missing sensors are not treated as normality. A production-wide prospective coverage distribution (100% through 0%) is not yet accumulated.

## Prospective collection and external blockers

The pipeline has `FORECAST_REGISTRY` enabled in shadow mode and emits one immutable registry row for each new forecast. Real accumulated registry/outcome counts were not queried in this audit because the administrative endpoint requires external operator credentials. Therefore the following remain `BLOCKED_EXTERNAL` or `INSUFFICIENT_DATA`:

- Turso/D1 response-lost-after-commit and long-run storage chaos.
- Real prospective registry volume and outcome completeness.
- Calibration readiness on a temporal holdout.
- Brier Skill, ECE, FPR, recall and lead-time evidence at adequate N.

## Files and tests

- Registry implementation: `engine/pulso_engine/validation/forecast_registry.py`.
- Registry tests: `engine/tests/reliability/test_forecast_registry_cutoff.py`, `engine/tests/test_forecast_registry_pipeline.py`.
- Leakage/replay tests: `engine/tests/reliability/test_data_leakage.py`, `test_replay.py`, `test_temporal_splits.py`.
- Metrics/gate tests: `engine/tests/reliability/test_metrics.py`, `test_reliability_gate.py`.

No predictive readiness claim is made.
