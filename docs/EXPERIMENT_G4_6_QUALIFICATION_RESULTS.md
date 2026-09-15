# G4.6 Clause-Grounded Recovery Governance Qualification Results

## Disposition

**G4.6 does not pass the strict simulation-realism qualification.** Batch
`d0ed05f5-ec64-49dc-8452-e2154d60c2fe` completed all eight matched dialogues
under the frozen `ollama/gpt-oss:120b` binding with zero dialogue failures and
zero degraded LLM fallbacks. All 48 independent AI dimension ratings completed
after retrying only missing dimensions. All eight public-transcript SHA-256
values were independently recomputed and matched the frozen export.

The narrow G4.6 mechanisms worked: a mixed confirmation-plus-question produced
a clause-local material confirmation, unsupported current-world evidence was
rejected in the incident stress case, and the incident ended truthfully as
deferred with four open obligations. However, three of four RoomMind runs fail
at least one applicable integrity probe, the AI descriptive mean is 0.042 below
Baseline, and full manual reading finds recurring floor-ownership, authority
routing, repetition, and late-consistency defects. G4.6 therefore remains
development evidence and is not promoted to external human review.

## Frozen protocol

- Generation: `G4.6`
- Architecture: `g4.6-clause-grounded-recovery-governance`
- Source revision: `806685cec452df63fd26186b21761dd031ef5b6e`
- Random seed: `20260906`
- Dialogue and evaluator model: `ollama/gpt-oss:120b`
- Dialogue concurrency: one
- Conditions: traditional independent-memory agents and RoomMind
- Dialogues: 8/8 frozen; dialogue failures: zero
- Independent evaluation: 48/48 dimensions complete
- Degraded LLM fallbacks: zero
- Transcript provenance: 8/8 SHA-256 recomputations match
- External human review: not started

## Independent AI evaluation

The six dimensions remain separate endpoints. The mean is descriptive only.

| Dimension | Baseline mean | RoomMind mean | Difference |
|---|---:|---:|---:|
| Role and strategic fidelity | 6.00 | 5.75 | -0.25 |
| Information-boundary fidelity | 5.75 | 6.25 | +0.50 |
| Temporal coherence | 5.25 | 5.50 | +0.25 |
| Interaction structure | 6.00 | 5.75 | -0.25 |
| Multi-party dynamics | 5.75 | 5.00 | -0.75 |
| Procedural fidelity | 5.50 | 5.75 | +0.25 |
| Descriptive mean | 5.708 | 5.667 | -0.042 |

RoomMind improves the dimensions directly targeted by evidence and state
governance, but loses most strongly on multi-party dynamics. This pattern is
consistent with manual reading: the guards prevent false completion, while
speaker routing and recovery language remain visibly mechanical.

## Run outcomes and mechanism evidence

| Scenario | Baseline messages | RoomMind messages | RoomMind outcome | Integrity disposition |
|---|---:|---:|---|---|
| Supply-chain negotiation | 56 | 27 | completed in 10 turns | Fail: NPC-directed floor twice taken by player |
| Product launch | 75 | 35 | completed in 14 turns | Fail: NPC-directed floor taken by player |
| Leadership interview | 64 | 35 | completed in 14 turns | Pass |
| Incident command | 78 | 35 | deferred in 13 turns with four open obligations | Fail: repeated same-speaker prompt |

The mixed confirmation-plus-question path activated in the product-launch run:
one clause-local confirmation was committed while the question clause remained
routable. In incident command, governance rejected ten public claims, including
seven unsupported current-world claims, repaired six clauses, and suppressed
one duplicate obligation. The obligation graph and recorded open set reconcile,
so the deferred outcome is internally honest rather than false completion.

Transport instability did not corrupt the experimental artifacts. The four
RoomMind runs recorded 22 LLM retries in total, five dialogue-safe fallbacks and
ten silent recoveries, but no degraded model output. The high repair load in
incident command coincides with its repeated prompts and weak conversational
naturalness.

## Manual reading of all four matched pairs

### Supply-chain negotiation

