# G3 ledger-grounded multi-agent qualification protocol

## Purpose

G3 tests whether RoomMind can preserve the independent-role and private-memory
benefits of the Stanford-style agent loop while making the simulated public
world authoritative, auditable, and internally consistent.

- Generation: `G3`
- Architecture: `g3-ledger-grounded-multi-agent-simulation`
- Study phase for initial qualification: exploration only
- Baseline: the frozen conventional independent-agent condition using the same
  scenario information, visible model, sampling policy, and turn budget

G1-G2.3 artifacts remain frozen. G3 results must be stored as a new batch and
must never overwrite earlier transcripts, hashes, manifests, or evaluations.

## Architectural treatment

Each RoomMind character retains its own seed memories, retrieved memories,
plans, and reflections. All agents additionally read one shared Public World
Ledger containing only public entities and validated transitions.

The public lifecycle is:

`proposed -> committed -> in_progress -> submitted -> verified -> accepted`

`rejected` and `blocked` are explicit alternatives. Before an NPC speaks, it
must emit a structured public intent. The system validates role authority,
simulation scope, inline evidence, and lifecycle strength. Only the validated
transition is rendered into speech and committed to the ledger. A post-hoc LLM
extractor may attach exact public evidence but may not create a stronger
terminal transition than the ledger supports.

## Frozen qualification design

Use the same matched scenarios and replications as the most recent G2
qualification unless a separate frozen manifest explicitly documents a change.
Generation and evaluation remain separate processes. Freeze dialogue JSON,
transcript hashes, provider/model labels, random seeds, generation settings,
task results, Public World Ledger, technical telemetry, and integrity probes
before starting AI evaluation.

## Engineering gates

All applicable gates must pass:

1. Every RoomMind run contains `roommind-public-world-ledger-v1`.
2. Every committed ledger event has an ID, public quote, actor, simulation turn,
   and `prevalidated_agent_intent` provenance.
3. No artifact/action/verification reaches submitted, verified, or accepted
   without concrete inline evidence and an allowed in-session scope.
4. No public utterance claims a stronger lifecycle than its validated intent.
5. The simulation clock is monotonic and no event occurs in a future turn.
6. Every entity uses an allowed lifecycle state.
7. A task cannot be marked completed while required work remains unresolved.
8. All legacy G2.3 coordination, focus, memory-partition, transcript-integrity,
   and public-grounding probes continue to pass.
9. Dialogue generation has no technical failures or degraded public fallback.
10. Transcript hashes recompute exactly after freezing.

## Realism progression gates

The independent six-dimension AI evaluation is diagnostic in exploration. G3
may progress to external blind review only when:

- RoomMind procedural fidelity exceeds its matched Baseline mean;
- RoomMind temporal and epistemic fidelity are not below Baseline;
- direct transcript inspection finds zero unsupported completed external
  actions, fabricated artifacts, invented links/hashes, or authority violations;
- naturalness and interaction-structure ratings are not below Baseline;
- endings truthfully distinguish completed, conditional, deferred, blocked,
  failed, and stalled outcomes.

AI scores cannot replace blind human realism review. If these gates pass, freeze
the exact original-language transcripts and create bilingual review forms while
keeping condition labels hidden from reviewers.

## Failure disposition

Any gate failure freezes the G3 batch as diagnostic evidence. Fixes require a
new generation or explicitly versioned minor generation; failed transcripts are
not regenerated in place and completed dimensions are not overwritten.
