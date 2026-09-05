# G4.2.1 Grounded Addressee and Confirmation Qualification Results

## Disposition

**G4.2.1 fails end-to-end simulation-realism qualification.** The engineering
rerun is valid: all eight matched dialogues and all 48 independent AI dimension
evaluations completed, no dialogue used an LLM degraded fallback, every
transcript hash recomputed correctly, and the frozen source revision and model
lock match the manifest. The new addressee and confirmation alignment paths
also operated without the G4.2 runtime fault.

The candidate is not promoted because two of four RoomMind sessions ended
`stalled` at the safety limit. Independent AI evaluation gives RoomMind only a
small descriptive advantage across the 24 dimension observations, and manual
paired reading finds a mixed 2--2 pattern with material role, evidence and
closure defects. This is exploratory development evidence, not confirmatory
evidence, and no external human review was started.

## Frozen protocol and artifact integrity

- Batch: `fbeacf41-d13b-449a-ad7d-9783442d6823`
- Generation: `G4.2.1`
- Architecture: `g4.2.1-grounded-addressee-and-confirmation`
- Source revision: `be2c6c79df13ace1e56f707e8231d8259d2af011`
- Manifest SHA-256: `aca80cdf1f1a400a188714f222dc904dde33f21f361075376d1999220428919b`
- Generation and evaluator model: `ollama/gpt-oss:120b`
- Random seed: `20260904`
- Concurrency: one
- Frozen dialogues: 8/8
- Dialogue failures: 0
- Independent AI dimensions: 48/48 after retrying only the two initially
  missing dimensions
- Transcript hash verification: 8/8 match the persisted SHA-256 values
- External human review: not started

The first G4.2 batch remains invalid engineering evidence. G4.2.1 is a new
source revision and a new batch; it did not retry failed rows across code
versions.

## Run-level engineering results

| Scenario | Condition | Turns | Messages | Final state | Governor stop | Degraded fallback | Safe fallback | Silent recovery | Addressee reconciliation | Confirmation alignment | Integrity |
|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| Supply-chain negotiation | Baseline | 20 | 77 | n/a | baseline limit | 0 | 1 | n/a | n/a | 0 | baseline checks pass |
| Supply-chain negotiation | RoomMind | 20 | 52 | stalled | safety limit | 0 | 2 | 3 | 0 | 2 | fail: stalled |
| Product launch | Baseline | 7 | 28 | n/a | completed | 0 | 2 | n/a | n/a | 0 | baseline checks pass |
| Product launch | RoomMind | 5 | 14 | completed | completion conditions | 0 | 1 | 0 | 2 | 0 | pass |
| Leadership interview | Baseline | 20 | 74 | n/a | baseline limit | 0 | 4 | n/a | n/a | 0 | baseline checks pass |
| Leadership interview | RoomMind | 16 | 40 | completed | completion conditions | 0 | 0 | 2 | 1 | 2 | pass |
| Incident command | Baseline | 9 | 36 | n/a | completed | 0 | 1 | n/a | n/a | 0 | baseline checks pass |
| Incident command | RoomMind | 20 | 55 | stalled | safety limit | 0 | 4 | 4 | 3 | 3 | fail: stalled |

All applicable RoomMind runs pass the G4.2 structured-question-target versus
public-speech probe. There are no recorded G4.1 player-floor violations in the
RoomMind runs. The G4.2 mechanisms are therefore active and internally
consistent, but they do not guarantee task convergence.

`all_applicable_passed=true` on a Baseline row must not be interpreted as a
realism pass. RoomMind-specific ledger, memory, closure and grounding checks are
not applicable to Baseline. For example, the supply-chain Baseline contains
unsupported emailed-contract claims and invented bank details, and the incident
Baseline contains unsupported current-world rollback/status-page actions even
though its applicable implementation checks pass.

## Independent six-dimension AI evaluation

The protocol reports dimensions separately. The overall means below are a
descriptive arithmetic summary for diagnosis, not a preregistered composite
realism score.

| Dimension | Baseline mean | RoomMind mean | Difference |
|---|---:|---:|---:|
| Role and strategic fidelity | 5.75 | 6.25 | +0.50 |
| Information-boundary fidelity | 6.25 | 5.75 | -0.50 |
| Temporal coherence | 6.25 | 5.25 | -1.00 |
| Interaction structure | 5.00 | 5.75 | +0.75 |
| Multi-party dynamics | 5.00 | 5.25 | +0.25 |
| Procedural fidelity | 5.00 | 5.75 | +0.75 |
| Descriptive mean of all 24 observations | 5.542 | 5.667 | +0.125 |

Pair-level descriptive means are:

| Scenario | Baseline | RoomMind | Difference |
|---|---:|---:|---:|
| Supply-chain negotiation | 5.833 | 5.667 | -0.166 |
| Product launch | 6.000 | 5.500 | -0.500 |
| Leadership interview | 4.333 | 6.000 | +1.667 |
| Incident command | 6.000 | 5.500 | -0.500 |

