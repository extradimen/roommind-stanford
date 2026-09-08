# G4.15 Qualification Results

## Disposition

**G4.15 fails strict qualification and must not advance to external human
review.**

The authorized fixed-model batch completed all eight frozen dialogues with
zero dialogue failures and zero degraded LLM output. All 48 independent
run-dimension evaluations completed without retry, and independent canonical
JSON recomputation matched every recorded transcript hash.

Those operational gates do not establish semantic qualification. Only one of
the four RoomMind runs passes every applicable integrity probe. The AI
aggregate is 4.538 for RoomMind versus 5.250 for Baseline, a difference of
-0.713, and RoomMind wins only one of four scored pairs. Manual reading finds
unsupported current-world capacity and artifact claims, failed response
ownership, broken multi-addressee routing, post-terminal interview speech, and
repetitive low-information fallbacks. G4.15's new typed diagnostics are empty
on all RoomMind runs despite several of those visible failures, so important
coverage gaps remain.

## Frozen protocol

- Batch: `ff6098d3-0cc5-41f6-90a2-5e35076c5dd2`
- Source revision: `5752d34bdeb08b9b35cb048011ed9b9e247c68c9`
- Architecture: `g4.15-typed-publication-and-terminal-phase-governance`
- Provider/model: `ollama/gpt-oss:120b` for dialogue and evaluation
- Design: four matched scenarios, Baseline and RoomMind, seed `20260915`
- Dialogue/evaluation concurrency: 1/1
- Manifest SHA-256: `130da6329ddbdee19a7190512ad64b925567dbab5b64e43b6d4cec336151b3c6`
- Evidence use: development-only exploration, not confirmatory evidence

## Completion and artifact integrity

All eight runs reached `evaluation_completed`; all evaluation error maps are
empty. The downloaded artifacts have these local SHA-256 values:

- `g4-15-transcripts.json`: `194d0b5bebae68fa3e7ac18e597139a3c31a7993a1dd8156c23d00c04f46e561`
- `g4-15-debug-bundle.json`: `394eabf1148bbbae6d084901ccad771982261c2ce7345d45729e1ea883e5b6d2`
- `g4-15-final-evaluation.json`: `98cc77fafcdcc6826c26b4b3811b35a6446da59e4532810f5077c3359ea668b2`

Independent canonical-JSON recomputation matched the recorded transcript hash
for every run:

| Run | Scenario | Condition | Messages | Transcript SHA-256 |
| ---: | ---: | --- | ---: | --- |
| 555 | 1 | Baseline | 79 | `9be48b4ec90fa8d133b613012a5fc305674c0cb7c3945e44c0f28c9b977cb0f8` |
| 556 | 1 | RoomMind | 32 | `3b2223f47dd6ab84df0e550cbe4b30d086ce90be50c2392c765a177586e145c5` |
| 557 | 2 | Baseline | 73 | `038de8b6eac12088a220d53e2d95ecb0ddd3dec15aa13bbfbecaa7dcca45c87b` |
| 558 | 2 | RoomMind | 14 | `970ab9ac86786a2351f2f7894bf04a216b34b31f0ca3d3a8ad1f2b11874665db` |
| 559 | 3 | Baseline | 40 | `36fb4b427f17af5b7794f618155fc185e43691bcbd9a4fa653256073bfad8773` |
| 560 | 3 | RoomMind | 34 | `c736c6cfbc49a086ef88174f9310004d83e168724732f876185462813e2fa4d1` |
| 561 | 4 | Baseline | 17 | `797af2feccb093f52788e495f8b68a72f59e6565dfa52fca5c93385671e57726` |
| 562 | 4 | RoomMind | 27 | `fd2e508ebd94c1bf9ac4b277931f48e0f6f9875040a3fa5c8c6e4c16b86973e0` |

Evaluation did not alter any frozen transcript.

## Independent AI evaluation

| Dimension | Baseline mean | RoomMind mean | Difference |
| --- | ---: | ---: | ---: |
| Role and strategy | 5.50 | 5.00 | -0.50 |
| Epistemic boundaries | 4.50 | 4.75 | +0.25 |
| Temporal coherence | 5.75 | 4.25 | -1.50 |
| Interaction structure | 5.50 | 4.125 | -1.375 |
| Multi-party dynamics | 5.25 | 4.35 | -0.90 |
| Procedural fidelity | 5.00 | 4.75 | -0.25 |

The unweighted descriptive mean is 5.250 for Baseline and 4.538 for RoomMind,
a difference of -0.713. Scenario-level means are:

| Scenario | Baseline | RoomMind | Difference |
| ---: | ---: | ---: | ---: |
| 1 | 5.500 | 5.750 | +0.250 |
| 2 | 5.167 | 3.167 | -2.000 |
| 3 | 6.000 | 5.900 | -0.100 |
| 4 | 4.333 | 3.333 | -1.000 |

RoomMind wins one AI-scored pair and trails in three.

## Run outcomes and telemetry

| Run | Condition | Turns / messages | Outcome / stop | Notable telemetry |
| ---: | --- | ---: | --- | --- |
| 555 | Baseline | 20 / 79 | completed | 2 safe fallbacks; 1 grounding rejection |
| 556 | RoomMind | 14 / 32 | conditional; 1 open issue; bounded close | 11 retries, 2 safe and 6 silent recoveries, 1 grounding rejection |
| 557 | Baseline | 19 / 73 | completed | 1 retry, 1 safe fallback |
| 558 | RoomMind | 7 / 14 | conditional; 3 open issues; bounded close | 5 safe fallbacks |
| 559 | Baseline | 12 / 40 | completed | 2 safe fallbacks |
| 560 | RoomMind | 14 / 34 | completed; completion conditions met | 2 retries, 2 safe and 1 silent recovery |
| 561 | Baseline | 5 / 17 | completed | 1 retry, 2 safe fallbacks |
| 562 | RoomMind | 10 / 27 | deferred; 6 open issues; bounded close | 4 retries, 8 safe fallbacks, 5 public/current-world rejections |

