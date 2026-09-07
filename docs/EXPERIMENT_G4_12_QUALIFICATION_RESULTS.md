# G4.12 Qualification Results

## Disposition

**G4.12 fails strict qualification and must not advance to external human
review.**

The fixed batch completed 8/8 dialogues with zero dialogue failures and zero
degraded LLM output. All eight transcript SHA-256 values recomputed exactly,
and a missing-only evaluator retry completed the final dimension without
changing any prior score or transcript hash.

The candidate nevertheless fails its defining player-response-lock gate.
RoomMind runs 532, 534, and 536 contain wrong, missing, or delayed responses to
player-addressed participants. Runs 532 and 538 also fail the inherited direct
same-turn NPC-response gate; run 534 permits speech after a terminal
confirmation; and run 536 publishes a current-world stored-artifact claim
without simulated tool evidence. Every RoomMind run therefore fails at least
one applicable integrity probe.

## Frozen protocol

- Batch: `c1b732d3-cec8-4d1b-8482-daa98ed813f3`
- Source revision: `433c179408195243a5d5d219db28903a10b08e57`
- Architecture: `g4.12-player-response-lock-and-atomic-speech-grounding`
- Provider/model: `ollama/gpt-oss:120b` for dialogue and evaluation
- Design: four matched scenarios, Baseline and RoomMind, seed `20260912`
- Manifest SHA-256: `54cafebd29343dbfce8e91d99fce3061122fc53ccfd8e98de4da094bf650dfac`
- Evidence use: development-only exploration, not confirmatory evidence

## Evaluation completion and integrity

The first pass completed 47/48 dimensions. Run 534's
`procedural_fidelity` response was truncated/unusable JSON and was rejected.
The missing-only `retry_all=false` evaluation requeued only that dimension. It
returned a score of 6, cleared the technical error, and left all other scores
and all eight transcript hashes unchanged. No dialogue or evaluator code,
configuration, model, seed, scenario, or manifest changed.

The downloaded artifacts match the remote files:

- `transcripts.json`: `0635608dc01044d741a9d6fa1d3f2a7d1de190a3ef879b98d273ebcf5e52bc22`
- `debug-bundle.json`: `a0e7747ab75a7d434ab91324e5b178942632304452d6c6df35b0795cdfd42f0c`
- `final-evaluation`: `651cd2d22fbcb59d768f45a1ea3150496ff5632e4ce8c97783f3f7028c52f356`

Independent canonical-JSON recomputation matched the recorded transcript hash
for runs 531 through 538.

## Independent AI evaluation

| Dimension | Baseline mean | RoomMind mean | Difference |
| --- | ---: | ---: | ---: |
| Role and strategy | 5.75 | 5.50 | -0.25 |
| Epistemic boundaries | 5.25 | 5.25 | 0.00 |
| Temporal coherence | 5.75 | 5.50 | -0.25 |
| Interaction structure | 5.75 | 5.50 | -0.25 |
| Multi-party dynamics | 5.00 | 4.50 | -0.50 |
| Procedural fidelity | 5.00 | 4.50 | -0.50 |

The unweighted descriptive mean is 5.417 for Baseline and 5.125 for
RoomMind, a difference of -0.292. Scenario-level mean differences are -0.667,
-0.500, +0.333, and -0.333. RoomMind therefore trails on five dimensions,
ties one, and wins only one of four matched scenarios by the AI scores.

## Run outcomes and telemetry

| Run | Condition | Messages | Outcome / stop | Notable telemetry |
| ---: | --- | ---: | --- | --- |
| 531 | Baseline | 79 | 20-turn safety stop | 1 safe fallback |
| 532 | RoomMind | 28 | completed, closure locked | 5 retries, 6 silent recoveries |
| 533 | Baseline | 76 | 20-turn safety stop | 1 retry, 1 safe fallback |
| 534 | RoomMind | 26 | completed, closure locked | 6 retries, 1 safe and 10 silent recoveries |
| 535 | Baseline | 60 | completed at turn 18 | 2 retries, 6 safe fallbacks |
| 536 | RoomMind | 47 | conditional timebox close; 2 open issues | 2 retries, 2 safe and 7 silent recoveries |
| 537 | Baseline | 70 | 20-turn safety stop | 4 retries, 2 safe fallbacks, 1 grounding rejection |
| 538 | RoomMind | 48 | conditional timebox close; 5 open issues | 10 retries, 2 safe, 7 silent, 4 duplicate suppressions |

Across the batch there were 30 LLM retries, 15 reported safe fallbacks, 30
silent recoveries, four near-duplicate suppressions, and zero degraded output.
RoomMind accounts for 23 retries and all 30 silent recoveries. The only observed
provider/model binding is `ollama/gpt-oss:120b`. No unresolved transport or API
failure remains in the frozen artifacts.

## Integrity probes

