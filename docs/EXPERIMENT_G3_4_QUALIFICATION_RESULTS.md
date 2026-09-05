# G3.4 Qualification Results

## Disposition

**G3.4 fails the realism qualification gate.** It is engineering-stable enough
to preserve as development evidence, but it does not support a claim that
RoomMind is more realistic than the matched traditional-agent baseline.

This was an exploratory development batch (`n = 4` matched scenario pairs),
not confirmatory evidence. No external human review was started.

## Frozen experiment identity

- Batch: `b1d3699d-d697-449d-8cca-ebe776712a74`
- Source revision: `6a5f645a1d05010e14b37692a18d2acfc157d8f6`
- Generation: `G3.4`
- Architecture: `g3.4-natural-recovery-bounded-evidence-ledger-simulation`
- Research manifest SHA-256:
  `1857cc9e8277bf26b82e56f058adac669188e73844107966941ab8b367cce4a9`
- Dialogue and evaluator provider/model: `ollama/gpt-oss:120b`
- Design: four scenarios, matched RoomMind/Baseline conditions, one repetition,
  fixed seed `202609034`, concurrency 1, maximum 20 turns
- Final batch status: `evaluation_completed`

All eight dialogues completed and were frozen before independent evaluation.
All eight six-dimension evaluations completed; no dimension retry was needed.
There were no dialogue failures, evaluation failures, or degraded-LLM
fallbacks.

The post-evaluation structural audit found that “completed” is too permissive:
run 368 Baseline temporal coherence and run 369 RoomMind procedural fidelity
each retained a dimension score while all required child metrics had empty
reasons and default score `1`. The current validator treats the presence of a
dimension score as sufficient. These two dimensions are therefore
**structurally completed but internally malformed**. They were not silently
repaired or selectively overwritten after the frozen result. The mean table
below reports the persisted scores for reproducibility, but the numerical AI
comparison must be treated as provisional and interpreted together with the
manual transcript audit.

## Transcript integrity

The exported transcript hashes were independently recomputed from the canonical
public message rows before and after evaluation. All eight matched the stored
hashes.

| Run | Scenario | Condition | Transcript SHA-256 |
|---:|---:|---|---|
| 364 | 1 | Baseline | `3b153009d4a19f009744c8cb7bb0726d43de70da06657ab57d14155a0db78bf5` |
| 363 | 1 | RoomMind | `21c3f521e4862b6c99c19cdbfb54227bea98900312cde1d8d9606c15f2d1659c` |
| 366 | 2 | Baseline | `708e60cbe37ab8b5a40fcbf118277a42dd484de5e397f0944e4104ff954fcda0` |
| 365 | 2 | RoomMind | `88135ee0dcc5730cfa371a4d7dc549987581d9ab2432f7d788bd396115b0a9f5` |
| 368 | 3 | Baseline | `06d5c3b24ab5d568a8b81517b6ca0805764fedf75360bfc66b95e31e8c6c2521` |
| 367 | 3 | RoomMind | `41e852900a09886f4ac039b7e6fba0ada59d5f5104b7a9b711de2689433f0ac5` |
| 370 | 4 | Baseline | `d751935ac9999f3949b861828fe147d78c6fdeae3d16b732b3d110bb5cbcae49` |
| 369 | 4 | RoomMind | `541ce90fc1713672f7fed9feb1b78a019a8327b8403b5b2cf70526b9cfd00f70` |

Provider and model labels in both dialogue-generation and evaluation traces
were uniformly `ollama/gpt-oss:120b`.

## Independent six-dimension AI evaluation

Scores use the frozen six-dimension rubric and remain separate. No composite
index was calculated.

| Dimension | RoomMind mean | Baseline mean | Paired difference |
|---|---:|---:|---:|
| Role and strategic fidelity | 4.50 | 5.00 | -0.50 |
| Epistemic / information-boundary fidelity | 5.00 | 5.50 | -0.50 |
| Temporal coherence | 4.00 | 5.75 | -1.75 |
| Interaction-structure fidelity | 3.25 | 4.75 | -1.50 |
| Multi-party dynamics fidelity | 4.25 | 5.50 | -1.25 |
| Procedural fidelity | 4.25 | 5.50 | -1.25 |

