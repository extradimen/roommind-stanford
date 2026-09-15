# G2.2 critical grounded coordination qualification disposition

## Frozen evidence

- Batch: `a0a86a39-69ef-4da3-b76a-afb0ee0d5d25`
- Generation: `G2.2`
- Architecture: `g2.2-critical-grounded-coordinated-agents`
- Source revision: `4848d9fbd3282d247fb9dc77bb57941315b0ec2c`
- Provider/model: `ollama/gpt-oss:120b`
- Seed: `202609023`
- Scope: development-only exploration

All eight dialogues reached a stored terminal state without a code failure or degraded
fallback. All 48 independent AI dimension evaluations eventually completed; one long
RoomMind transcript required two targeted retries because the evaluator returned truncated
JSON. Human review was not started.

## Integrity disposition

All eight transcript SHA-256 values were nonempty, unique, and independently recomputed from
the verbatim stored public messages. Speaker, sequence, model-lock, memory-partition, and
coordination-history probes passed.

The public-evidence probe nevertheless produced a false negative. Forensic transcript review
found unsupported completed external-action claims in RoomMind output, including a signed
letter being emailed as an attachment and an incident archive being uploaded to a fabricated
`repo://` location with checksum verification. These claims violate the G2.2 grounding
requirement even though the original regular expressions did not detect them.

The task-critical work-focus probe also passed vacuously. Across all four RoomMind sessions,
all 70 coordinator turns focused on `state_variable`; no `work_item` or
`outcome_resolution` focus was selected. State-variable focus streaks reached 12–16 turns.
The new work-priority and outcome-resolution mechanisms therefore were not exercised by the
qualification dialogues.

## Progression results

- Task-grounded terminal outcomes: 1/4 RoomMind sessions (`conditional`), below the required
  3/4.
- Safety-limit endings: 2/4 RoomMind sessions, above the permitted maximum of one.
- Supply-chain procedural fidelity: RoomMind 5.0 vs Baseline 5.5; gate failed.
- Incident-command procedural fidelity: RoomMind 6.0 vs Baseline 5.0; gate passed.
- Deterministic protected-secret leakage and authority-violation counts were zero.

Across all scenarios, RoomMind's AI means were higher for role/strategy (6.0 vs 5.5) and
procedural fidelity (5.5 vs 5.25), but lower for epistemic fidelity (5.25 vs 5.5), temporal
coherence (5.75 vs 6.0), interaction structure (5.0 vs 5.75), and multi-party dynamics
(4.75 vs 5.75). These small exploratory cells are diagnostic and are not confirmatory
effect estimates.

## Decision

G2.2 does not qualify for the 24-cell exploration or human review. Freeze the batch without
editing or excluding failed cells. The next candidate must validate completed external-action
claims against an explicit public artifact ledger, bound repeated focus for state variables as
well as work items, force truthful outcome resolution when a sole focus cannot advance, and
make evaluation retries append only the missing dimensions.
