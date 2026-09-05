# G4.4 Deterministic Floor, Registered Owner and Timebox Closure Qualification Results

## Disposition

**G4.4 fails simulation-realism qualification.** The experiment is technically
valid: batch `776890ab-6a96-4efc-b777-8d1817ac2a40` completed all eight matched
dialogues under the fixed `ollama/gpt-oss:120b` model with zero dialogue
failures and zero degraded LLM fallbacks. All 48 independent AI dimension
ratings completed after retrying only missing dimensions in two partial runs,
and all eight transcript SHA-256 values were independently recomputed from the
persisted public messages.

The candidate is not promoted because the RoomMind incident run fails the
same-speaker near-duplicate probe, the launch run is materially inconsistent
and incomplete, and the aggregate AI score is lower than Baseline. Manual
reading finds that the new deterministic boundaries work, but their repairs do
not yet produce a consistently more natural or procedurally complete meeting.
This remains exploratory development evidence. External human review was not
started.

## Frozen protocol

- Generation: `G4.4`
- Architecture: `g4.4-deterministic-floor-owner-and-timebox-closure`
- Source revision: `343c01b626ca7b31d1af768273d75c53c6e4bbd9`
- Random seed: `20260905`
- Dialogue and evaluator model: `ollama/gpt-oss:120b`
- Dialogue concurrency: one
- Conditions: traditional independent-memory agents and RoomMind
- Dialogues: 8/8 complete; dialogue failures: zero
- Degraded LLM fallbacks: zero
- Independent evaluation: 48/48 dimensions complete
- Transcript provenance: 8/8 SHA-256 recomputations match
- External human review: not started

## Independent AI evaluation

These scores are descriptive development measurements rather than a validated
composite endpoint.

| Dimension | Baseline mean | RoomMind mean | Difference |
|---|---:|---:|---:|
| Role and strategic fidelity | 5.75 | 4.75 | -1.00 |
| Information-boundary fidelity | 5.50 | 5.25 | -0.25 |
| Temporal coherence | 5.75 | 5.25 | -0.50 |
| Interaction structure | 5.00 | 5.25 | +0.25 |
| Multi-party dynamics | 5.00 | 5.50 | +0.50 |
| Procedural fidelity | 4.50 | 4.50 | 0.00 |
| Descriptive mean | 5.250 | 5.083 | -0.167 |

The paired scenario means are mixed: RoomMind is higher in supply-chain
negotiation (+0.167) and the leadership interview (+0.833), but lower in the
product-launch meeting (-1.500) and incident command (-0.333). This is not a
consistent treatment advantage.

## Run outcomes and mechanism evidence

| Scenario | Baseline messages | RoomMind messages | RoomMind outcome | AI paired difference |
|---|---:|---:|---|---:|
| Supply-chain negotiation | 79 | 52 | conditional, safety-timebox close | +0.167 |
| Product launch | 77 | 50 | conditional, safety-timebox close | -1.500 |
| Leadership interview | 70 | 45 | conditional, safety-timebox close | +0.833 |
| Incident command | 80 | 25 | conditional terminal outcome | -0.333 |

The shared deterministic cross-role handoff fired twice and no G4.1--G4.4
floor, target or registered-owner probe failed in any RoomMind run. The incident
run recorded one unregistered-owner rejection, six current-world grounding
rejections and seven broader public-grounding rejections. No unsupported
visible current-world action remained in the frozen RoomMind transcript. These
are direct signs that the G4.4 boundaries entered the real generation path.

All four RoomMind runs avoided `stalled`. Three timebox endings preserved open
work as `conditional`; the incident run ended as a conditional terminal
outcome. Thus the truthful-timebox mechanism also worked as designed.