Paired RoomMind-minus-Baseline differences by scenarios 1 through 4 were:

- role and strategy: `-3, -1, +3, -1`;
- epistemic fidelity: `0, -2, 0, 0`;
- temporal coherence: `-1, -2, -1, -3`;
- interaction structure: `-3, -3, +2, -2`;
- multi-party dynamics: `-1, -2, 0, -2`;
- procedural fidelity: `-3, -2, +1, -1`.

Exact paired sign-flip p-values ranged from `.125` to `1.0`. With four pairs,
these values are descriptive diagnostics only. They neither establish a
generalizable baseline advantage nor rescue the intended RoomMind advantage.

Scenario 3, the leadership interview, was the only clear RoomMind pair win:
role/strategy `+3`, interaction structure `+2`, and procedural fidelity `+1`.
That local success did not transfer to negotiation, launch decision, or
incident-command scenes.

## Engineering and recovery behavior

| Scenario | Condition | Turns | Messages | Safe fallbacks | Final governor state |
|---:|---|---:|---:|---:|---|
| 1 | Baseline | 20 | 73 | 6 | completed at safety limit |
| 1 | RoomMind | 20 | 56 | 14 | stalled / safety limit |
| 2 | Baseline | 4 | 15 | 2 | completed |
| 2 | RoomMind | 20 | 54 | 10 | stalled / safety limit |
| 3 | Baseline | 20 | 72 | 5 | completed at safety limit |
| 3 | RoomMind | 20 | 58 | 18 | stalled / safety limit |
| 4 | Baseline | 20 | 78 | 2 | completed at safety limit |
| 4 | RoomMind | 20 | 60 | 16 | stalled / safety limit |

The event stream records 58 RoomMind safe-fallback events versus 15 Baseline
events, and 159 versus 48 public-output rejections. This is not a model outage:
there were no degraded-LLM fallbacks. It is a governance/rendering interaction
problem. Common RoomMind rejection causes were public-draft echo, speech that
exceeded the validated lifecycle, truncation, and unsupported artifact or URL
claims.

All deterministic G3 integrity probes reported
`all_applicable_passed = true`. That establishes implementation properties such
as ledger presence, memory partitioning, event provenance fields, clock order,
and lifecycle shape. It does **not** establish conversational realism. Manual
inspection found unsupported current-world statements that regex- and
ledger-shape probes did not classify as violations.

## Full-dialogue manual inspection

Every RoomMind and Baseline transcript was read turn by turn. The main findings
were:

### Scenario 1: supply-chain negotiation

RoomMind opened naturally, then repeatedly requested capacity-validation files,
used visible recovery language, and oscillated from 83 to 84 and back to 83
RMB. Capacity evidence also changed from 2,500 units/day to 3,500 units/day.
Public confirmations did not become accepted task state, so all required fields
remained proposed and the dialogue ended while asking again for the same
evidence. Baseline was also repetitive, but its state progression was less
visibly governed.

### Scenario 2: launch go/no-go meeting

RoomMind introduced unsupported commercial figures, changed LOI and budget
claims, and repeatedly promised calendar, email, and artifact actions. It
eventually voiced a phased-launch decision, but the ledger still classified the
run as stalled with required work open. Baseline reached a decision in four
turns; this was efficient but unrealistically cooperative and therefore should
not be interpreted as a perfect simulation.

### Scenario 3: leadership interview

RoomMind produced a stronger division of interviewer responsibilities and more
role-consistent questioning than Baseline. It nevertheless emitted many generic
fallback lines, repeated already answered questions, and allowed panelists to
“confirm” a candidate's retrospective claims as if those claims were panel
records. The candidate-question phase never closed. Baseline was worse here: the
product and engineering interviewers repeated nearly identical evidence
requests for many turns despite receiving relevant answers.

