# G4.14 Qualification Results

## Disposition

**G4.14 fails strict qualification and must not advance to external human
review.**

The fixed batch completed 8/8 dialogues with zero dialogue failures and zero
degraded LLM output. All 48 independent run-dimension evaluations completed,
all eight transcript hashes recomputed exactly, and all four RoomMind runs pass
every recorded G4.14 and applicable legacy integrity probe.

That deterministic clean-pass result does not survive semantic review. The AI
aggregate favors Baseline by 0.938 points, with zero RoomMind pair wins and one
tie. Manual reading finds unsupported present-world readiness, artifact-review,
and operational-action claims, an unregistered incident owner in published
speech, cross-role action substitution, premature bounded closure, and a
candidate-Q&A phase that reopens and reaches the timebox. G4.14 therefore
improves probe compliance from G4.13's 1/4 to 4/4 while making the descriptive
gap and several real dialogue defects worse. This is evidence of incomplete
probe coverage, not qualification.

## Frozen protocol

- Batch: `e29005cf-d6e5-4e4b-b4e1-34e5036f1e5e`
- Source revision: `6b4e461d5d69659bb8546e285b96f77eccfa4539`
- Architecture: `g4.14-publication-owner-and-artifact-grounding`
- Provider/model: `ollama/gpt-oss:120b` for dialogue and evaluation
- Design: four matched scenarios, Baseline and RoomMind, seed `20260914`
- Dialogue/evaluation concurrency: 1/1
- Manifest SHA-256: `5605c5f71b9f3daeca520ffa7af45cc98bd2d5dbc70f3b6cb70d20bd8ea688d6`
- Evidence use: development-only exploration, not confirmatory evidence

## Completion and artifact integrity

All eight runs reached `evaluation_completed`; all evaluation error maps are
empty. The downloaded artifacts have these local SHA-256 values:

- `transcripts.json`: `724d34aa577c6485ad45c8aafa1c4e185624848c2dda960b1b52a70ebe1dadbe`
- `debug-bundle.json`: `602fe9d1dfcb035405340ae12fcd0c17f5fcae0b2472a14726f0b890ef3f76b0`
- `final-evaluation`: `ec5ed408296fcaa10428e01572e1f424fe2b2cd6962823f23aea39645271cb2e`

Independent canonical-JSON recomputation matched the recorded transcript hash
for every run:

| Run | Condition | Transcript SHA-256 |
| ---: | --- | --- |
| 547 | Baseline | `bba9fcecdc20aa0dacce7c0f2c275acd555f253332cc2713244dc10f089dfd8c` |
| 548 | RoomMind | `96712e8dfce3619666d93390a2d507351e7bed04d01a8fb1c0a08f7986d55289` |
| 549 | Baseline | `fdb8ea254f815df3dc317091f1e8eb2d34e75f87d1e2faa28494b226d3cedcd5` |
| 550 | RoomMind | `9916c68c0969c97308806f9a17570f3df71872ce032d2084e4ed8d4cc4b4d4c5` |
| 551 | Baseline | `8ad41d3629dd9e5abb7939a77beed83e1d67693f2aba3414ef6210a0009699c7` |
| 552 | RoomMind | `78defee9e885ef3f66bd24485debc73c8a7d8a7972d363dce03e0df91f209c32` |
| 553 | Baseline | `bcc173df0619f39d61abbb8f2b5c60988be867c2370bf6d2a28630597b764883` |
| 554 | RoomMind | `ccb3f0ea71eb02c9e4b42af54033a66884ba3247b516352dc1f211c7076e0aa5` |

Evaluation did not alter any frozen transcript.

## Independent AI evaluation

| Dimension | Baseline mean | RoomMind mean | Difference |
| --- | ---: | ---: | ---: |
| Role and strategy | 5.50 | 5.75 | +0.25 |
| Epistemic boundaries | 6.00 | 4.50 | -1.50 |
| Temporal coherence | 5.00 | 4.50 | -0.50 |
| Interaction structure | 5.75 | 4.875 | -0.875 |
| Multi-party dynamics | 5.00 | 4.50 | -0.50 |
| Procedural fidelity | 5.50 | 3.00 | -2.50 |

The unweighted descriptive mean is 5.458 for Baseline and 4.521 for RoomMind,
a difference of -0.938. Scenario-level differences are -0.583, -0.833, 0.000,
and -2.333. RoomMind wins no AI-scored pair, ties the interview pair, and
trails in the other three.

## Run outcomes and telemetry

| Run | Condition | Messages | Outcome / stop | Notable telemetry |
| ---: | --- | ---: | --- | --- |
| 547 | Baseline | 24 | 7 turns | no retry or degraded output |
| 548 | RoomMind | 38 | conditional; 1 open issue; player-requested bounded close | 3 retries, 5 safe and 1 silent recovery |
| 549 | Baseline | 31 | 9 turns | 1 retry, 2 safe fallbacks |
| 550 | RoomMind | 13 | conditional; 2 open issues; player-requested bounded close | 3 retries, 3 safe and 1 silent recovery |
| 551 | Baseline | 57 | 15 turns | 2 retries, 3 safe fallbacks |
| 552 | RoomMind | 44 | conditional; 1 open issue; 20-turn safety timebox | 4 retries, 2 silent recoveries |
| 553 | Baseline | 77 | 20 turns | 4 retries, 3 safe fallbacks, 5 grounding rejections |
| 554 | RoomMind | 15 | deferred; player-requested bounded close | 5 retries, 3 safe and 9 silent recoveries, 1 public-grounding rejection |

