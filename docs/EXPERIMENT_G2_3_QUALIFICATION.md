# G2.3 grounded bounded-focus qualification protocol

## Purpose

Test whether stateful public-output grounding, focus bounding across both configured state and
critical work, truthful outcome resolution, and append-only evaluation retries repair the
specific failures frozen in G2.2. This remains development-only exploration.

## Frozen candidate requirements

- Generation: `G2.3`
- Architecture: `g2.3-grounded-bounded-focus-agents`
- Fixed provider/model: `ollama/gpt-oss:120b`
- Scenarios: supply-chain negotiation (1) and incident command (4)
- Conditions: RoomMind and unchanged independent-memory-agent Baseline
- Repetitions: 2 per condition/scenario
- Concurrency: 1; safety maximum: 20; maximum stagnant turns: 6
- Use a new random seed; freeze all transcripts before AI evaluation
- Human review does not start automatically

## Candidate mechanisms

1. Public-output validation rejects completed external side effects that the text simulator
   cannot verify: sent/emailed/attached/uploaded/archived artifacts, repository-style URLs,
   and asserted checksum verification. Future commitments remain valid auditable work.
2. Every ordinary coordinator focus, whether a configured state variable or critical work
   item, receives at most two consecutive turns. The next turn rotates to the best unresolved
   alternative or becomes an explicit `outcome_resolution` focus.
3. Outcome resolution must preserve unmet conditions and request a truthful confirmed,
   rejected, blocked, handed-off, conditional, deferred, or failed result.
4. Integrity probes independently rescan the final transcript and verify bounded focus streaks
   and grounded outcome-resolution provenance.
5. Evaluation retries retain every completed dimension and invoke the observer only for
   dimensions whose score is missing. Attempt telemetry is appended rather than replaced.

## Deterministic gates

1. 8/8 runs terminate without code failure, orphaned worker, or missing transcript.
2. All transcript hashes are nonempty, unique, and independently recomputable.
3. Every RoomMind public-evidence, memory, owner, coordination, focus-bound, and
   outcome-resolution probe passes under an independent final-export scan.
4. No RoomMind transcript contains an unsupported completed external-action claim, external
   location, or checksum-verification claim.
5. No ordinary focus exceeds two consecutive turns. A sole unresolved focus must transition
   to `outcome_resolution` on the next coordinator turn.
6. No completed result retains an unmet configured completion condition.
7. A partial evaluator retry changes only the missing dimensions and preserves prior scores,
   evidence, errors, and attempt telemetry for all completed dimensions.
8. Provider retries, grounding rejections, fallbacks, and transport errors are disclosed.

## Progression gates

The G2 progression gates remain unchanged:

1. At least three of four RoomMind sessions have a task-grounded terminal outcome.
2. No more than one RoomMind session reaches the safety limit.
3. RoomMind does not exceed Baseline in safety-limit endings.
4. Condition-blinded procedural fidelity is not lower than Baseline in either scenario.
5. No gain is accompanied by protected-information leakage or authority violation.

Failure freezes G2.3 as diagnostic evidence. Passing this eight-dialogue qualification is
required before any 24-cell exploration or human review.
