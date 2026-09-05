# G1 engineering pilot disposition

## Identity

- Batch UUID: `44a9e7b3-05e8-4903-ad01-42a67e7f0134`
- Generation: `G1`
- Architecture: `g1-governed-independent-agents`
- Frozen source revision: `95b6594fef5cefebf1fbd669ffd6ce44d3455177`
- Study phase: exploration
- Intended cells: 4 scenarios × 2 conditions × 3 repetitions = 24

## Final disposition

The batch is classified as an **engineering-invalid exploratory pilot**. It is
retained for failure analysis but excluded from RoomMind-versus-Baseline
realism estimates, effect sizes, hypothesis tests, and confirmatory claims.

Final dialogue outcomes:

- 8 dialogue-completed runs;
- 16 technical dialogue failures;
- 12/12 Baseline failures from the same first-turn empty-memory defect;
- 4/12 RoomMind failures from unrecoverable empty visible model output with
  `finish_reason='length'`;
- no valid matched RoomMind/Baseline transcript pairs;
- independent six-dimension evaluation was not started.

## What the pilot establishes

The pilot establishes implementation defects and reliability risks only. It
does not establish that either dialogue architecture is more realistic. The
Baseline failure is deterministic missing-value handling, not evidence of weak
agent behavior. The RoomMind failures demonstrate cumulative reliability risk
from a high number of model calls in long autonomous sessions.

## Required gate before another full experiment

1. Run offline first-turn and empty-output regression checks.
2. Run one live Baseline and one live RoomMind canary with the frozen model.
3. Verify terminal status, transcript export, transcript hash, telemetry, and
   zero orphaned `running` rows.
4. Report any degraded fallback count separately.
5. Expand to all four scenarios only after the canary passes.

All original G1 sessions, traces, errors, partial transcripts, and debug bundle
remain immutable development evidence.