No unresolved transport, provider, API, or evaluator failure remains. The
RoomMind incident run reports six final open issues in the run result, while a
lower-level diagnostic surface lists four open obligations; this discrepancy
is itself a state-surface concern even though the exported probes pass.

## Integrity probes

Independent local recomputation reproduced the exported checks. Every recorded
G4.14 and applicable legacy probe is true on all four RoomMind runs, including
the G4.14 publication-owner, direct-response, routing-language, public-evidence,
and current-world-action composite.

Manual reading exposes material false negatives outside those lexical and
ledger surfaces:

- run 550 changes from missing monitoring, rollback, and staffing to claiming
  24/7 coverage, real-time dashboards “in place,” clear rollback criteria, and
  two contracted engineers, without intervening evidence;
- run 552 claims a sprint backlog and engineering design document were reviewed
  although no live artifact is supplied, then reopens evaluation after the
  panel had entered candidate questions;
- run 554 assigns unregistered `Carlos Ruiz` as incident owner in visible
  speech and has one role promise that another role will capture evidence;
- required-response fallback publication can produce conspicuous template or
  malformed wording such as “On statement,” while still satisfying the
  structural probe.

Passing the current probes is therefore necessary but not sufficient.

## Manual reading of all four matched pairs

### Supply-chain negotiation

Baseline is shorter and commercially coherent, although it makes unsupported
claims that attachments were sent. RoomMind eventually obtains an inspection
outline and preserves a conditional close, but it makes the buyer provide the
supplier's production metrics, repeatedly promises the same protocol, and
publishes generic or malformed fallback responses. **Baseline wins.**

### Product launch

Baseline is repetitive and also claims an unsupported attachment, but it keeps
the launch conditional and retains the remaining operational work. RoomMind
reverses an explicit lack of monitoring, rollback, and staffing into unsupported
claims that all three are ready, then closes with unresolved budget and readiness
issues. **Baseline wins; the RoomMind run is unacceptable.**

### Structured interview

RoomMind is more focused early, but claims to have reviewed unsupplied sprint
and design artifacts. After the panel reaches candidate questions, it reopens
product and engineering evaluation and runs to the 20-turn safety timebox.
Baseline is more repetitive but completes the intended panel procedure. The AI
scores tie; manual review finds no defensible RoomMind win. **Tie at best.**

### Incident response

Baseline fabricates extensive live containment, rollback, status-page, and
metric actions and later incoherently revisits containment. RoomMind avoids
some unsafe commitments but does not complete containment or recovery, claims
it is toggling a feature flag, delegates evidence capture across roles, assigns
an unregistered owner, and closes deferred with many open requirements.
**Neither is acceptable; RoomMind is procedurally worse.**

The manual result is zero RoomMind wins, at most one tie, and material defects
in every RoomMind transcript.

## Gate disposition

| Gate | Result | Evidence |
| --- | --- | --- |
| 8/8 frozen dialogues; zero failures/degraded output | PASS | all runs frozen; 0 dialogue failures; 0 degraded |
| Fixed revision/model/seed/manifest | PASS | `6b4e461...`, `ollama/gpt-oss:120b`, seed `20260914` |
| Exact immutable transcript provenance | PASS | all eight hashes independently recomputed |
| Complete six-dimension evaluation | PASS | 48/48; no evaluator errors or replacement |
| Every recorded G4.14/applicable legacy probe passes | PASS | 4/4 RoomMind composite passes |
| Required-response output remains natural and role-local | FAIL | templated/malformed fallback speech in run 548 |
| No unsupported current-world or live-artifact claim | FAIL | runs 550, 552, and 554 contain manual-review false negatives |
| Registered publication owner and no role substitution | FAIL | `Carlos Ruiz` and cross-role action delegation in run 554 |
| Terminal phase and closure integrity | FAIL | run 552 reopens candidate Q&A; all RoomMind runs close conditional/deferred |
| No material routing/repetition regression | FAIL | repeated protocol/close cycles and fallback artifacts remain |
| Stable advantage over Baseline | FAIL | AI aggregate -0.938; 0/4 AI pair wins; manual 0 wins |

## Recommendation

Do not start external human review. Before another live qualification, replace
the growing phrase-list approach with a typed publication-claim boundary that
classifies claims by actor, action, object, time, evidence source, and authority.
Validate the final rendered utterance against the same transition and evidence
state, and reject unregistered named owners in speech rather than only in the
ledger. Make phase terminality monotonic, especially after candidate-Q&A entry,
and treat fallback publication quality as a first-class gate. Add frozen
counterexamples from runs 550, 552, and 554 before changing generation again.

The central conclusion is a probe/behavior divergence: G4.14 achieves a perfect
deterministic clean-pass rate but not a realistic or procedurally reliable
dialogue system. **Strict disposition: FAIL.**
