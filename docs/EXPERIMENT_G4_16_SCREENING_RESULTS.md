# G4.16 Screening Results

## Disposition

**G4.16 fails strict screening and must not advance to external human review or
confirmatory testing in its current form.**

The authorized fixed-model batch completed all 16 frozen dialogues with zero
dialogue failures, zero cancellations, and zero degraded LLM output. All 96
independent run-dimension evaluations completed, and independent canonical JSON
recomputation matched every recorded transcript hash. The three downloaded
artifacts also match the server copies byte-for-byte by SHA-256.

Those operational gates do not establish semantic qualification. None of the
eight RoomMind runs passes every applicable integrity probe. The six-dimension
descriptive mean is 4.854 for RoomMind versus 5.583 for Baseline, a difference
of -0.729. RoomMind wins only two of eight AI-scored matched pairs. Manual
reading finds repeated low-information fallback loops, unsupported live
artifact and current-world claims, response-owner failures, terminal-floor
violations, conditional commitments treated too strongly, and incomplete task
closure. G4.16 is development screening evidence only and supports no causal or
confirmatory superiority claim.

## Frozen protocol

- Batch: `28a42b33-b95d-4953-b8b3-f518f62bc9c8`
- Source revision: `f6111ece8b14d4e102482d4c4d41e54f96660045`
- Architecture: `g4.16-shared-simulation-and-resumable-evidence-governance`
- Provider/model: `ollama/gpt-oss:120b` for dialogue and evaluation
- Design: four matched world-v3 scenarios, two repetitions, Baseline and
  RoomMind; 16 dialogues and 96 dimension evaluations
- Dialogue/evaluation concurrency: 1/1
- Seed: `20260916`
- Manifest SHA-256:
  `25ddedbe903c71515eeebea25f26e6b7d1572ba58eb6c0c980fb53a73d9df76e`
- Frozen-input aggregate SHA-256:
  `1c5831af603b148e84237e62779c768c46e0628ed5b3e454f9816e0a3cb7d3a6`
- Evidence use: `candidate_selection_only`; repeatedly inspected development
  scenarios, not confirmatory evidence

The four per-scenario frozen-input hashes are:

| Scenario | Slug | SHA-256 |
| ---: | --- | --- |
| 13 | `candidate-panel-interview-world-v3` | `78a1d12d134c0394c3bb9b962a4ccb9c089a5fdeefdbf9798ccd04670155f42f` |
| 14 | `incident-response-command-world-v3` | `38500735190865d9a71e639eefcb747aaa0723b319b8cec01137a66096fa56ed` |
| 15 | `market-launch-go-no-go-world-v3` | `3a9d7eccd76edeee5ef068d5b2b3f70e386a391602d382d8aca730d72adf1991` |
| 16 | `supply-chain-negotiation-world-v3` | `b8c2a71f5016e9f16a410ade50c73b1aac3b9dd5fa37e05732140220df4c0520` |

## Completion and artifact integrity

The batch reports `evaluation_completed`, 16 completed runs, zero failed runs,
and zero cancelled runs. All evaluation error maps are empty. Telemetry records
only provider `ollama` and model `gpt-oss:120b` for LLM requests.

Downloaded artifact hashes, independently compared with the server copies:

- `transcripts.json` (7,201,955 bytes):
  `495ee67c05518ed8d04ac3cc78ae164b059eb1ee717a634e8c3c76bc37a90f59`
- `debug-bundle.json` (14,995,863 bytes):
  `aa4d80a91f1dd13062450aa9b3f351d1c83c32f6d567107c3b592774b39caba8`
- `final-evaluation.json` (14,402 bytes):
  `04ed74df1826bca3c706462280b56183f4d056f648349622fcd3bce8e050f910`

Independent canonical-JSON recomputation matched the recorded transcript hash
for every run:

