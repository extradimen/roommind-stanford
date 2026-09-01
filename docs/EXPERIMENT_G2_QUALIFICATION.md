# G2 coordination qualification protocol

## Purpose

Qualify the deterministic G2 turn coordinator before any full realism experiment.
This is engineering and exploratory evidence, not confirmation evidence.

## Frozen candidate

- Generation: `G2`
- Architecture: `g2-coordinated-independent-agents`
- Fixed provider/model: `ollama/gpt-oss:120b`
- Conditions: RoomMind and the unchanged independent-memory-agent Baseline
- Shared player: `public-only-comparison-player-v1`
- Concurrency: 1
- Safety maximum: 20 turns
- Maximum stagnant turns: 6
- Scenarios: supply-chain negotiation (1) and incident command (4)
- Repetitions: 2 per condition and scenario (8 dialogues)
- AI evaluation starts only after all dialogue artifacts are frozen
- Human review does not start automatically

## Deterministic gates

1. 8/8 dialogue runs reach a terminal stored state without code failure or orphaned worker.
2. 8/8 transcript exports have nonempty, unique, recomputable SHA-256 values.
3. All integrity probes pass; no empty public messages or unknown speakers occur.
4. Every RoomMind run records coordinator focus history and independent role-memory partitions.
5. Confirmed-state locking, overdue commitment focus, focus-owner routing, and closeout
   activation pass the offline smoke tests.
6. Degraded fallbacks, provider retries, and transport errors are disclosed separately.

## Exploratory progression gates

These gates select whether G2 is worth a larger exploration; they are not realism claims.

1. At least three of four RoomMind sessions end by a task-grounded completed,
   conditional, deferred, or failed outcome rather than safety-limit/no-progress stall.
2. No more than one RoomMind session reaches the safety turn limit.
3. RoomMind does not exceed Baseline in the number of safety-limit endings.
4. Condition-blinded procedural-fidelity mean is not lower than Baseline in both
   qualification scenarios.
5. No observed gain is accompanied by a protected-information leak or authority violation.

Failure of a progression gate leads to diagnosis and a new G2 candidate version. It
does not justify silently changing this batch or excluding failed runs.

## Next stage

If all deterministic and progression gates pass, run a new 24-cell G2 exploration
over all four scenarios with a new seed schedule. Keep G1.1 frozen, keep automatic
and human evaluation independent, and do not pool G1.1 and G2 as if they were one
treatment generation.