All four Baseline runs pass their seven applicable comparison-integrity checks.
All four RoomMind runs fail strict probe completeness:

- run 532 fails direct NPC response and the new player-addressed response lock;
- run 534 fails terminal-floor locking and the player-addressed response lock;
- run 536 fails current-world tool grounding and the player-addressed response
  lock;
- run 538 fails direct same-turn NPC response.

Representative visible failures are:

- run 532 sequence 6 asks Mr. Wang for the required volume, but the Quality
  Director speaks first; sequence 26 asks Emma for sign-off and receives no NPC
  response until a later player floor relay;
- run 534 sequence 3 addresses Operations and Finance, but Finance is omitted;
  sequence 9 asks Operations for confirmation and Finance interrupts; after
  Finance's terminal confirmation at sequence 23, Operations and Sales still
  speak at sequences 25-26;
- run 536 sequence 24 asks the People Partner for confirmation, but Engineering
  and Product consume the floor and the target responds only after another
  player relay; sequence 13 claims measurements are already stored in an
  internal metrics database/dashboard without simulated tool evidence;
- run 538 sequence 25 asks Communications directly, but the player must relay
  the floor before the response. The transcript repeatedly re-confirms the same
  communications owner and ends with five required items still open.

The atomic rejected-transition surface check passes in every RoomMind run, so
that narrow G4.12 mechanism improved. The full G4.12 response-routing mechanism
did not converge.

## Manual reading of all four matched pairs

### Supply-chain negotiation

Baseline is extremely long, contradicts itself on contract timing and liability
wording, and reopens settled quality work. RoomMind is substantially shorter
and reaches an internally reconciled close, but it still lets unrelated roles
answer player-targeted questions and needs explicit player floor relays. On
overall usability RoomMind wins narrowly, while failing the defining strict
routing gate.

### Product launch

Baseline is repetitive and makes unsupported document/calendar claims, but it
keeps the three prerequisite owners recognizable and obtains a coherent launch
decision. RoomMind lets Finance interrupt an Operations-directed confirmation,
has Operations draft a budget proposal outside its role, omits a named Finance
response, and continues NPC speech after terminal confirmation. Baseline wins.

### Structured interview

Baseline loops across sixty messages, occasionally has panelists supply answers
that should come from the candidate, and stops with questions unanswered.
RoomMind is more focused and obtains concrete product, engineering, and people
evidence, but misroutes the People Partner floor and asserts that measurements
are already stored in internal systems without tool evidence. RoomMind wins
narrowly on interaction quality but remains procedurally disqualified.

### Incident response

Baseline contains unsupported live-action claims and a visibly malformed JSON
fragment at sequence 64. RoomMind avoids that malformed surface but repeatedly
reopens the communications-owner assignment, requires a player relay for a
direct Communications question, and closes conditionally with five open items.
Neither condition is acceptable; no winner is assigned.

The manual result is two narrow RoomMind wins, one Baseline win, and one tie.
That is not a stable advantage, conflicts with the adverse AI aggregate, and
does not offset deterministic gate failures.

## Gate disposition

| Gate | Result | Evidence |
| --- | --- | --- |
| 8/8 frozen dialogues; zero failures/degraded output | PASS | all runs frozen; 0 failures; 0 degraded |
| Fixed revision/model/seed/manifest | PASS | `433c179...`, `ollama/gpt-oss:120b`, seed `20260912` |
| Exact immutable transcript provenance | PASS | all eight hashes independently recomputed |
| Complete six-dimension evaluation | PASS | 48/48 after one missing-only retry; prior results unchanged |
| Rejected transitions cannot reappear in speech | PASS | no G4.11 surface violations in RoomMind |
| Player-addressed response locks | FAIL | violations in runs 532, 534, and 536 |
| Direct same-turn NPC responses | FAIL | violations in runs 532 and 538 |
| Terminal floor locks | FAIL | post-terminal speech in run 534 |
| Current-world artifact/action grounding | FAIL | unsupported stored-artifact claim in run 536 |
| Every applicable legacy through G4.12 probe passes | FAIL | every RoomMind run fails at least one probe |
| No material routing/repetition regression | FAIL | wrong/missing targets, relays, and repeated owner confirmation |
| Stable advantage over Baseline | FAIL | AI aggregate -0.292; only 1/4 AI pair wins; manual advantage not stable |

## Recommendation

Do not start external human review. A successor should enforce the response
queue at the actual publication boundary, carry unresolved targets across
turns without requiring player relay, and make terminal confirmation suppress
all later nonessential speech. It should also apply current-world evidence
grounding to generated player claims and add frozen runtime regressions for the
specific G4.12 violations above before another live batch.

G4.12 validates the atomic rejected-transition speech boundary, but fails its
new response-lock mechanism and applicable legacy gates. **Strict disposition:
FAIL.**