### Scenario 4: incident command

RoomMind had a strong opening but then asserted unsupported current-world
actions: archived evidence, hashes, write-once repositories, completed rollback,
green health checks, prepared reports, and incident-folder delivery. It moved
toward closure while containment remained active and the scheduled review had
not happened. Baseline also contradicted itself: it proposed rollback from
v4.18 to v4.17, later claimed 100% traffic was restored to v4.18, and then
simultaneously said the rollback to v4.17 had completed. Both conditions were
unrealistic, but RoomMind added more repeated coordination and artifact
language.

## Root-cause interpretation

1. **Public commitment and authoritative state are still split.** An authorized
   participant can explicitly confirm a value in speech while the projector
   records only `information_provided`; the required variable remains proposed.
   The coordinator then treats settled-looking dialogue as unfinished.
2. **Rejection happens too late and too often.** The model generates a complete
   utterance, the renderer rejects it, and repeated full-utterance regeneration
   ends in recognizable fallback language. Safety increases, but naturalness
   and progress fall.
3. **Evidence provenance is too weak.** A participant's own utterance is public
   evidence that the utterance occurred; it is not evidence that an external
   action, upload, health check, hash verification, or approval actually
   occurred.
4. **The coordinator pursues unavailable work.** When the simulation cannot
   produce a real external artifact or tool result, the dialogue continues to
   ask for it instead of reaching a bounded conditional close, handoff, defer,
   or explicit failure.
5. **Fallback observability worked.** G3.4's new safe-fallback metric exposed
   the mechanism that prior generations hid. This is a useful engineering
   result even though realism did not improve.

## Qualification gates

| Gate | Result | Evidence |
|---|---|---|
| Procedural fidelity exceeds matched Baseline | Fail | 4.25 vs 5.50 |
| Temporal and epistemic fidelity do not regress | Fail | 4.00 vs 5.75; 5.00 vs 5.50 |
| No unsupported completed external actions | Fail | Manual inspection found multiple claims in scenarios 2 and 4 |
| Interaction structure improves | Fail | 3.25 vs 4.75 |
| Endings reconcile public commitments and task state | Fail | All four RoomMind runs stalled at the safety limit |
| Technical reproducibility and artifact integrity | Pass | 8/8 dialogues, 8/8 evaluations, matching hashes, fixed model |
| Evaluator structural validity | Fail | Two dimensions contain total scores with malformed/default child metrics |

## Recommended G3.5 direction

Any implementation change must be a new generation and must not alter this
frozen G3.4 batch.

1. Commit speech and state atomically. A deterministic projector should map an
   authorized, explicit confirmation of a configured value directly to the
   corresponding lifecycle transition and task variable.
2. Replace “utterance exists” grounding with source-typed provenance:
   `scenario_seed`, `public_statement`, `simulated_tool_result`, and
   `external_followup`. A current-world completed action must require a
   simulated tool/result event, not self-assertion.
3. Constrain intent before surface generation and repair only the violating
   clause. Avoid two complete regenerations and avoid reusable public fallback
   templates.
4. When available in-session evidence is exhausted, require bounded resolution:
   conditional agreement, handoff, deferment, or explicit failure. Do not ask
   repeatedly for artifacts the text simulation cannot produce.
5. Retain a generic ledger mechanism but give negotiation, go/no-go, interview,
   and incident scenes explicit completion semantics so “realistic ending” is
   appropriate to the activity rather than identical across all scenes.
6. Strengthen evaluator acceptance independently of dialogue generation: every
   required child metric must contain an in-range score, a non-empty reason,
   and valid public evidence references before a dimension is marked complete.

## Research-use conclusion

G3.4 should be reported as a negative, informative development result. It shows
that stronger governance and evidence constraints can prevent crashes and make
failure observable, but can also reduce conversational naturalness and block
task progression when speech, evidence provenance, and authoritative state are
not reconciled. It must not be used as confirmatory evidence that RoomMind
outperforms the baseline.
