# G3.5 Qualification Results

## Disposition

**G3.5 fails the realism qualification gate.** The generation is technically
reproducible and the stricter evaluator now produces structurally complete
evidence, but RoomMind scores below the matched traditional independent-agent
Baseline on every realism dimension. All four RoomMind dialogues ended
`stalled`; no external human review was started.

This is an exploratory development batch (`n = 4` matched pairs), not
confirmatory evidence.

## Frozen experiment identity

- Batch: `5bc77e6d-822e-42d1-9ad2-dbd97a0a33ba`
- Source revision: `78c9fd14d0c9a520fbc1715afd17228059561844`
- Generation: `G3.5`
- Architecture: `g3.5-atomic-confirmation-source-typed-evidence-simulation`
- Research manifest SHA-256:
  `4c95d6414240aaf027dc928d1c4f42b5db6b71eebbe9a94f4f65ff5b5b648040`
- Dialogue and evaluator provider/model: `ollama/gpt-oss:120b`
- Design: four scenarios, matched RoomMind/Baseline conditions, one
  repetition, fixed seed `202609035`, concurrency 1, maximum 20 turns
- Final batch status: `evaluation_completed`

All eight dialogues completed and were frozen before evaluation. Transcript
hashes were recomputed from canonical messages; all eight matched their stored
hashes. There were no dialogue failures or degraded-LLM fallbacks.

The first evaluation pass completed 46 of 48 dimensions. Strict structural
validation correctly rejected two malformed responses. Selective retry filled
only missing dimensions (47/48, then 48/48) without overwriting completed
dimensions. A final independent audit confirmed that every required child
metric now has a valid score, non-empty reason, and references to sequence
numbers present in the frozen transcript.

## Transcript integrity

| Run | Scenario | Condition | Transcript SHA-256 |
|---:|---:|---|---|
| 372 | 1 | Baseline | `69eebd6343d5fddada8f60ca15ad66392f127916413d3dfc0319c2472c0a947e` |
| 371 | 1 | RoomMind | `10e764d6f38fecf4e7cbf9a253634d67d471003b3c7810d25abcbd41fe670aae` |
| 374 | 2 | Baseline | `39adfa6aad46a9a0c4d310797d422cb3cfb91dcfb3d91ee0366b9274ff85da0d` |
| 373 | 2 | RoomMind | `4723038b1c3f311fe61b490fc4c3fe1c04ad431b280222b7a7262adce1b71e3d` |
| 376 | 3 | Baseline | `09e3536ab7d9e9b944ae4519b04af023e23f58d3255561382834af4673d574b5` |
| 375 | 3 | RoomMind | `195a66dfd467df507aa05fdd22d77b0815f3e477ab8a5f0481b0ab467f54e35e` |
| 378 | 4 | Baseline | `d01578e1db94ee898cd9b84d501fbebb9c87bfd051e0c4ed4aa4f2e79274562c` |
| 377 | 4 | RoomMind | `27c3a56cb05d32595bce4f95559257a157e248172b155227f98069ce7e2f292b` |

## Independent six-dimension evaluation

Scores remain separate; no composite index was calculated.

| Dimension | RoomMind mean | Baseline mean | Paired difference |
|---|---:|---:|---:|
| Role and strategic fidelity | 3.50 | 6.50 | -3.00 |
| Epistemic / information-boundary fidelity | 4.00 | 6.25 | -2.25 |
| Temporal coherence | 4.00 | 5.00 | -1.00 |
| Interaction-structure fidelity | 3.50 | 5.75 | -2.25 |
| Multi-party dynamics fidelity | 4.75 | 5.25 | -0.50 |
| Procedural fidelity | 4.50 | 6.00 | -1.50 |

RoomMind-minus-Baseline differences for scenarios 1 through 4 were:

- role and strategy: `-3, -2, -5, -2`;
- epistemic fidelity: `-3, -2, -2, -2`;
- temporal coherence: `-1, -3, +2, -2`;
- interaction structure: `-2, -3, -2, -2`;
- multi-party dynamics: `-1, -1, 0, 0`;
- procedural fidelity: `-1, -3, -1, -2`.

With only four matched pairs these results are descriptive. They do not
establish a general Baseline advantage, but they decisively fail the intended
development gate for promoting G3.5.

## Engineering behavior

| Scenario | Condition | Turns | Messages | Safe fallbacks | Grounding rejections | Ending |
|---:|---|---:|---:|---:|---:|---|
| 1 | Baseline | 8 | 30 | 3 | 0 | completed |
| 1 | RoomMind | 20 | 56 | 11 | 4 | stalled / safety limit |
| 2 | Baseline | 20 | 72 | 7 | 0 | completed / safety limit |
| 2 | RoomMind | 8 | 23 | 8 | 0 | stalled / no task progress |
| 3 | Baseline | 19 | 65 | 6 | 0 | completed |
| 3 | RoomMind | 9 | 26 | 0 | 0 | stalled / no task progress |
| 4 | Baseline | 16 | 61 | 5 | 0 | completed |
| 4 | RoomMind | 20 | 57 | 15 | 4 | stalled / safety limit |

All exported deterministic integrity probes passed, including independent
memory partitions, ledger provenance, monotonic lifecycle, completion
reconciliation, and the requirement that a terminal current-world action cite
a registered simulated tool result. These are useful implementation guarantees,
but they did not predict natural dialogue or successful task progression.

