# G3.9 Qualification Results

## Disposition

**G3.9 fails end-to-end qualification.** All eight matched dialogues and all
six-dimension evaluations completed without a technical generation failure,
but two of four RoomMind sessions ended stalled and the mechanism introduced
for natural quote-level joint confirmation did not activate in any RoomMind
run. This batch remains exploratory development evidence.

## Frozen experiment

- Batch: `8388208e-6535-4723-93e1-387e287d4783`
- Generation: `G3.9`
- Architecture: `g3.9-natural-joint-confirmation-closure`
- Source revision: `825fa672b39216a00a40e89af4e5ef45a12cdae1`
- Manifest SHA-256: `b539810ad458b43147a81edd5a6eba776c3da429e4f34ca73faa0d615501a963`
- Fixed model: `ollama/gpt-oss:120b`
- Design: four scenarios, one matched RoomMind/Baseline run per scenario,
  concurrency one, maximum 20 turns, exploration only

## Integrity and stability

- 8/8 public transcripts were frozen; generation failures were zero.
- Independent evaluation completed all 48 run-dimension cells after retrying
  only missing dimensions.
- Recomputed transcript SHA-256 values match all eight stored values.
- No run used an LLM degraded fallback.
- RoomMind dialogue-safe fallback counts were 1, 0, 4, and 0.
- Two RoomMind runs fail the non-vacuous G3.9 integrity gate because their
  final completion status is `stalled`.
- `quote_confirmation_commit_count` is zero in every RoomMind run, so the
  central G3.9 mechanism has no observed end-to-end activation evidence.

## Independent AI evaluation

| Dimension | RoomMind | Baseline | Difference |
|---|---:|---:|---:|
| Role and strategic fidelity | 5.25 | 6.00 | -0.75 |
| Information boundaries | 5.00 | 5.25 | -0.25 |
| Temporal coherence | 3.75 | 6.00 | -2.25 |
| Interaction structure | 3.75 | 5.75 | -2.00 |
| Multi-party dynamics | 4.75 | 5.00 | -0.25 |
| Procedural fidelity | 4.25 | 5.00 | -0.75 |

These scores are secondary evidence. The evaluator over-credits internally
consistent but unsupported actions in several Baseline transcripts, so the
table does not establish Baseline validity. It does establish that G3.9 has no
automated realism advantage in this sample.

## Convergence

| Scenario | RoomMind turns | Final status | Stop reason | Closure lock |
|---|---:|---|---|---|
| Supply-chain negotiation | 15 | stalled | no task progress | absent |
| Product launch | 15 | completed | completion conditions met | present |
| Panel interview | 20 | stalled | safety limit | absent |
| Incident command | 2 | conditional | terminal conditional outcome | absent |

## Manual paired reading

- **Supply-chain negotiation:** both conditions become repetitive. RoomMind
  confirms a 45-day lead time despite the public 30-day target and later
  reopens delivery, then waits on another promised plan. Baseline is much
  longer and repeatedly invents delivery of contract documents. Neither is a
  strong realistic meeting; RoomMind is shorter but not convergent.
- **Product launch:** Baseline reaches a concise joint decision in four turns.
  RoomMind develops useful operating safeguards but reopens readiness after a
  launch decision, then repeats requests for a staffing plan before eventually
  closing. Baseline is more natural in this pair.
- **Panel interview:** both conditions ask overlapping questions and continue
  after evidence requirements are satisfied. RoomMind retains somewhat clearer
  functional roles, but it still loops and reaches the safety limit.
- **Incident command:** RoomMind truthfully stops at a conditional boundary
  instead of inventing containment and rollback. Baseline appears complete but
  fabricates live firewall, rollback, evidence-preservation and publication
  actions without tools. RoomMind is epistemically safer, but its six-message
  exchange omits the Security Lead and is procedurally incomplete.

## Root cause and next generation

G3.9 treated recurring symptoms as quote-normalization problems. The frozen
run shows the remaining failure is broader: prompts advise agents not to
repeat, but no deterministic dialogue-level gate suppresses near-duplicate
requests; the player can accept a value that contradicts a public target; and
ordinary conversational exhaustion is recorded as a technical `stalled`
result instead of a truthful conditional or deferred business outcome. G4.0
therefore moves these controls from prose instructions into bounded,
domain-neutral governance.