| Run | Scenario / repetition | Condition | Messages | Transcript SHA-256 |
| ---: | --- | --- | ---: | --- |
| 565 | interview r1 | Baseline | 107 | `3d6eb31cd3ab06d7cdc0d622057681616a9eb09ef8a8fe1f2f7f2c1b025355ab` |
| 563 | interview r1 | RoomMind | 79 | `95c33b51e1acee93ac2377d820e8cae8c057afc47aa48da82199c161dccf1092` |
| 566 | interview r2 | Baseline | 170 | `268f131195e5cbd33db49b66a5325f0007a23f808193b1344a7c70cd62898b0f` |
| 564 | interview r2 | RoomMind | 50 | `df366c4b3afb2a95b30fcac0107a61f14a5e5784510eaddb5343845237039305` |
| 569 | incident r1 | Baseline | 55 | `9b0566785ec21400fd690db1009f4f5f6727a9a269d6fbaffbc255c78be59f8e` |
| 567 | incident r1 | RoomMind | 28 | `c7a1ded5416f8493398c7a44e7710c0de7131a1a8aa98f7a195860c76876cda6` |
| 570 | incident r2 | Baseline | 45 | `6d605649329d4ff3094c9f81cb29d7d431bf54dbd67e33846d1f5314981525e7` |
| 568 | incident r2 | RoomMind | 30 | `e3a31987f3f2580e8d9231f535c3678e7f8c3ced8cefded87e438f5528e738fc` |
| 573 | launch r1 | Baseline | 64 | `5ffaa2fd585e0b4be299c3fda6d8efe598f67ce2d177ae20e059ec612c022753` |
| 571 | launch r1 | RoomMind | 21 | `c88e6609e831b108375d8378f6e1b43c861ee2bc0cf0df99824adb07867f37e0` |
| 574 | launch r2 | Baseline | 35 | `70ae9df78ffd2d3660c93b6bfbb46dad254550ba64c468ef9f0184c4b9cbba5b` |
| 572 | launch r2 | RoomMind | 18 | `d72799b4001c1b7e40d16529f1d1b79fe84477466b3ce16ec6169e2edb76f134` |
| 577 | negotiation r1 | Baseline | 20 | `3a98a311ed465b404922871c30b7fdab96e809d20a52ebe08eb928b55b293e5c` |
| 575 | negotiation r1 | RoomMind | 15 | `78cc64e3eaee1e07575c2af33e5c00777e754a63a61f2bb4e9eb91bf24642a80` |
| 578 | negotiation r2 | Baseline | 64 | `f629d7c67011c47730c42d2491ba5470b04eb7ed235217aa7ee3a87a91009491` |
| 576 | negotiation r2 | RoomMind | 30 | `0f9b50ba9af1fc824c2fbdd04586cf6e7d2370378fe727b5caf2de0693c56ed4` |

Evaluation did not alter any frozen transcript. No dialogue retry created a
replacement session. The new same-session interruption recovery path was not
exercised by this live batch, so the live recovery gate is **not applicable / not
demonstrated**, rather than passed.

## Independent AI evaluation

| Dimension | Baseline mean | RoomMind mean | Difference |
| --- | ---: | ---: | ---: |
| Role and strategy | 5.875 | 5.375 | -0.500 |
| Epistemic boundaries | 5.500 | 4.875 | -0.625 |
| Temporal coherence | 5.625 | 4.750 | -0.875 |
| Interaction structure | 5.500 | 4.875 | -0.625 |
| Multi-party dynamics | 4.875 | 4.500 | -0.375 |
| Procedural fidelity | 6.125 | 4.750 | -1.375 |

The unweighted descriptive mean is 5.583 for Baseline and 4.854 for RoomMind,
a difference of -0.729. Pair-level means are:

| Matched pair | Baseline | RoomMind | Difference |
| --- | ---: | ---: | ---: |
| Interview r1 | 4.833 | 4.500 | -0.333 |
| Interview r2 | 5.333 | 5.833 | +0.500 |
| Incident r1 | 5.500 | 5.000 | -0.500 |
| Incident r2 | 6.000 | 4.833 | -1.167 |
| Launch r1 | 6.000 | 2.500 | -3.500 |
| Launch r2 | 5.500 | 4.500 | -1.000 |
| Negotiation r1 | 6.000 | 5.667 | -0.333 |
| Negotiation r2 | 5.500 | 6.000 | +0.500 |

RoomMind wins two pairs and trails in six. Scores remain separate from manual
audit and are descriptive only.

