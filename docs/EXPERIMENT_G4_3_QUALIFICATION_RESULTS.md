# G4.3 Cross-role Floor and Evidence-boundary Qualification Results

## Disposition

**G4.3 fails simulation-realism qualification.** The frozen engineering run is
valid: batch `ea08dd0f-bbec-45a7-93d1-dd8579281211` completed all eight matched
dialogues and all 48 independent AI dimension evaluations under the fixed
`ollama/gpt-oss:120b` model. There were no technical dialogue failures and all
eight persisted transcript hashes were recomputed successfully.

The candidate is not promoted because one RoomMind meeting ended `stalled`, a
RoomMind negotiation violated cross-role question ownership twice, and manual
reading found invented in-session artifacts, unregistered task owners and
incomplete closure. This is exploratory development evidence; no external
human review was started.

## Frozen protocol

- Generation: `G4.3`
- Architecture: `g4.3-cross-role-floor-and-evidence-boundary`
- Source revision: `fc0fff0286166966d31c76454ded7f4c46666da4`
- Random seed: `20260904`
- Dialogue and evaluator model: `ollama/gpt-oss:120b`
- Dialogue concurrency: one
- Dialogues: 8/8 complete; failures: zero
- Independent evaluation: 48/48 dimensions complete
- Transcript provenance: 8/8 SHA-256 recomputations match
- External human review: not started

## Independent AI evaluation

These are descriptive development results, not a validated composite score.

| Dimension | Baseline mean | RoomMind mean | Difference |
|---|---:|---:|---:|
| Role and strategic fidelity | 5.50 | 4.75 | -0.75 |
| Information-boundary fidelity | 4.75 | 5.75 | +1.00 |
| Temporal coherence | 4.75 | 5.25 | +0.50 |
| Interaction structure | 5.50 | 5.25 | -0.25 |
| Multi-party dynamics | 5.00 | 5.75 | +0.75 |
| Procedural fidelity | 5.75 | 4.75 | -1.00 |
| Descriptive mean | 5.208 | 5.250 | +0.042 |

The near-zero aggregate difference and opposing dimension movements do not
support a general RoomMind advantage. In particular, AI evaluation rewarded
some internally coherent dialogue despite unsupported current-world facts.

## Run outcomes and deterministic evidence

| Scenario | Baseline messages | RoomMind messages | RoomMind outcome | Key RoomMind finding |
|---|---:|---:|---|---|
| Supply-chain negotiation | 80 | 27 | conditional | two cross-role ownership violations |
| Product launch | 23 | 51 | stalled | 20-turn safety limit; three unresolved issues |
| Leadership interview | 77 | 19 | deferred | concise but interview ends materially incomplete |
| Incident command | 36 | 41 | conditional | invented evidence actions and unregistered owners |

The G4.3 cross-role integrity probe fails the RoomMind negotiation with two
violations. Offline replay with the successor detector identifies two
unsupported visible current-world claims in the incident transcript and two
explicit assignments to people absent from the frozen participant directory:
Emily Chen and Alex Patel. These successor diagnostics are evidence motivating
G4.4, not retroactive G4.3 qualification gates.

## Manual reading of all four matched pairs

### Supply-chain negotiation

RoomMind is shorter and less repetitive than Baseline, but the player still
restates facts controlled by Emma or the supplier CEO before yielding the
floor. The meeting ends conditionally with an unresolved material item. The
G4.3 prompt-level handoff instruction was therefore insufficient.

### Product launch

RoomMind repeatedly returns to the forecast and treats a purportedly posted
artifact as available without a registered simulated result. It reaches the
safety limit and ends stalled. Baseline has its own realism defects but reaches
a more recognizable close.

### Leadership interview

RoomMind is substantially shorter than the repetitive Baseline panel and keeps
roles more distinct, but it ends deferred after only 19 public messages without
completing the interview. Brevity alone is not procedural realism.

### Incident command

RoomMind invents posted verification hashes and subsequent review, assigns
blocking work to unregistered Emily Chen and Alex Patel, and later asks those
non-agents for results. It then loops around the unavailable response. Baseline
also invents live actions, but its conversational flow is more coherent.

## Gate decision

| Gate | Result | Evidence |
|---|---|---|
| Frozen source, model, seed and transcripts | Pass | manifest and 8/8 hashes verified |
| Engineering completion | Pass | 8/8 dialogues, 48/48 dimensions, zero technical failures |
| Cross-role question ownership | **Fail** | two violations in RoomMind negotiation |
| No RoomMind stalled outcome | **Fail** | product launch ends stalled |
| Current-world evidence discipline | **Fail** | posted/reviewed hashes survive without tool result |
| Registered role ownership | **Fail** | Emily Chen and Alex Patel become blocking owners |
| Manual paired realism progression | **Fail** | no consistent paired advantage; material defects in every RoomMind run |

## Successor requirement

G4.4 must turn cross-role handoff into a deterministic public invariant rather
than another prompt preference, reject unregistered in-session task owners while
still allowing explicitly external follow-up, recognize posted/shared/reviewed
artifact states as current-world terminal claims, and translate an exhausted
meeting timebox into a truthful conditional or deferred outcome rather than a
semantic system failure.