However, the RoomMind incident run contains one same-speaker near-duplicate
diagnostic and fails `g4_same_speaker_near_duplicates_absent`. Baseline
diagnostics, although not treatment qualification gates, also expose 13
same-speaker near duplicates, 26 player-floor violations, seven unsupported
public-evidence claims, ten unsupported visible current-world actions and four
unregistered public assignments. This confirms that the control condition is
meaningfully less governed, but does not by itself establish that the resulting
RoomMind dialogue is globally more realistic.

## Manual reading of all four matched pairs

### Supply-chain negotiation

RoomMind reaches the substantive price, delivery and inspection terms much
faster and avoids Baseline's long sequence of repeated document requests. Its
information discipline and turn routing are better. It nevertheless loops for
many turns after the material agreement, lets the Quality Director promise to
email the final contract and payment sheet, and temporarily compresses the
5-percent liability cap and 10-percent defect-trigger escalation into ambiguous
language. This pair modestly favors RoomMind, but role authority and closure are
still visibly artificial.

### Product-launch decision

Baseline reaches a recognizable phased-launch approval early, although it then
loops, invents uploaded artifacts and proposes contradictory day-30 dates.
RoomMind is worse: it shifts between provisional and final readiness, has Sales
claim that Operations already confirmed readiness before Operations retracts
it, calls the player `John`, gives the player operational drafting work, and
introduces external names as substitute owners. It reaches the timebox without
a supported final launch decision. This is the clearest G4.4 regression.

### Leadership interview

Baseline allows all panelists to ask several questions in the same turn and
repeats nearly identical product and engineering prompts. RoomMind routes the
interview sequentially, preserves distinct panel roles, obtains concrete
evidence and closes all three evidence areas. Some retrospective numbers and
artifact identifiers are overly polished, but they are presented as candidate
claims about past work rather than fabricated current-world tool results. This
pair clearly favors RoomMind.

### Incident command

Baseline is highly repetitive and fabricates live rollback state, a checksum,
status-page publication and an unregistered forensic owner. RoomMind blocks
those failure classes and is much shorter. But it never obtains the required
formal containment confirmation or joint recovery-plan approval, lets Security
propose approval outside its authority, and ends after evidence capture rather
than recovery. Two Communications turns are nearly duplicates. The governance
is safer, but the incident procedure is incomplete; the pair is therefore
mixed rather than a RoomMind realism win.

## Gate decision

| Gate | Result | Evidence |
|---|---|---|
| Frozen source, model, seed and transcripts | Pass | manifest verified; 8/8 hashes recomputed |
| Engineering completion | Pass | 8/8 dialogues, 48/48 dimensions, zero dialogue failures |
| No RoomMind stalled outcome | Pass | all RoomMind outcomes conditional rather than stalled |
| G4.1--G4.4 floor, target and owner invariants | Pass | no applicable violation in RoomMind |
| Current-world evidence discipline | Pass | six incident claims rejected; none survive unsupported |
| Truthful timebox close | Pass | open work retained in conditional outcomes |
| Same-speaker repetition control | **Fail** | one near-duplicate in RoomMind incident command |
| Consistent paired realism progression | **Fail** | two pairs improve, two regress; AI mean difference -0.167 |
| Manual procedural and role realism | **Fail** | launch and incident runs remain materially incomplete/inconsistent |

## Successor requirement

The next iteration should not add another broad prompt. It should connect the
existing public ledger to a deterministic **meeting obligation graph**:

1. each required confirmation has one authorized role, evidence prerequisites
   and a terminal state;
2. contradictory confirmation/retraction reopens the exact obligation rather
   than producing generic closeout prompts;
3. task closure is prohibited while a required obligation lacks authorized
   evidence, but the system can close conditionally without repeating it;
4. semantic duplicate suppression applies across adjacent turns and different
   speakers when they merely restate the same unresolved obligation;
5. responsibility assignment is checked against role capability, not only name
   registration or external timing.

This targets the remaining realism defect: the system now blocks many unsafe
claims correctly, but it does not always transform those rejections into a
natural, role-correct path to a useful meeting outcome.