## Executor, receipts, and telemetry

The shared simulated-world executor did produce condition-neutral, exact
server-registry receipts in the incident scenario. All four incident runs share
the same contract hash
`8ff9d974ac277362fbf7c5be8da40c9755115110b97bb0192ab00b41b7bd9de8`.
Both conditions persisted successful receipts for scope diagnosis, evidence
preservation, and containment activation. RoomMind run 567 additionally
persisted a blocked precondition attempt without changing world facts, then
successfully executed the action after its prerequisite. This validates the
narrow executor and idempotent/precondition behavior in live generation.

The executor did not solve the surrounding publication problem. RoomMind run
568 later claimed that a full snapshot, memory dump, immutable S3 storage, hash,
and chain-of-custody upload had completed without a corresponding registered
operation. Baseline incident transcripts also made unregistered live status-page
and rollback/archive claims. Baseline's RoomMind-specific legacy probe fields are
not applicable, so `all_applicable_passed=true` for Baseline must not be read as
semantic cleanliness or condition-parity proof.

Across the eight RoomMind runs there were 30 retry events, 30 safe fallbacks, 28
silent recoveries, 7 public-grounding rejections, 5 current-world-grounding
rejections, 1 unregistered-owner rejection, 3 near-duplicate suppressions, 37
obligation-duplicate suppressions, and 16 public-clause repairs. Baseline had 13
retry events, 23 safe fallbacks, no silent recoveries, 3 public-grounding
rejections, and 10 public-clause repairs. Neither condition used a degraded LLM
fallback.

## Integrity probes

Every Baseline run passes its limited applicable probe set. **All eight RoomMind
runs fail at least one applicable probe:**

- interview r1 fails task-critical focus, terminal-floor locking, response /
  terminal / grounding convergence, and the G4.15 composite;
- interview r2 fails terminal-floor locking, response / terminal / grounding
  convergence, and the G4.15 composite;
- incident r1 fails public evidence grounding, task-critical focus, same-speaker
  repetition, obligation repetition, cross-speaker repetition, live-artifact
  grounding, and publication-owner/artifact convergence;
- incident r2 fails conditional-confirmation handling, public evidence grounding,
  and publication-owner/artifact convergence;
- launch r1 fails same-speaker near-duplicate control;
- launch r2 fails cross-role obligation and issue-repetition controls;
- negotiation r1 fails terminal-floor locking, response / terminal / grounding
  convergence, and the G4.15 composite;
- negotiation r2 fails player-addressed response ownership, response / terminal /
  grounding convergence, publication-owner/artifact convergence, and the G4.15
  composite.

The exported deterministic probe schema still ends at the G4.15 composite and
does not expose a named G4.16 composite for executor provenance, frozen-input
binding, response-queue persistence, and same-session recovery. Those mechanisms
have supporting artifacts and local tests, but the missing live composite is a
coverage gap that should be corrected before another candidate is screened.

## Manual reading of all eight matched pairs

### Interview, repetition 1

Baseline repeatedly asks nearly identical product and engineering questions,
but eventually obtains and confirms the required evidence. RoomMind is shorter
but interleaves artifact promises, reopened evidence collection, and candidate-
question closure; it repeatedly asks for material already provided and uses
future uploads as if they were useful present evidence. **Baseline is less bad;
neither is a clean semantic pass.**

### Interview, repetition 2

RoomMind produces the strongest interview transcript: evidence is concrete,
roles are differentiated, and the main stages are substantially coherent.
However, after the panel says it is wrapping up, the player reopens questions and
the panel continues speaking, matching the terminal-floor failures. Baseline is
far longer and heavily repetitive, with evidence collection restarting after
closure. **RoomMind wins descriptively but remains ineligible.**

### Incident response, repetition 1

Both conditions use exact executor receipts for scope, preservation, and
containment. Baseline then loops on rollback completion and makes unsupported
status-page claims. RoomMind correctly records an initially blocked preservation
request and later successful execution, but first states containment is active
before its receipt, repeats low-information refusals, and closes with required
items unresolved. **No acceptable winner.**

### Incident response, repetition 2

