# G4.7 Qualification Results

## Disposition

**G4.7 fails strict qualification and must not advance to external human review.**

The frozen staging batch completed all eight dialogues with zero dialogue
failures and zero degraded LLM fallbacks. Transcript hashes and all registered
deterministic probes verified. However, the independent evaluator finished only
47 of 48 dimensions, RoomMind did not show a descriptive scoring advantage, and
manual review found material repetition, premature closure, role-routing, and
unsupported-artifact defects that the current probes did not detect.

## Frozen protocol

- Batch: `b9e79535-4ab5-4db7-89d9-684ab5ba211c`
- Source revision: `597dbe4b4efca804f93bc9099fc2ac95e7a7381d`
- Architecture: `g4.7-floor-and-authority-routing-governance`
- Provider/model: `ollama/gpt-oss:120b`
- Design: four matched scenarios, Baseline and RoomMind, seed `20260907`
- Dialogue result: 8/8 frozen, zero dialogue failures, zero degraded fallbacks
- Evaluation result: `evaluation_partial`, 47/48 dimensions

The sole missing result is RoomMind run 486, `procedural_fidelity`. The initial
evaluation and two targeted retries returned JSON with empty
`evidence_sequence_nos` arrays. The evaluator rejects such arrays although its
prompt example permits them. The other five scores for that run retained hash
`a5aa5247c555043a7fff948bc12cea8b14615ff4292116babeeb114b4109449e`
through both retries, and its transcript hash remained unchanged. This is an
evaluation-pipeline defect, not a dialogue-generation failure.

## Independent AI evaluation

| Dimension | Baseline mean (n=4) | RoomMind mean | Difference |
| --- | ---: | ---: | ---: |
| Role and strategy | 6.00 | 5.25 (n=4) | -0.75 |
| Epistemic boundaries | 5.25 | 5.25 (n=4) | 0.00 |
| Temporal coherence | 5.50 | 5.00 (n=4) | -0.50 |
| Interaction structure | 6.00 | 5.75 (n=4) | -0.25 |
| Multi-party dynamics | 5.25 | 4.75 (n=4) | -0.50 |
| Procedural fidelity | 5.50 | 4.33 (n=3) | -1.17 |

The unweighted descriptive mean of the six dimension means is 5.583 for
Baseline and 5.056 for RoomMind, a difference of -0.528. This is exploratory
only: there are four pairs, and RoomMind procedural fidelity is incomplete.
The evaluator also scored clearly repetitive and fabricated Baseline dialogue
too generously, so the values cannot replace transcript-level judgment.

## Run outcomes

| Run | Condition | Messages | Outcome / stop | Notable telemetry |
| ---: | --- | ---: | --- | --- |
| 481 | Baseline | 31 | completed | 2 retries, 1 safe fallback |
| 482 | RoomMind | 38 | conditional / no task progress | 9 retries, 3 silent recoveries, 4 public rejections |
| 483 | Baseline | 63 | completed | 2 retries |
| 484 | RoomMind | 14 | conditional / player bounded close | 3 retries, 2 safe and 3 silent recoveries |
| 485 | Baseline | 72 | safety stop | 12 retries |
| 486 | RoomMind | 12 | deferred / no task progress | no LLM retry; 5 open issues |
| 487 | Baseline | 74 | stopped | 3 retries, 8 clause repairs |
| 488 | RoomMind | 39 | conditional / player bounded close | 5 retries, 3 safe and 7 silent recoveries |

## Manual reading of all matched pairs

### Supply-chain negotiation

Baseline is more coherent and reaches a usable conclusion in 31 messages,
with only modest redundancy. RoomMind begins efficiently but enters a repeated
multi-role chase for supplier capacity evidence. A malformed utterance (`Mr.`)
appears, followed by unsupported claims that attached files contain utilization,
yield, and capability metrics. The player then falsely confirms receipt. The
dialogue ends with another unanswered capacity question. **Baseline wins this
pair on realism and completion.**

### Product launch

Baseline reaches a reasonable decision early, then continues for 63 messages,
repeating checklists and inventing approvals, uploads, shared-drive artifacts,
and current actions. RoomMind is much shorter and exposes two genuine specialist
gaps, but private-constraint handling produces silence and recovery behavior.
After the player asks to close, an NPC speaks again and repeats an already
supplied request, leaving three issues open. **The pair is mixed; neither output
qualifies.**

### Interview

Baseline is pathological: 72 messages of repeated questions, fabricated internal
artifacts, and a contradictory checkout timeline. RoomMind gives a concise,
progressive, and internally consistent interview, but stops immediately after a
fresh leadership question, with no answer or closing and five open issues.
**RoomMind is substantially more natural, but incomplete.**

### Incident response

Baseline is highly repetitive and invents live firewall, rollback, timestamp,
status-page, hash, and upload actions; its final turns contradict one another on
containment. RoomMind is more natural and truthful overall, but repeatedly asks
for containment status, routes a confirmation to the wrong role once, and lets
an NPC object after the player closes. **RoomMind is better, but still has a
material floor/closure defect.**

Overall, RoomMind is the manual winner in two pairs, Baseline in one, and one is
mixed. This is not a robust overall advantage, and the serious RoomMind defects
are disqualifying even where Baseline is worse.

## Gate disposition

| Gate | Result | Evidence |
| --- | --- | --- |
| Eight frozen dialogues; zero dialogue failures/degraded fallbacks | PASS | 8/8 complete, 0 failures, 0 degraded |
| Hashes and registered integrity probes | PASS | All eight hashes recomputed; all applicable probes passed |
| Player does not substitute for addressed NPC | FAIL (manual) | Repeated interposition/chase remains despite probe pass |
| Task-critical focus targets authorized owners | PASS, limited exercise | Registered probe passes; no focus rejection event exercised |
| Repeated handoff is bounded | FAIL | Negotiation and incident contain synonymous cross-speaker loops |
| No malformed repair utterance | FAIL | Negotiation contains truncated `Mr.` utterance |
| Outcome and closure reconciliation | FAIL (manual) | NPC question/objection appears after player-directed closure |
| Complete independent six-dimension evaluation | FAIL | 47/48; prompt/parser contradiction blocks one dimension |
| No material realism regression in manual review | FAIL | Unsupported artifacts, premature stop, repetition, role reversal |

The deterministic probes are necessary but insufficient. The registered G4.7
checks pass because they observe specific metadata events; they miss semantic
paraphrase loops, malformed natural-language output, post-closure objections,
and unsupported claims expressed as “attached files”.

## Narrow G4.8 recommendation

1. Treat an unresolved directed question and new semantic evidence as progress;
   never trigger `no_task_progress` while a responsible reply is pending.
2. Reconcile the pending NPC response before honoring player closure, then lock
   the floor against further objections or new questions.
3. Budget repetition by normalized issue/obligation across all speakers, rather
   than only explicit handoff metadata or same-speaker duplication.
4. Expand artifact grounding to attached/uploaded/emailed/received claims and
   concrete reported metrics; require a registered simulated tool result.
5. Tighten private-constraint contradiction matching and produce a truthful
   conditional answer instead of silent recovery.
6. Align evaluator prompt and parser on evidence requirements. For a genuine
   non-occurrence metric, cite a defined transcript scope or support an explicit
   whole-transcript evidence scope.
7. Add probes for truncated utterances, cross-speaker semantic repetition,
   post-closure speech, and unsupported artifact receipt acknowledgements.

G4.7 remains useful exploratory evidence: it improves two difficult scenarios
and keeps the pipeline stable, but it does not yet deliver a reliable realism
advantage over the safety-only Baseline.