Across RoomMind, the system recorded 17 retries, 17 safe fallbacks, 7 silent
recoveries, 6 public-grounding rejections, 5 current-world-grounding
rejections, and zero degraded output. There are no unresolved dialogue,
transport, provider, API, or evaluator failures.

## Integrity probes

Only run 562 passes every applicable probe. Runs 556, 558, and 560 fail the
G4.12 response lock, G4.13 response/terminal convergence, G4.14
publication-owner/artifact convergence, and the G4.15 composite. Run 560 also
fails the G4.10 terminal confirmation floor lock.

Concrete violations include:

- run 556 asks the quality director and later the supplier CEO to answer, but
  the procurement ally speaks while the named role remains missing;
- run 558 requests ordered responses from sales, operations, and finance, but
  produces only a generic operations fallback and does not preserve the
  multi-addressee response chain;
- run 560 asks the people partner for evidence, receives product and
  engineering responses instead, and later publishes engineering speech after
  the interview's terminal event;
- run 562 passes the deterministic chain and rejects five unsafe current-world
  claims, but the visible conversation degrades into repetitive fallback
  requests and closes deferred with six open issues.

The new G4.15 diagnostic arrays for typed publication-claim violations,
terminal-phase reentries, and synthetic fallback fragments are empty in all
four RoomMind runs. Manual review nevertheless finds unsupported present-world
capacity and attachment assertions in run 556, a visible terminal continuation
in run 560, and conspicuous fallback speech in runs 558 and 562. The composite
does catch three runs through legacy-dependent failures, but the new typed
surfaces do not yet directly represent all motivating defects.

## Manual reading of all four matched pairs

### Supply-chain negotiation

Baseline loops for 79 messages, contradicts its earlier quality threshold, and
claims current reports or attachments without tool evidence. RoomMind is more
bounded and obtains useful commercial terms, but invents current production
capacity and pilot-compliance facts, claims an attached summary, violates two
explicit response-owner handoffs, and leaves a publicly discussed price item
open in state. The AI narrowly prefers RoomMind, but neither transcript is a
clean semantic pass. **No acceptable winner.**

### Product launch

Baseline is long and makes unsupported current readiness and artifact claims,
but it maintains a coherent multi-role launch discussion. RoomMind breaks the
ordered response chain almost immediately: two named respondents disappear,
the remaining response is generic, a later handoff is refused despite prior
evidence, and the dialogue closes after 14 messages with operations, budget,
and decision work unresolved. **Baseline wins; RoomMind is unacceptable.**

### Structured interview

Baseline is substantive but reopens assessment after moving to candidate
questions. RoomMind is somewhat more concise, yet misroutes a question intended
for the people partner, asks for nonexistent artifacts, and allows engineering
speech after the terminal event. The new phase guard does not catch this
continuation form. **No clean winner; neither supports qualification.**

### Incident response

Baseline is concise but fabricates live forensic, containment, storage, and
status-page actions. RoomMind correctly rejects several current-world claims
and is the only probe-clean RoomMind run, yet repeatedly publishes templated,
low-information requests, crosses a role boundary around incident ownership,
and closes deferred with six unresolved issues. **No acceptable winner.**

Manual review therefore finds zero defensible RoomMind wins, one Baseline win,
and three pairs with no acceptable winner.

## Gate disposition

| Gate | Result | Evidence |
| --- | --- | --- |
| 8/8 frozen dialogues; zero failures/degraded output | PASS | all runs frozen; 0 dialogue failures; 0 degraded |
| Fixed revision/model/seed/manifest | PASS | `5752d34...`, `ollama/gpt-oss:120b`, seed `20260915` |
| Exact immutable transcript provenance | PASS | all eight hashes independently recomputed |
| Complete six-dimension evaluation | PASS | 48/48; no evaluator errors or retry |
| Every G4.15/applicable legacy probe passes | FAIL | only run 562 passes; runs 556, 558, and 560 fail |
| Required-response output remains natural and role-local | FAIL | missing owners, generic and repetitive fallbacks |
| No unsupported current-world or live-artifact claim | FAIL | manual false negatives in run 556 and Baselines |
| Terminal phase and closure integrity | FAIL | post-terminal speech in run 560; conditional/deferred closures |
| No material routing/repetition regression | FAIL | multi-addressee and direct-response failures remain |
| Stable advantage over Baseline | FAIL | AI aggregate -0.713; 1/4 AI pair wins; manual 0 wins |

## Recommendation

Do not start external human review. Before another live qualification, make
response ownership and terminal phase transitions single authoritative state
machines rather than separately checked speech heuristics. Bind current-world
quantities and attachment/review statements to typed evidence objects, include
capacity and compliance assertions in the typed claim surface, and turn
fallback naturalness and information gain into deterministic gates. Add the
exact failures from runs 556, 558, 560, and 562 as frozen counterexamples before
further generation changes.

G4.15 demonstrates a useful incident-safety improvement, but it neither closes
the probe/behavior gap nor beats Baseline consistently. **Strict disposition:
FAIL.**
