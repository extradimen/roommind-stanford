# G4.9 Qualification Results

## Disposition

**G4.9 fails strict qualification and must not advance to external human review.**

The frozen staging batch completed all eight dialogues and all 48 independent
evaluation dimensions with zero dialogue failures and zero degraded LLM
fallbacks. The retired generated routing prompt and interview retrospective
authorship substitution are absent. The central multi-addressee gate still
fails in the RoomMind launch run, however, and three RoomMind runs retain
applicable legacy probe failures. Manual reading also finds a premature
incident close and important contradictions in the launch and interview runs.

## Frozen protocol

- Batch: `9ca21260-0f2f-43c9-9a15-0796608753c3`
- Source revision: `e4f953cb46a219472f2955ac4313023815c7657a`
- Architecture: `g4.9-response-routing-and-authorship-governance`
- Provider/model: `ollama/gpt-oss:120b`
- Design: four matched scenarios, Baseline and RoomMind, seed `20260909`
- Dialogue result: 8/8 frozen, zero dialogue failures, zero degraded fallbacks
- Evaluation result: `evaluation_completed`, 48/48 dimensions
- Evidence use: development-only exploration, not confirmatory evidence

The staging API was ready at final inspection, the deployed revision matched
the manifest, and every canonical transcript SHA-256 was independently
recomputed and matched the frozen run result.

## Independent AI evaluation

| Dimension | Baseline mean (n=4) | RoomMind mean (n=4) | Difference |
| --- | ---: | ---: | ---: |
| Role and strategy | 5.25 | 5.75 | +0.50 |
| Epistemic boundaries | 4.75 | 4.50 | -0.25 |
| Temporal coherence | 4.50 | 4.75 | +0.25 |
| Interaction structure | 5.00 | 4.75 | -0.25 |
| Multi-party dynamics | 4.75 | 5.00 | +0.25 |
| Procedural fidelity | 4.00 | 5.25 | +1.25 |

The unweighted descriptive mean of the six dimension means is 4.708 for
Baseline and 5.000 for RoomMind, a difference of +0.292. This is exploratory
only. It hides a severe scenario interaction: the evaluator strongly favors
RoomMind in negotiation, launch, and interview, but scores the RoomMind
incident run far below its Baseline pair.

## Run outcomes

| Run | Condition | Messages | Outcome / stop | Notable telemetry |
| ---: | --- | ---: | --- | --- |
| 499 | Baseline | 57 | stopped after extended close | 2 safe fallbacks |
| 500 | RoomMind | 30 | completed / conditions met | 7 retries, 4 silent recoveries; 2 legacy probes fail |
| 501 | Baseline | 77 | stopped after extended loop | 3 safe fallbacks; unsupported action/artifact diagnostics |
| 502 | RoomMind | 44 | completed / conditions met | 16 retries, 1 safe and 8 silent recoveries; 3 probes fail |
| 503 | Baseline | 78 | stopped at safety limit | 7 retries, 4 safe fallbacks; extensive repetition |
| 504 | RoomMind | 47 | completed / conditions met | 2 retries, 2 safe and 4 silent recoveries; 2 legacy probes fail |
| 505 | Baseline | 25 | stopped after bounded close | 1 retry, 2 safe fallbacks |
| 506 | RoomMind | 12 | conditional / bounded close | 3 retries, 3 silent recoveries; premature completion |

## Manual reading of all matched pairs

### Supply-chain negotiation

RoomMind reaches the coherent 83 RMB, 30-day, 7 million RMB package in 30
messages and is substantially less repetitive than the 57-message Baseline,
which confirms one price and later reopens it. RoomMind still inserts a player
handoff instead of yielding directly to an NPC-directed question and repeats
requests for written confirmation after the draft already contains the price.
**RoomMind wins the pair, but the conversation is not clean enough to qualify.**

### Product launch

RoomMind is shorter than the 77-message Baseline, but the key correction does
not hold. After the player asks Sales, Finance, and Operations to confirm, Sales
and Operations answer before the next player message while Finance does not.
Finance later says approval is unavailable pending a breakdown, contingency
justification, risk register, and committee sign-off, then reverses to approval
after Operations merely claims to have shared an unregistered artifact. The
dialogue also invents exact September dates and repeatedly promises documents.
Baseline is longer and contains its own unsupported uploads and role leakage.
**Neither output qualifies; RoomMind is more bounded but the pair is mixed.**

### Structured interview

G4.9 succeeds at the narrow authorship boundary: no panelist narrates the
candidate's historical work in the first person, and the old administrative
routing prompt is absent. RoomMind is still internally inconsistent: it calls
p95 latency of 260 ms compliant with a less-than-250 ms target, then later says
the same value triggered rollback. After declaring the candidate-question
phase complete, it reopens that phase several times and ends on yet another
formal-completion request. Baseline is a much worse 78-message near-identical
question loop. **RoomMind wins the pair, but still fails natural closure and
temporal consistency.**

### Incident response

RoomMind starts with plausible role separation but jumps from containment and
evidence capture to recovery-plan approval before containment is confirmed.
It contains a malformed numbered list, misroutes a floor handoff, leaves four
open issues, and closes conditionally after only 12 messages. Baseline is more
procedurally coherent, though it unrealistically reports live rollback,
artifact archival, canary deployment, and status-page actions without tool
evidence. **Baseline is the more natural pair member; neither is safe enough
for confirmatory use.**

Overall manual judgment is two RoomMind wins, one mixed pair, and one Baseline
win. This is an improvement over G4.8's aggregate AI result, but it does not
establish a stable realism advantage.

## Gate disposition

| Gate | Result | Evidence |
| --- | --- | --- |
| Eight frozen dialogues; zero failures/degraded fallbacks | PASS | 8/8, 0 dialogue failures, 0 degraded |
| Exact immutable transcript provenance | PASS | All eight hashes independently recomputed and matched |
| Complete independent six-dimension evaluation | PASS | 48/48 after missing-dimension-only retries; existing scores and hashes retained |
| Fixed revision, provider/model, seed, and manifest | PASS | Revision `e4f953cb...`, `ollama/gpt-oss:120b`, seed `20260909` |
| Every applicable legacy and G4.9 probe passes | FAIL | Runs 500, 502, and 504 have registered failures |
| Every directly addressed NPC responds before next player turn | FAIL | Run 502 sequence 8 is missing Finance before the next player message |
| Retired generated routing prompt absent | PASS | No G4.9 routing-prompt diagnostics in any run |
| No panel retrospective authorship substitution | PASS | No G4.9 authorship diagnostics; manual text confirms the boundary |
| No material repetition or floor-routing defect | FAIL | Run 502 duplicate-player and cross-role ownership probes; runs 500/504 cross-role ownership probes |
| Natural completion and no material regression | FAIL | Run 506 is marked premature with four open issues; runs 502/504 contain contradictions and reopened closure |

## Narrow next-step recommendation

Do not add another broad governance layer. The next candidate should correct
three concrete defects and re-run the same four matched scenarios:

1. keep a multi-addressee response set attached to the originating player turn
   across deterministic floor-handoff messages, and accept only a semantically
   responsive answer from each required role;
2. prevent conditional or unavailable approval from being projected as final,
   especially when the only new input is an unsupported artifact claim;
3. make phase-completion and incident prerequisites monotonic: a completed
   interview phase must not reopen without new user intent, and incident
   recovery approval must not precede confirmed containment/evidence state.

G4.9 validates the routing-prompt removal and interview authorship guard, but
the unresolved response-set, confirmation semantics, and closure ordering are
the current limiting mechanisms.