Only the interview is a clear AI-scored RoomMind pair win. With one repetition
per cell, three lower-scored RoomMind pairs, a tiny aggregate difference and no
human ratings, these scores do not support a claim that G4.2.1 is generally more
realistic.

## Manual reading of all four matched pairs

### Supply-chain negotiation

RoomMind is less meandering than Baseline and avoids Baseline's late fictional
contract execution, bank account, shipment and inspection logistics. It also
retains the 84 RMB and 30-day terms. However, it opens with the wrong currency
(`$12.50`), has the player answer a quality-capacity question on the supplier's
behalf, renders a purported protocol and certificate in chat despite describing
them as future documents, repeatedly reopens already accepted terms, and stalls
after 52 messages. Baseline is longer and more seriously fabricates off-channel
actions, but it reaches a recognizable negotiated package. Manual preference:
RoomMind is less unsafe, but neither transcript qualifies as a clean realistic
meeting.

### Product launch

RoomMind completes quickly and the new addressee reconciliation activates
twice. It nevertheless exposes protected customer identities/commitments,
omits the requested budget amount and contingency, and treats a generic budget
approval as sufficient for launch closure. Baseline develops an explicit
stop-loss threshold and ownership plan, although its participants temporarily
propose conflicting thresholds and it also leaks protected commitments. Manual
preference: Baseline for substantive decision procedure; neither is fully
epistemically clean.

### Leadership interview

RoomMind is substantially better than Baseline at panel coordination. Baseline
repeats almost identical Product VP and Engineering Director questions across
many turns and lets all panelists pile onto candidate-directed questions in the
same turn. RoomMind gives each role more distinct participation and completes
in fewer public messages. Its remaining faults are important: the candidate
asks interviewers to supply evidence for the candidate's own past project, an
interviewer invents a post-launch report, the evidence stage is reopened after
the candidate said it was complete, and detailed CPU evidence remains a future
follow-up. Manual preference: RoomMind, with reservations.

### Incident command

Baseline follows a more recognizable triage-containment-recovery sequence and
reaches a bounded ownership plan, but it falsely claims live rollback,
snapshots, status-page updates and service recovery without registered tool
results. RoomMind is initially more cautious about evidence preservation, then
gets trapped waiting for `containment_active`, repeatedly asks for the same
verification, invents exact firewall/process timestamps, and stalls even after
the SRE lead finally states that containment remains active and approves the
rollback. Manual preference: Baseline for meeting flow, but neither is safe
enough for a realistic incident simulation.

Across pairs, manual preference is mixed rather than a general RoomMind win:
RoomMind is favored in negotiation safety and interview coordination; Baseline
is favored in launch substance and incident flow. The qualitative review also
shows that the independent AI evaluator is too tolerant of internally coherent
but unsupported current-world claims.

## Gate decision

| Gate | Result | Evidence |
|---|---|---|
| Frozen source/model/seed manifest | Pass | Exact G4.2.1 manifest and source revision present |
| All dialogues and dimensions complete | Pass | 8/8 dialogues; 48/48 AI dimensions |
| No technical dialogue failure | Pass | 0 failed runs; 0 degraded fallbacks |
| Transcript provenance and hashes | Pass | 8/8 SHA-256 recomputations match |
| Grounded addressee interface | Pass | 6 reconciliations; no structured/public target mismatch |
| Authorized confirmation alignment | Pass as mechanism | 7 alignments; no speech-act mismatch rejection |
| RoomMind sessions do not stall | **Fail** | Negotiation and incident command hit the 20-turn safety limit |
| Completion and closure integrity | Partial | Launch/interview pass; two configured tasks do not close |
| Manual realism progression | **Fail** | Mixed 2--2 preference and material defects in every pair |
| Evidence sufficient for promotion | **Fail** | One repetition; no blind human review; no consistent pair advantage |

## What G4.2.1 established and what remains

G4.2.1 successfully fixes its narrow interface target: named NPC questions are
reconciled to the visible addressee, player-floor handoff no longer fires on
those questions, and some clear authorized confirmations survive generic model
intent labels. The engineering rerun also demonstrates that the missing
telemetry import is fixed.

The remaining bottleneck is now the semantic contract between public speech and
task state, not basic model availability. In particular:

1. completion projection still misses plausible confirmation language in the
   negotiation and incident tasks;
2. player-agent speech can answer on behalf of another role;
3. simulated documents/data can be written directly into dialogue without the
   same capability boundary applied to external actions;
4. completion conditions can also close too early when a Boolean approval lacks
   the substantive details requested by the meeting;
5. the evaluator needs explicit penalties for unsupported current-world claims
   and for premature or stalled closure, rather than rewarding mere internal
   fluency.

Any successor must receive a new generation identifier, frozen source revision
and new matched batch. G4.2.1 artifacts must remain unchanged.