Baseline preserves the action prerequisite chain and reaches a bounded unresolved
rollback state, although it narrates unregistered archive work. RoomMind executes
the three registered actions but then invents completion of snapshot, memory-dump,
immutable-storage, hash, and audit-repository operations. It also mishandles a
conditional approval and response ownership. **Baseline wins; RoomMind is
unacceptable.**

### Product launch, repetition 1

Baseline is verbose and invents sent attachments and invitations, but maintains a
recognizable cross-functional decision process. RoomMind stalls for 21 messages:
Operations repeatedly refuses to provide scenario-disclosable evidence, Finance
never approves, and no launch decision is reached. **Baseline wins; RoomMind is
unacceptable.**

### Product launch, repetition 2

Baseline reaches a bounded phased launch with operational constraints, despite
minor repetition and a protected-information concern noted by the evaluator.
RoomMind begins with a strong market claim, later has Sales claim insufficient
information, leaves operational readiness and the joint launch decision open,
and closes after repeated confirmation requests. **Baseline wins.**

### Supply-chain negotiation, repetition 1

Baseline reaches a concise core package, but supplier and quality roles give
conflicting capacity figures and claim attachments without evidence. RoomMind is
also concise and reaches the price and lead-time terms, yet the player speaks as
if it owns supplier production capacity, quality confirmation changes without
new evidence, and NPC speech continues around the terminal event. **No clean
winner; neither supports qualification.**

### Supply-chain negotiation, repetition 2

Baseline is excessively long, repeatedly promises or claims delivery of documents,
and keeps renegotiating already accepted terms. RoomMind is more coherent and
compact, but a player-addressed supplier response is replaced by the quality
director and final contract/document assertions lack a trusted artifact surface.
**RoomMind wins descriptively but remains ineligible.**

Manual review therefore records two descriptive RoomMind wins, four Baseline
wins, and two pairs with no acceptable winner. The manual judgment agrees with
the AI result that RoomMind has no stable advantage and confirms multiple strict
semantic failures not reducible to score noise.

## Gate disposition

| Gate | Result | Evidence |
| --- | --- | --- |
| 16/16 frozen dialogues; zero technical failures | PASS | 16 completed, 0 failed, 0 cancelled |
| Zero degraded dialogue output | PASS | 0 degraded fallbacks |
| Fixed revision/model/seed/manifest/input binding | PASS | fixed revision and hashes above; only `ollama/gpt-oss:120b` observed |
| Exact immutable transcript provenance | PASS | all 16 transcript hashes independently recomputed |
| Complete six-dimension evaluation | PASS | 96/96; no evaluation errors |
| Shared executor parity and exact registered receipts | PASS | same contract and receipt schema in both conditions; blocked request did not mutate facts |
| Same-session interruption recovery | NOT EXERCISED | no retry or recovered prior session in this batch |
| Every G4.16/applicable legacy probe passes | FAIL | 0/8 RoomMind runs pass all applicable probes; no named G4.16 composite exported |
| No unsupported current-world/live-artifact claims | FAIL | manual and deterministic failures in incident and other scenarios |
| Response ownership, repetition, and terminal integrity | FAIL | multiple probe failures and visible loops/post-terminal speech |
| Valid evidence-to-decision closure | FAIL | launch runs and incident runs close with material open work; conditionality mishandled |
| Stable advantage over Baseline | FAIL | AI aggregate -0.729; RoomMind wins 2/8 pairs |
| External human review starts automatically | PASS | no external human review was started |

## Recommendation

Do not tune another generation directly against these same four development
scenarios without first changing the validation architecture. Add a named G4.16
composite that applies condition-neutral receipt/publication checks to both
conditions, represent every executable live-artifact claim as a closed operation
vocabulary, and make terminal floor plus response ownership a single persistent
queue/state-machine invariant. Reduce fallback loops by requiring each retry or
fallback to add an admissible fact, execute an available operation, transfer the
floor to the correct owner, or close once.

After local and frozen-counterexample tests pass, use this result only to choose a
candidate. Any confirmation experiment must preregister unseen scenario instances
before outputs are inspected. **Strict disposition: FAIL.**
