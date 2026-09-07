# G4.13 Qualification Results

## Disposition

**G4.13 fails strict qualification and must not advance to external human
review.**

The fixed batch completed 8/8 dialogues with zero dialogue failures and zero
degraded LLM output. Independent evaluation completed all 48 run-dimensions
without a retry, and all eight transcript SHA-256 values recomputed exactly.

The candidate nevertheless fails its defining convergence gate. RoomMind runs
542 and 544 violate the inherited player-addressed response lock, and run 546
violates direct same-turn NPC response routing. Consequently three of four
RoomMind runs fail `g413_response_terminal_and_grounding_converged`. The
descriptive AI aggregate also favors Baseline by 0.417 points, and manual pair
review finds no stable RoomMind advantage.

## Frozen protocol

- Batch: `335f6406-5cd2-4028-a5ac-9803a4b8bd9a`
- Source revision: `87688345d961b8d0e834d34bd5498c37783e50b2`
- Architecture: `g4.13-required-response-and-terminal-state-convergence`
- Provider/model: `ollama/gpt-oss:120b` for dialogue and evaluation
- Design: four matched scenarios, Baseline and RoomMind, seed `20260913`
- Dialogue/evaluation concurrency: 1/1
- Manifest SHA-256: `457610af1ba8cbf1f26b82dc093a09107358eb01ea2f6330a8b9eba8e5b6da40`
- Evidence use: development-only exploration, not confirmatory evidence

## Completion and artifact integrity

All eight runs reached `evaluation_completed`; all evaluation error maps are
empty. The downloaded artifacts have these local SHA-256 values:

- `transcripts.json`: `c59d242c4b7bd2f0b25e47699b527a7365cb378e52d7394d9c1c6a4eb85739fd`
- `debug-bundle.json`: `7b5c29ffccfab69589f0312638c0a64a91160e22927157c0dcc58aba2b524c6d`
- `final-evaluation`: `47b6f37e8383654a16ff73cc59530cfcaf50791a0ef64453c48a420e4624b894`

Independent canonical-JSON recomputation matched the recorded transcript hash
for runs 539 through 546. Evaluation did not alter any frozen transcript.

## Independent AI evaluation

| Dimension | Baseline mean | RoomMind mean | Difference |
| --- | ---: | ---: | ---: |
| Role and strategy | 5.25 | 5.00 | -0.25 |
| Epistemic boundaries | 5.25 | 5.00 | -0.25 |
| Temporal coherence | 5.25 | 4.50 | -0.75 |
| Interaction structure | 5.25 | 4.75 | -0.50 |
| Multi-party dynamics | 4.75 | 4.75 | 0.00 |
| Procedural fidelity | 5.25 | 4.50 | -0.75 |

The unweighted descriptive mean is 5.167 for Baseline and 4.750 for RoomMind,
a difference of -0.417. Scenario-level mean differences are -0.167, -0.833,
+1.333, and -2.000. RoomMind wins only the interview pair by AI score, ties no
pair, and trails in the other three.

## Run outcomes and telemetry

| Run | Condition | Messages | Outcome / stop | Notable telemetry |
| ---: | --- | ---: | --- | --- |
| 539 | Baseline | 80 | 20-turn safety stop | no retry or fallback |
| 540 | RoomMind | 22 | completed, closure locked | 2 retries, 1 silent recovery |
| 541 | Baseline | 63 | 16 turns | 1 retry, 2 safe fallbacks |
| 542 | RoomMind | 47 | conditional timebox close; 1 open issue | 4 retries, 4 safe and 10 silent recoveries |
| 543 | Baseline | 79 | 20-turn safety stop | 2 retries, 4 safe fallbacks |
| 544 | RoomMind | 44 | premature conditional timebox close; 1 open issue | 2 safe, 8 silent recoveries, 3 grounding rejections |
| 545 | Baseline | 50 | 14 turns | 2 safe fallbacks |
| 546 | RoomMind | 25 | player-requested deferred close; 4 open issues | 1 retry, 2 safe, 1 silent recovery, 2 grounding rejections |

Across generation there were ten retry events, sixteen safe fallbacks, twenty
silent recoveries, and zero degraded output. RoomMind accounts for seven
retries and all twenty silent recoveries. No unresolved transport, provider,
API, or evaluator failure remains in the frozen artifacts.

## Integrity probes

Run 540 passes every applicable probe. Three RoomMind runs do not:

- run 542 fails `g412_player_addressed_response_lock_respected`: sequence 15
  asks Samir directly, but no NPC response follows until a generated player
  routing prompt at sequence 16;
