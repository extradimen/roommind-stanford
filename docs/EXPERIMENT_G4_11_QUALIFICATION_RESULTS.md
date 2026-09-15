# G4.11 Qualification Results

## Disposition

**G4.11 fails strict qualification and must not advance to external human
review.**

The fixed generation batch completed 8/8 dialogues with zero dialogue failures
and zero degraded LLM output, all eight transcript hashes recomputed exactly,
and the final evaluation contains 48/48 evidence-backed dimensions. The narrow
NPC-to-NPC direct-response diagnostic is clean in all four RoomMind runs.

The candidate nevertheless fails its other defining boundary. Every RoomMind
run has a rejected transition that later appears as stronger public
confirmation language; run 528 also commits a conditional confirmation. The
RoomMind condition trails Baseline on all six AI dimensions, all four matched
pairs, and the unweighted overall mean. Manual reading finds repeated player
floor relays, wrong or missing targeted speakers, unsupported live-artifact
claims, and three of four RoomMind runs ending conditionally with unresolved
work.

## Frozen protocol and evaluator repair

- Batch: `fffde583-355b-4b3e-8e5f-e404c236addb`
- Generation source revision: `496bd1058432d7f5389ef3898fbac58e686c5b3b`
- Architecture: `g4.11-direct-routing-and-state-surface-convergence`
- Provider/model: `ollama/gpt-oss:120b` for dialogue and evaluation
- Design: four matched scenarios, Baseline and RoomMind, seed `20260911`
- Dialogue result: 8/8 frozen, zero failures, zero degraded fallbacks
- Evidence use: development-only exploration, not confirmatory evidence

The first evaluation passes reached 46/48 dimensions. Runs 527 and 528
repeatedly returned a total-only `role_strategic_fidelity` JSON object whose six
metric rows had null scores, blank reasons, and no evidence. Those outputs were
correctly rejected; repeated missing-only retries reproduced the same malformed
shape.

With user authorization, evaluator-only revision
`dc159780997b3b160641c02f22b09e521f9766e2` added feedback-directed repair
prompts and one bounded attempt. It did not change dialogue code, the frozen
manifest, transcripts, provider/model, seed, scenarios, or any completed
dimension. Server compilation and the LLM-resilience smoke test passed before
the API was restarted. Only runs 527 and 528 were requeued, only their missing
role-strategy dimension was evaluated, their transcript hashes and the other
ten completed dimension hashes remained byte-identical, and the batch reached
48/48 with no evaluation errors. This split generation/evaluator revision is
part of the audit record and prevents describing the batch as a single-revision
end-to-end run.

## Independent AI evaluation

| Dimension | Baseline mean (n=4) | RoomMind mean (n=4) | Difference |
| --- | ---: | ---: | ---: |
| Role and strategy | 5.75 | 5.25 | -0.50 |
| Epistemic boundaries | 5.25 | 3.50 | -1.75 |
| Temporal coherence | 5.75 | 4.00 | -1.75 |
| Interaction structure | 5.75 | 4.75 | -1.00 |
| Multi-party dynamics | 5.50 | 4.50 | -1.00 |
| Procedural fidelity | 5.75 | 3.25 | -2.50 |

The unweighted descriptive mean is 5.625 for Baseline and 4.208 for
RoomMind, a difference of -1.417. Matched scenario differences are -1.333,
-1.833, -0.500, and -2.000. The direction is adverse in every dimension and
every scenario.

## Run outcomes and telemetry

| Run | Condition | Public messages | Outcome / stop | Notable telemetry |
| ---: | --- | ---: | --- | --- |
| 523 | Baseline | 76 | externally complete; 20 turns | 1 retry; no fallbacks |
| 524 | RoomMind | 33 | conditional bounded close; 2 open issues | 8 retries, 2 safe and 6 silent recoveries |
| 525 | Baseline | 40 | externally complete | 1 safe fallback |
| 526 | RoomMind | 8 | conditional bounded close; 2 open issues | 1 retry, 2 silent recoveries |
| 527 | Baseline | 73 | not externally complete; 20 turns | 2 retries, 5 safe fallbacks; repetitive evidence loop |
| 528 | RoomMind | 32 | externally complete but internally conditional; 1 open issue | 3 retries, 1 safe and 5 silent recoveries |
| 529 | Baseline | 32 | externally complete | 2 retries, 3 safe fallbacks, 1 grounding rejection |
| 530 | RoomMind | 25 | conditional bounded close; 4 open issues | 9 retries, 1 safe and 11 silent recoveries |

Across the batch there were 26 LLM retries, 13 safe fallbacks, and 24 silent
recoveries. No degraded provider output was recorded. RoomMind accounts for 21
of 26 retries and all 24 silent recoveries, with the incident run alone using
11 silent recoveries. The only observed provider/model pair in generation and
evaluation telemetry is `ollama/gpt-oss:120b`; no recent API/transport failure
is present in the frozen bundle.

## Integrity probes

The new direct-response probe
`g411_npc_questions_receive_direct_same_turn_response` passes in every RoomMind
run: no registered NPC-to-NPC question lacks the addressed NPC's immediate
same-turn response.

Strict probe completeness fails:

- runs 524, 526, 528, and 530 fail
  `g411_rejected_transitions_not_reintroduced_in_speech`, with two, one, three,
  and one flagged public clauses respectively;
- run 528 also fails `g410_conditional_confirmations_not_committed` for the
  `product_evidence` event;
- all four Baseline runs pass their applicable implementation-integrity probes.

The failures are visible rather than merely bookkeeping artifacts. Examples
include Supplier CEO confirmation language after quote validation rejected the
subject/value, Sales declaring market readiness after value validation failed,
interview panelists publicly confirming evidence whose transition was rejected,
and Communications confirming a review transition unsupported by its public
quote.

## Manual reading of all matched pairs

### Supply-chain negotiation

Baseline is much too long and reopens price and delivery after an earlier
agreement, but it eventually secures authorized price, delivery, and quality
confirmations. RoomMind is shorter and initially obtains the correct direct
quality response, yet the player must explicitly relay the floor after another
NPC answers first, the audit outline remains open, and Supplier CEO confirmation
phrasing survives two rejected transitions. **Baseline wins the pair; neither
is strong enough for confirmatory use.**

### Product launch

Baseline is verbose and invents detailed commercial and staffing figures, but
it obtains market, operations, and CFO budget confirmation before a coherent
phased-launch decision. RoomMind asks the CFO directly, lets Sales and then
Operations answer instead, never gives the CFO a turn, and closes after only
eight public messages with budget and launch decision unresolved. **Baseline
wins decisively.**

### Structured interview

Baseline loops excessively on evidence artifacts and reaches the 20-turn limit,
but each panel role remains recognizable and the missing engineering evidence
is honestly left pending. RoomMind gets through the three evidence categories
faster, then mishandles the candidate-question floor: a request to Maya yields a
new administrative question, a request to Avery yields Noah, and the meeting
ends waiting for Avery. It also claims that design specs, roadmaps, and sprint
artifacts have just been placed in shared folders without simulated tool
evidence. **Baseline wins narrowly on process integrity despite poor
naturalness.**

### Incident response

Baseline makes unsupported live-action claims but maintains a coherent
evidence-first sequence, activates containment, obtains SRE and Security
approval, assigns communications, and progresses into bounded execution.
RoomMind repeatedly waits for evidence hashes, then publicly approves the plan
but never routes the requested confirmation back to SRE; an explicit player
floor relay still produces no response. It closes with containment, recovery
approval, and ownership obligations still open. **Baseline wins decisively.**

Overall manual judgment is four Baseline wins and zero RoomMind wins. G4.11's
narrow NPC-to-NPC direct edge works when triggered, but the broader
player-to-multiple-NPC response set, focus selection, transition-to-speech
boundary, and live-artifact grounding remain non-convergent.

## Gate disposition

| Gate | Result | Evidence |
| --- | --- | --- |
| Eight frozen dialogues; zero failures/degraded output | PASS | 8/8, 0 failures, 0 degraded |
| Exact immutable transcript provenance | PASS | all eight SHA-256 values independently recomputed |
| Complete six-dimension evaluation | PASS with disclosed repair | 48/48; only two missing dimensions rerun; prior hashes retained |
| Fixed generation revision, model, seed, and manifest | PASS | generation revision `496bd105...`, fixed model, seed `20260911` |
| Single revision throughout generation and evaluation | FAIL | evaluator-only revision `dc15978...` completed two missing dimensions |
| Direct same-turn response to registered NPC-to-NPC questions | PASS | zero G4.11 direct-response diagnostics |
| Rejected transitions never reappear as stronger speech | FAIL | all four RoomMind runs have violations |
| Conditional confirmations are not committed | FAIL | run 528 commits conditional `product_evidence` |
| Every applicable legacy through G4.11 probe passes | FAIL | all four RoomMind runs fail at least one applicable probe |
| No player-mediated routing or missing targeted speaker | FAIL | explicit relays and wrong/missing targets in runs 524, 526, 528, 530 |
| No unsupported current-world artifact claim | FAIL | run 528 claims live shared-folder/repository artifacts without tool evidence |
| No material repetition/naturalness regression | FAIL | high recovery concentration and repeated unresolved asks |
| Stable advantage over Baseline | FAIL | AI loses 6/6 dimensions and 4/4 matched pairs |

## Narrow next-step recommendation

Do not broaden confirmation vocabulary. A successor should:

1. generalize the pending-response set to player multi-addressee questions and
   explicit named-floor requests, with deterministic target delivery before any
   unrelated speaker;
2. make a rejected transition invalidate or regenerate the exact public clause,
   and add runtime tests using the seven frozen G4.11 violations;
3. prohibit claims that an artifact was uploaded, placed in a repository, or
   made available unless a simulated tool result is present;
4. couple bounded-close selection to unresolved prerequisite ownership so the
   system cannot repeatedly ask the wrong role and then close administratively;
5. run evaluator repair regressions before the next live batch so evaluation
   infrastructure does not require a post-freeze revision change.

G4.11 validates the narrow NPC-to-NPC direct-response mechanism, but fails the
state-to-speech boundary and overall realism comparison. **Do not start
external human review.**