The G3.5 direct-public-draft path recorded **zero** validated-draft uses in all
eight runs. The model's drafts therefore continued through rejection,
regeneration, or fallback paths; the intended naturalness improvement never
activated in this real-model batch.

## Full-dialogue manual inspection

Every RoomMind and Baseline transcript was read turn by turn.

### Scenario 1: supply-chain negotiation

Baseline reached a conditional agreement in eight turns and was mostly
natural, although its capacity figures contained a minor inconsistency.
RoomMind repeatedly reopened capacity evidence and confirmations, exposed
recognizable recovery templates, and continued after the participants appeared
to agree. It also referred to a draft contract and attached/finalized protocol
without an in-session artifact. The ledger kept price, delivery, and quality
in proposed states; the numeric price was stored as the string `84 RMB` and
authorized public confirmations did not close the fields.

### Scenario 2: launch go/no-go meeting

Baseline was verbose but gathered commercial, operational, and financial
evidence and reached a phased-launch decision. RoomMind's CFO repeatedly
returned the generic `On statement...` recovery sentence and never supplied
the budget analysis. A malformed player line and repeated generic recovery
language made the meeting visibly machine-governed. The run stopped after
eight turns with budget and launch decision unresolved.

### Scenario 3: leadership interview

RoomMind's candidate gave substantive examples, but the panel asked duplicate
questions and then pursued a post-meeting matrix attachment instead of
projecting the spoken evidence into the task variables. Product evidence alone
was recognized; engineering and leadership evidence remained unknown. Baseline
also repeated itself and restarted questioning after apparent completion, but
its overall role separation and procedure were judged stronger.

### Scenario 4: incident command

Baseline advanced through containment and recovery but fabricated operational
actions, hashes, canary metrics, and publication. It also contradicted the
rollback plan by later deploying version 4.18 instead of restoring 4.17.
RoomMind initially preserved the dependency between evidence capture and
containment, but then oscillated between `in progress`, `active`, and `not yet
finalized`; it repeatedly emitted generic recovery templates. It later claimed
completed dumps and verified hashes without a registered tool result and asked
for a hash the simulation could not produce. The ledger refused to accept the
unsupported completion, but the public transcript still displayed it. Thus
G3.5 protected canonical state without making the visible conversation true.

## Root-cause interpretation

1. **Validation depends on intent classification.** Source-typed provenance is
   applied after the model classifies an utterance. If an unsupported action is
   mislabeled as ordinary information, its false completion remains visible
   even though the ledger does not advance.
2. **Atomic confirmation is not end-to-end.** Value normalization, authority,
   confirmation parsing, and aggregate state projection still diverge. Public
   acceptance can coexist with `proposed` task state.
3. **Valid-draft publication did not activate.** The zero-use count shows that
   G3.5 did not remove the dominant renderer/rejection path in actual runs.
4. **Fallbacks remain public dialogue.** Generic safety text is safe but not a
   believable utterance by a CEO, CFO, interviewer, or incident specialist.
5. **The simulation lacks a general evidence-producing environment.** It asks
   agents for files, hashes, health checks, and executed actions that the text
   world cannot actually perform. This creates either hallucinated completion
   or indefinite waiting.
6. **Deterministic invariants and realism must stay separate.** Every integrity
   probe passed while manual and AI realism evaluations failed. Passing ledger
   shape checks cannot substitute for dialogue-level validity.

## Qualification gates

| Gate | Result | Evidence |
|---|---|---|
| Procedural fidelity exceeds matched Baseline | Fail | 4.50 vs 6.00 |
| Temporal and epistemic fidelity do not regress | Fail | 4.00 vs 5.00; 4.00 vs 6.25 |
| No unsupported completed external actions in visible speech | Fail | Manual audit found attachments, hashes, captures, and containment claims without tool evidence |
| Interaction structure improves | Fail | 3.50 vs 5.75 |
| Endings reconcile public commitments and task state | Fail | 4/4 RoomMind runs stalled |
| Technical reproducibility and artifact integrity | Pass | 8/8 dialogues, 48/48 valid dimensions, matching hashes, fixed model |
| Evaluator structural validity | Pass | Strict validation rejected malformed responses and all final child evidence passed audit |

## Next-generation direction

Any new implementation must be labeled **G3.6** and must preserve this batch.

1. Make dialogue-act parsing deterministic and clause-level for configured
   confirmations and action claims; do not let an LLM intent label bypass
   provenance checks.
2. Normalize typed values before ledger comparison (`84 RMB` to numeric `84`,
   booleans and enums likewise) and expose projection diagnostics per clause.
3. Never publish a terminal current-world action unless the matching simulated
   tool result already exists. Convert unsupported clauses to future
   commitments before they reach the transcript, not only before state update.
4. Replace reusable public fallback templates with a silent bounded repair of
   the violating clause; if repair fails, omit the turn or use a role-specific
   conditional statement generated from verified public facts.
5. Add explicit scenario capabilities. If no simulated tool can produce an
   artifact or measurement, the coordinator must not make it an in-session
   completion requirement and must close with a named external follow-up.
6. Add qualification probes for visible unsupported claims and require nonzero
   direct-draft use before claiming the direct-draft architecture was exercised.
