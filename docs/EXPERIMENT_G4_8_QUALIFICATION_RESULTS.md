# G4.8 Qualification Results

## Disposition

**G4.8 fails strict qualification and must not advance to external human review.**

The batch completed all eight dialogues and all 48 independent evaluation
dimensions with zero dialogue failures and zero degraded LLM fallbacks. G4.8
successfully prevented post-closure NPC speech and unsupported live artifact
claims in the RoomMind runs. It nevertheless fails because two RoomMind runs
have registered integrity-probe failures, the product-launch run closes before
the finance confirmation, and the interview and incident runs remain materially
repetitive and unnatural.

## Frozen protocol

- Batch: `930fca41-758e-4b1e-ac3f-a235d8f1524b`
- Source revision: `fa4e673580d0e7d041cb57a0e19e6c682ae73a33`
- Architecture: `g4.8-convergence-closure-and-evidence-governance`
- Provider/model: `ollama/gpt-oss:120b`
- Design: four matched scenarios, Baseline and RoomMind, seed `20260908`
- Dialogue result: 8/8 frozen, zero dialogue failures, zero degraded fallbacks
- Evaluation result: `evaluation_completed`, 48/48 dimensions
- Evidence use: development-only exploration, not confirmatory evidence

All eight transcript hashes were independently recomputed from the canonical
public rows and matched the run result and debug-bundle provenance.

## Independent AI evaluation

| Dimension | Baseline mean (n=4) | RoomMind mean (n=4) | Difference |
| --- | ---: | ---: | ---: |
| Role and strategy | 5.75 | 3.75 | -2.00 |
| Epistemic boundaries | 6.25 | 5.75 | -0.50 |
| Temporal coherence | 5.75 | 4.50 | -1.25 |
| Interaction structure | 5.75 | 4.75 | -1.00 |
| Multi-party dynamics | 5.75 | 3.75 | -2.00 |
| Procedural fidelity | 5.50 | 4.50 | -1.00 |

The unweighted descriptive mean of the six dimension means is 5.792 for
Baseline and 4.500 for RoomMind, a difference of -1.292. This is exploratory
only. The evaluator over-rewards long Baseline transcripts that visibly loop
and claim unsupported current-world actions, so the scores must be interpreted
alongside the frozen text and deterministic diagnostics.

## Run outcomes

| Run | Condition | Messages | Outcome / stop | Notable telemetry |
| ---: | --- | ---: | --- | --- |
| 491 | Baseline | 78 | completed / model declaration | 1 retry, 1 safe fallback |
| 492 | RoomMind | 11 | completed / conditions met | 1 retry; all probes pass |
| 493 | Baseline | 79 | stopped / safety limit | 1 safe fallback |
| 494 | RoomMind | 14 | conditional / bounded close | 2 safe, 9 silent recoveries; repetition probe fails |
| 495 | Baseline | 73 | stopped / safety limit | 3 retries, 1 safe fallback |
| 496 | RoomMind | 50 | completed / conditions met | 4 retries, 2 safe fallbacks; two probes fail |
| 497 | Baseline | 54 | stopped / bounded close | 1 retry, 3 safe fallbacks, 3 grounding rejections |
| 498 | RoomMind | 31 | conditional / bounded close | 9 retries, 3 safe, 6 silent recoveries, 9 grounding rejections |

## Manual reading of all matched pairs

### Supply-chain negotiation

RoomMind reaches a coherent agreement in 11 messages. Roles contribute distinct
price, delivery, quality, and benchmark evidence; the draft contract is promised
rather than falsely reported as delivered. Baseline continues for 78 messages,
reopens settled terms, contradicts the liability cap, and repeatedly claims that
contracts, annexes, schedules, and sign-offs were emailed or received without a
registered tool result. **RoomMind clearly wins this pair.**

### Product launch

Baseline contains substantive readiness discussion but then loops through
charter, brief, mitigation-plan, and sign-off requests for 79 messages while
inventing attachments and reviews. RoomMind is concise and correctly routes the
first market-readiness questions, but repeatedly inserts the player prompt
“please answer directly,” lets Sales speak when Operations and Finance were
addressed, and closes after Operations answers without obtaining the CFO budget
confirmation or a valid launch decision. **Neither output qualifies; the pair is
mixed.**

### Interview

Baseline is a 73-message interrogation loop with near-identical questions from
all three interviewers and ends at the safety limit. RoomMind is shorter but
still spends 50 messages revisiting the same engineering evidence, repeats the
player routing line three times, lets interviewers answer questions about the
candidate's own historical technical implementation, and follows a candidate
question with unrelated autobiographical content before reopening closure.
**Neither output is natural enough; RoomMind is somewhat more bounded but the
pair remains mixed.**

### Incident response

Baseline fabricates containment, evidence capture, rollback, status-page
publication, and preserved artifacts, then loops for 54 messages waiting on
health checks. RoomMind correctly rejects unsupported bucket/hash and current-
world completion claims and ends with the responsible owner and unresolved
evidence blocker recorded. It still repeats the same snapshot request across
the player, Security, and SRE, and never receives evidence needed to mark
containment active. **RoomMind wins on truthfulness and safety, but remains too
repetitive to qualify.**

Overall, manual reading gives RoomMind two clear pair wins and two mixed pairs.
That does not offset the registered failures or establish a reliable realism
advantage across scenarios.

## Gate disposition

| Gate | Result | Evidence |
| --- | --- | --- |
| Eight frozen dialogues; zero failures/degraded fallbacks | PASS | 8/8, 0 dialogue failures, 0 degraded |
| Exact immutable transcript provenance | PASS | All eight canonical hashes recomputed and matched |
| Complete independent six-dimension evaluation | PASS | 48/48 dimensions after targeted missing-dimension retries |
| Every applicable integrity probe passes | FAIL | Run 494 same-speaker repetition; run 496 noncritical focus and same-speaker repetition |
| No post-player-closure speech | PASS | All RoomMind G4.8 probes pass; frozen transcripts confirm terminal floor lock |
| Live artifact and receipt claims are grounded | PASS for RoomMind | No RoomMind unsupported receipt/action diagnostics; Baseline still fabricates them |
| Fresh directed questions are not prematurely abandoned | FAIL | Run 494 closes before CFO budget confirmation after Operations answers |
| No material cross-role or same-role repetition | FAIL | Runs 494, 496, and 498 contain visible prompt/issue loops |
| Natural role ownership and turn-taking | FAIL | Interviewers answer candidate-history questions; Sales interposes in launch routing |
| No material realism regression in manual review | FAIL | Two of four RoomMind runs remain seriously incomplete or repetitive |

## Narrow next-step recommendation

G4.9 should not broaden the architecture. It should make one bounded correction
to response routing and one to termination:

1. represent every directed multi-addressee request as separate pending-response
   obligations and do not close while any authorized present addressee still
   owes a response;
2. suppress the generated player “please answer directly” line when the pending
   owner can be scheduled directly, and count repeated routing prompts as
   repetition;
3. forbid an interviewer NPC from supplying autobiographical facts or technical
   implementation details on behalf of the candidate;
4. extend issue-level repetition detection to short player/NPC paraphrases,
   including evidence-location and hash requests;
5. add frozen probes for premature multi-addressee closure, repeated routing
   prompts, and candidate/interviewer authorship reversal.

G4.8 establishes real progress on closure integrity, artifact grounding, and
evaluation completeness, but convergence and role-naturalness remain the
limiting mechanisms.
