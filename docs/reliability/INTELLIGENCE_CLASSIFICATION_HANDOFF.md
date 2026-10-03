# Intelligence classification handoff — 2026-10-03

## Finding and root cause

Sports/editorial headlines could become publishable through source count alone. The old gate treated independent publisher IDs as sufficient even when every signal described a scheduled or editorial topic. This was reproduced with match schedules, “onde assistir”, betting/odds and Brasileirão bursts.

## Changes delivered

- `importance.assess` now emits a semantic role: `EDITORIAL_ONLY`, `SCHEDULED_CONTEXT`, `OPERATIONAL_SIGNAL` or `POTENTIAL_INCIDENT`.
- `events.is_publishable` rejects clusters containing only editorial/scheduled roles. This is not a football keyword block.
- Operational context remains eligible for blackout, evacuation, fire, interdiction and transport/security failures.
- `EventStats.extra.content_roles` preserves the classification for downstream inspection.

## Regression evidence

- Editorial hard negatives at 10/50/100/500/1000 signals: PASS.
- Paraphrases and tracking-parameter variants: PASS.
- Positive controls for metro failure, stadium evacuation, blackout and concert transport failure: PASS.
- Full Engine suite: 794 passed, 24 known compliance warnings.

## Invariants and limitations

Volume is not evidence of independent origin. This change gates publication but does not yet expose the role as a versioned public API field, nor does it replace provenance measurement at 50–1000 reposts. The Worker invalid-UF finding (`/api/pulse/state/ZZ`) remains a separate platform handoff.

Forecast V1/V2 should consume `EDITORIAL_ONLY` only as non-operational context; no forecast tuning or model promotion was performed.
