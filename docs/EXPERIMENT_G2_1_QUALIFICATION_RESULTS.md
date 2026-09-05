# G2.1 grounded coordination qualification disposition

## Frozen identity

- Batch UUID: `3b9232e8-399e-4000-941d-b55abb3587a5`
- Generation: `G2.1`
- Architecture: `g2.1-grounded-coordinated-independent-agents`
- Source revision: `a012de1a5716a88cb847b3e6212921639fb62794`
- Model: `ollama/gpt-oss:120b`
- Study phase: exploration (`development_only`)
- Design: 2 scenarios × 2 conditions × 2 repetitions = 8 runs / 4 matched pairs
- Human blind review: not started

## Deterministic result

- 8/8 dialogue runs and 8/8 independent evaluations completed without a technical
  failure, orphaned worker, or degraded fallback.
- All eight verbatim transcript hashes were present, unique, and independently
  recomputed successfully.
- Every RoomMind run had independent role-memory partitions and applicable passing
  G2.1 probes for coordinator-history presence, increasing unique coordinator turns,
  and registered focus owners.
- No measured protected-information leak or authority violation occurred.
- No `completed` RoomMind result retained an unmet configured completion condition.
- RoomMind recorded 33 recovered LLM retries in 542 attempts; Baseline recorded 8 in
  327 attempts.

The new metadata/probe wiring and owner normalization therefore passed their engineering
gates.

## Six-dimension exploratory result

| Dimension | RoomMind | Baseline | Difference |
|---|---:|---:|---:|
| Role and strategic fidelity | 6.00 | 6.25 | -0.25 |
| Epistemic fidelity | 5.50 | 5.75 | -0.25 |
| Temporal coherence | 5.50 | 6.00 | -0.50 |
| Interaction-structure fidelity | 5.25 | 5.75 | -0.50 |
| Multi-party dynamics fidelity | 5.75 | 6.00 | -0.25 |
| Procedural fidelity | 5.00 | 6.00 | -1.00 |

The scenario-level procedural result was heterogeneous: incident command improved to
6.5 versus Baseline 6.0, while supply-chain negotiation fell to 3.5 versus 6.0.

## Progression and grounding gates

- Two of four RoomMind runs reached task completion; two supply-chain runs reached the
  20-turn safety limit with 9 and 10 unresolved issues. The required three task-grounded
  endings gate and the maximum-one-safety-ending gate failed.
- RoomMind did not exceed Baseline in maximum-turn endings, and no leak/authority gate
  failed.
- Procedural fidelity was lower than Baseline in the supply-chain scenario, so the
  both-scenarios progression gate failed.
- A RoomMind incident response invented exact SHA-256 values and a memory-dump filename.
  Supply-chain messages also claimed unsupported attachments. The explicit grounded-
  artifact gate failed.

## Failure mechanism and disposition

Grounding instructions prevented some unsupported state transitions, but the public
agents could still utter fabricated evidence. More importantly, the deterministic
coordinator continued to classify incidental offered artifacts and blockers as required
work. A blocked work item then dominated focus for multiple turns, while the three
registered negotiation conditions remained only proposed. This created an expanding
work-item backlog and worsened closure quality.

G2.1 fails qualification and must not advance to the 24-cell exploration. A later
candidate should distinguish task-critical obligations from incidental conversational
offers, prevent one blocked item from monopolizing focus, and enforce public-utterance
grounding before speech rather than relying only on prompts and post-hoc extraction.
G2.1 data remain frozen and must not be pooled with later candidates.