- run 544 fails the same lock: sequence 38 asks Avery for the roadmap link,
  but Engineering and People consume the floor and Avery never responds before
  the next player message;
- run 546 fails `g411_npc_questions_receive_direct_same_turn_response`:
  Priya asks Marcus directly at sequence 17, but the player inserts an
  administrative floor handoff at sequence 18 before Marcus responds.

Those failures make `g413_response_terminal_and_grounding_converged` false in
runs 542, 544, and 546. All other applicable recorded RoomMind checks pass,
including sequence integrity, speaker registration, conditional-confirmation
rejection, post-closure speech suppression, accepted-field projection, and
obligation reconciliation. Manual review additionally finds live-artifact
claims that the current grounding probes did not detect. The result therefore
shows a narrow improvement over G4.12, where every RoomMind run failed, but not
the required convergence.

## Manual reading of all four matched pairs

### Supply-chain negotiation

Baseline runs for 80 messages, repeatedly reopens settled contract terms, and
ends by changing the inspection protocol it had already confirmed. RoomMind
reaches a locked completion in 22 messages and preserves role ownership. It
does contain a conspicuous `$2.10` versus `84 RMB` inconsistency and treats a
text-rendered signed capacity sheet as completion evidence. RoomMind wins the
pair on structure, but the evidence presentation remains too simulation-like.

### Product launch

Baseline is verbose and publishes unsupported calendar/document actions, yet
it obtains explicit confirmations from the three prerequisite owners and a
coherent phased-launch decision. RoomMind prematurely invokes bounded-close
language, needs a generated player floor prompt to elicit Operations, repeats
the closeout cycle, and ends conditionally after 20 turns with an open launch
decision. Baseline wins.

### Structured interview

Baseline degenerates into repeated, nearly identical panel questions through
the 20-turn limit. RoomMind obtains concrete product, engineering, and people
examples and reaches candidate questions, so it is substantially more usable.
However, Avery's directly addressed roadmap request is displaced by two other
panelists, and panelists claim to have reviewed uploaded or repository evidence
that the transcript does not actually provide. RoomMind wins the pair but
still fails the strict routing boundary.

### Incident response

Baseline reaches containment, rollback, recovery, and handoff, but fabricates
many live operational actions and artifacts without tool evidence. RoomMind
avoids committing most unsafe transitions, yet stalls before containment,
routes Priya's direct question to Marcus through the player, and publishes a
specific archive bucket and SHA-256-manifest claim without visible tool
evidence before closing with four open requirements. Baseline is more complete,
but neither condition is acceptable as a grounded incident simulation.

The manual result is two RoomMind wins and two Baseline wins, with material
defects on both sides. That is not a stable RoomMind advantage and does not
override deterministic gate failures.

## Gate disposition

| Gate | Result | Evidence |
| --- | --- | --- |
| 8/8 frozen dialogues; zero failures/degraded output | PASS | all runs frozen; 0 failures; 0 degraded |
| Fixed revision/model/seed/manifest | PASS | `8768834...`, `ollama/gpt-oss:120b`, seed `20260913` |
| Exact immutable transcript provenance | PASS | all eight hashes independently recomputed |
| Complete six-dimension evaluation | PASS | 48/48; no evaluator errors |
| Required-response fallback is safe and role-local | PARTIAL | run 540 passes, but required response is still lost in runs 542 and 544 |
| Player-addressed targets retain order | FAIL | runs 542 and 544 |
| Direct same-turn NPC responses | FAIL | run 546 |
| Terminal floor and rejected-transition locks | PASS | no G4.10/G4.11 terminal-surface violation |
| No unsupported current-world claim in probe and manual review | FAIL | recorded probes pass, but runs 544 and 546 expose undetected live-artifact claims |
| Every applicable legacy/G4.13 probe passes | FAIL | 3/4 RoomMind runs fail convergence |
| No material routing/repetition regression | FAIL | generated player relays and missing target responses remain |
| Stable advantage over Baseline | FAIL | AI aggregate -0.417; 1/4 AI pair wins; manual split 2-2 |

## Recommendation

Do not start external human review. The next iteration should make the pending
response owner a publication-bound invariant rather than a best-effort slot:
the required target must either publish a validated role-local utterance
immediately or remain the only eligible speaker, without generating a player
relay. The same invariant must cover NPC-to-NPC questions. Add frozen runtime
regressions for runs 542 sequence 15, 544 sequence 38, and 546 sequence 17,
plus explicit detection of text-only claims that a live artifact was uploaded,
reviewed, signed, or archived.

G4.13 improves the clean-pass rate from 0/4 to 1/4 RoomMind runs, but its core
response/terminal/grounding convergence does not hold. **Strict disposition:
FAIL.**
