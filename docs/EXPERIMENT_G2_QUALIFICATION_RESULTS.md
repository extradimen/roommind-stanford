# G2 coordination qualification disposition

## Frozen identity

- Batch UUID: `2e9e1a8b-a03d-4b0e-90f2-0652bf7a77d5`
- Generation: `G2`
- Architecture: `g2-coordinated-independent-agents`
- Source revision: `ba23b9c1ea0ab685cb207d0bab321dfda5c97c74`
- Model: `ollama/gpt-oss:120b`
- Study phase: exploration (`development_only`)
- Design: 2 scenarios × 2 conditions × 2 repetitions = 8 runs / 4 matched pairs
- Human blind review: not started

## Engineering result

- 8/8 dialogues and 8/8 independent six-dimension evaluations completed.
- All eight public transcripts were nonempty; their SHA-256 values were unique and
  independently recomputed from the archived verbatim messages.
- No dialogue failure, orphaned worker, degraded fallback, protected-information leak,
  or measured authority violation occurred.
- RoomMind recorded coordinator histories of 16, 20, 20, and 13 turns and retained
  independent memory partitions for every role.
- RoomMind incurred 33 recovered LLM retry events in 588 attempts; Baseline incurred
  10 in 338 attempts. These are disclosed reliability observations, not realism scores.

The forensic probe wiring was incomplete: the batch manifest and architecture version
were not copied into each session run configuration, so the G2-specific probe checks
were exported as not applicable. Manual replay also found one focus owner encoded as
`player` rather than the registered `user` alias. General transcript probes passed, but
the G2-specific deterministic gate therefore did not receive a valid automated pass.

## Exploratory six-dimension result

Scores use the registered 1–7 condition-blinded AI rubric.

| Dimension | RoomMind | Baseline | Difference |
|---|---:|---:|---:|
| Role and strategic fidelity | 5.75 | 6.25 | -0.50 |
| Epistemic fidelity | 5.75 | 6.00 | -0.25 |
| Temporal coherence | 5.75 | 6.00 | -0.25 |
| Interaction-structure fidelity | 6.00 | 5.25 | +0.75 |
| Multi-party dynamics fidelity | 5.00 | 5.50 | -0.50 |
| Procedural fidelity | 5.00 | 5.50 | -0.50 |

Interaction structure improved, but the registered procedural progression gate failed:
RoomMind procedural fidelity was 5.0 versus Baseline 5.5 in both qualification scenarios.
Three of four RoomMind runs reached a task-grounded completion and one reached the safety
limit, so progression gates 1–3 and the no-leak/no-authority-violation gate passed.

## Failure mechanism and disposition

The coordinator successfully created a stable topic/owner order, but it treated many
incidental promises as required work. This led roles to chase simulated attachments,
links, reports, hashes, and actions instead of resolving the registered task state. One
incident dialogue also asserted completion while three required conditions remained
unconfirmed. The architecture improved meeting order without reliably improving business
process truthfulness.

G2 is frozen as a failed qualification candidate and must not proceed to a 24-cell
exploration. G2.1 retains independent Stanford-style role memories and the deterministic
coordinator while adding grounded work claims, routable owner selection, evidence-based
terminal-state reconciliation, and correctly frozen probe metadata. G2 and G2.1 evidence
must not be pooled.