Baseline is long and repeatedly reopens the production schedule and cost
breakdown after the commercial terms are already settled. It also claims an
attached schedule, a DocuSign package, email delivery, a corporate seal and
insurance without tool evidence. RoomMind is substantially shorter and more
bounded, but mishandles the floor: after an NPC asks another NPC for capacity
evidence, the player repeats or pre-empts the request, and the final quality
speaker offers to circulate a contract outside the natural role boundary.
RoomMind is directionally better on boundedness and evidence discipline, but
the meeting choreography is not yet reliable.

### Product-launch decision

Baseline initially approves the budget and later revokes it pending a new
review, then continues through fabricated uploads, calendars, hires and current
metrics. RoomMind is clearer and shorter, but one safe fallback emits visibly
templated language, the CFO confirms funding without receiving the promised
detailed model, and Operations later says two specialists are missing after
earlier claiming all support personnel were trained. An NPC-to-NPC question is
also intercepted by the player. RoomMind improves boundedness, but temporal and
floor consistency remain material defects.

### Leadership interview

Baseline contains richer candidate examples but repeats similar morale and
product-evidence questions, with panel authority overlap. RoomMind is shorter
and avoids the long pile-on, yet its opening candidate response is vague,
several later figures read as invented artifact summaries, and panelists still
overlap in what evidence they certify. This pair is mixed: RoomMind has better
meeting length and progression, while Baseline sometimes sounds more naturally
detailed at the utterance level.

### Incident command

Baseline repeatedly fabricates storage snapshots, traffic shifts, live metrics,
hashes, status-page publication and elapsed time, and eventually describes a
rollback target inconsistently. RoomMind is materially more truthful: it blocks
premature completion, keeps forensic work open and stops as deferred. It still
repeats variants of “Priya Shah, answer directly”, routes forensic ownership to
the SRE even though Security owns the evidence, and loops while asking for a
capability the current role cannot honestly confirm. RoomMind is better on
epistemic safety and closure, but the dialogue remains visibly unnatural.

## Integrity and qualification gates

| Gate | Result | Evidence |
|---|---|---|
| Frozen source, model, seed and transcripts | Pass | manifest verified; 8/8 hashes recomputed |
| Engineering completion | Pass | 8/8 dialogues, 48/48 dimensions, zero dialogue failures |
| No degraded LLM output | Pass | zero degraded fallback; retries recovered |
| Clause-local mixed confirmation | Pass | one accepted material clause in the launch run |
| Evidence and owner boundary | Pass | incident rejects unsupported current-world claims; no unregistered public owner leak |
| Obligation/open-set reconciliation | Pass | incident deferred with the same four obligations recorded open |
| All applicable integrity probes | **Fail** | only one of four RoomMind runs passes every applicable probe |
| NPC-to-NPC floor ownership | **Fail** | negotiation and launch contain player interposition |
| Repair/fallback repetition control | **Fail** | incident repeats player-directed prompts and fails the near-duplicate probe |
| Consistent AI realism advantage | **Fail** | descriptive mean difference is -0.042; multi-party difference is -0.75 |
| Manual overall realism | **Fail** | recurring routing, authority, repetition and late-consistency defects |

## Successor requirement

The next candidate should be a narrow G4.7 correction, not another broad prompt
rewrite:

1. make floor ownership deterministic: an NPC-to-NPC question reserves the next
   response for the addressed NPC, while the player yields unless explicitly
   addressed;
2. split compound requests by authoritative owner, routing evidence status to
   Security and containment state to SRE rather than letting one role substitute
   for another;
3. normalize repeated “answer directly” recovery prompts and, after one failed
   attempt, switch to a truthful bounded defer instead of paraphrasing the same
   demand;
4. replace templated repair splices such as “For Could you…” with a clean,
   context-aware fallback utterance;
5. validate late public claims against the ledger so “all staff trained” cannot
   later coexist with “two specialists are still missing” without an explicit
   update or correction.

These changes should remain domain-neutral. G4.6 shows that clause grounding
and evidence-state governance improve truthfulness, but it does not show that
RoomMind is more realistic overall than the independent-memory baseline.
