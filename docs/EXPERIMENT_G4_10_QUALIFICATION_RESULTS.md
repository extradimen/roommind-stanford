# G4.10 Qualification Results

## Disposition

**G4.10 fails strict qualification and must not advance to external human
review.**

The fixed staging run completed 8/8 dialogues, froze all transcript hashes,
and completed 48/48 independent evaluation dimensions with zero dialogue
failures and zero degraded LLM output. The three new G4.10 mechanisms work at
their registered boundaries: no conditional confirmation was committed, no
multi-addressee response was lost across a deterministic player handoff, and
no NPC spoke after a terminal confirmation in the same autonomous turn.

Those narrow passes did not translate into better dialogue. RoomMind loses to
Baseline on every AI-evaluated dimension, three RoomMind runs stall on an
NPC-to-NPC question routed through the player, the interview reopens after its
evidence is declared complete and reaches the 20-turn safety limit, and only
one of four RoomMind runs is externally judged complete. Manual reading finds
one RoomMind win and three Baseline wins.

## Frozen protocol

- Batch: `6394089e-662e-422b-9b82-9bea10264650`
- Source revision: `5e4df7aaf004b14f088f2be7592013ab0dc51aaf`
- Architecture: `g4.10-prerequisite-and-terminal-floor-governance`
- Provider/model: `ollama/gpt-oss:120b` for generation and evaluation
- Design: four matched scenarios, Baseline and RoomMind, seed `20260910`
- Dialogue result: 8/8 frozen, zero dialogue failures, zero degraded fallbacks
- Evaluation result: 48/48 dimensions after missing-dimension-only retries
- Evidence use: development-only exploration, not confirmatory evidence

An obsolete orphan process initially exposed G4.9 runtime constants after the
Git deployment. Batch `5b9a4b2e-5a71-450f-84c8-24382d648291` was cancelled
with 0/8 dialogues completed. The orphan was terminated, systemd took over
port 8910, and the formal batch was created only after the live runtime and
manifest both reported G4.10. The cancelled batch is audit history only.

The final API was ready, the deployed revision and manifest matched, the only
observed provider/model pair was `ollama/gpt-oss:120b`, and all eight canonical
transcript SHA-256 values independently recomputed exactly.

## Independent AI evaluation

| Dimension | Baseline mean (n=4) | RoomMind mean (n=4) | Difference |
| --- | ---: | ---: | ---: |
| Role and strategy | 6.00 | 5.25 | -0.75 |
| Epistemic boundaries | 6.00 | 5.50 | -0.50 |
| Temporal coherence | 6.00 | 4.50 | -1.50 |
| Interaction structure | 6.00 | 4.50 | -1.50 |
| Multi-party dynamics | 5.25 | 4.25 | -1.00 |
| Procedural fidelity | 5.75 | 3.75 | -2.00 |

The unweighted descriptive mean is 5.833 for Baseline and 4.625 for
RoomMind, a difference of -1.208. The matched scenario differences are -1.000,
-1.333, -2.000, and -0.500 respectively. This is exploratory evidence, but it
is both directionally uniform and materially adverse.

The first evaluation pass was structurally partial because the evaluator
occasionally returned null metric fields. Missing-dimension-only retries moved
the result from 3/8 complete, to 7/8, and finally 8/8. Previously completed
dimension results were retained and every transcript hash remained unchanged.

## Run outcomes and telemetry

| Run | Condition | Messages | Outcome / stop | Notable telemetry |
| ---: | --- | ---: | --- | --- |
| 515 | Baseline | 78 | externally complete at 20 turns | no retries or fallbacks; repetitive late contract loop |
| 516 | RoomMind | 24 | internal completed / externally premature | 2 silent recoveries; cross-role probe failure |
| 517 | Baseline | 52 | externally complete | no retries or fallbacks |
| 518 | RoomMind | 18 | conditional / bounded close | 2 retries, 7 silent recoveries, near-duplicate and cross-role failures |
| 519 | Baseline | 27 | externally complete | 1 retry, 1 safe fallback |
| 520 | RoomMind | 46 | conditional / 20-turn safety close | 2 retries, 2 safe and 4 silent recoveries; unsupported current-world player claim |
| 521 | Baseline | 29 | externally complete / bounded unresolved close | 1 retry, 2 safe fallbacks, 1 grounding rejection |
| 522 | RoomMind | 22 | conditional / bounded close | 6 retries, 7 silent recoveries, 4 grounding rejections; cross-role failure |

Across the batch there were 12 LLM retries, five safe fallbacks, and twenty
silent recoveries, all without degraded model output. The recovery mechanisms
kept the batch alive, but the concentration in RoomMind launch and incident
runs corresponds to visible stalls rather than invisible robustness alone.

## Integrity probes

All three narrow G4.10 target diagnostics are clean in every RoomMind run:

- `g410_conditional_confirmations_not_committed` passes;
- `g410_terminal_confirmation_locks_floor` passes;
- `g49_multi_addressee_responses_preserved` passes under the corrected visible
  handoff boundary.

Strict applicable-probe completeness still fails:

- run 518 fails same-speaker near-duplicate suppression;
- run 520 fails the current-world action/tool-evidence boundary because the
  player claims to have assembled a cross-functional board and collected live
  records without a simulated tool result;
- runs 516, 518, and 522 are flagged by the legacy G4.3 cross-role ownership
  probe when the player inserts the deterministic `Name, the floor is yours`
  handoff. Manual inspection shows these three flags are probe-contract false
  positives—the visible handoff names the correct target and that target later
  responds—but they expose that the legacy probe was not updated to the G4.10
  handoff contract. Even excluding those false positives, applicable probe
  completeness fails on runs 518 and 520.

## Manual reading of all matched pairs

### Supply-chain negotiation

Baseline becomes an implausible 78-message contract loop, repeatedly promising
the same next-day draft and eventually claiming unsupported attachments.
RoomMind is substantially shorter and its visible handoff correctly reaches
the Supplier CEO. It nevertheless lets the Procurement Ally invent the
inspection-plan detail and 120,000-unit forecast, and internally closes after
the Supplier confirms price even though the quality and legal work is not
fully resolved. **RoomMind is more natural in this pair, but fails procedural
completion.**

### Product launch

Baseline is verbose and introduces invented commercial and staffing numbers,
but it preserves the conditional budget restriction and reaches a coherent
phased-launch decision. RoomMind already receives an operational-readiness
confirmation at sequence 8, then asks for it again, routes Sales' question
through two player handoffs, never lets Operations answer, and closes with
three open issues. **Baseline wins the pair.**

### Structured interview

Baseline elicits product, engineering, and leadership evidence, gives each
panel role a relevant answer in candidate questions, and closes in 27
messages. RoomMind declares all evidence and candidate questions complete by
sequence 23, then reopens the interview, asks for external reports, begins a
second product example, repeats engineering-ownership questions, and stops at
46 messages only because of the 20-turn safety limit. Its internal obligation
graph still shows candidate questions pending despite an accepted public
event. **Baseline wins decisively.**

### Incident response

Baseline has unsupported live action claims, but its evidence-first ordering
and bounded unresolved close are comparatively coherent. RoomMind publicly
approves recovery before evidence storage is confirmed; the ledger correctly
refuses to treat that as final, but later speech still says the plan is
approved and execution starts. A Security-to-SRE verification question is
routed through the player, SRE never responds, and the run closes with four
open issues. **Baseline wins; neither output is safe for confirmatory use.**

Overall manual judgment is one RoomMind win and three Baseline wins. The main
failure is no longer conditional ledger commitment itself. It is the mismatch
between deterministic state governance and public conversational control:
rejected or already-resolved state still produces misleading speech, repeated
questions, handoff stalls, and reopened phases.

## Gate disposition

| Gate | Result | Evidence |
| --- | --- | --- |
| Eight frozen dialogues; zero failures/degraded output | PASS | 8/8, 0 failures, 0 degraded |
| Exact immutable transcript provenance | PASS | all eight hashes independently recomputed |
| Complete six-dimension evaluation | PASS | 48/48 via missing-only retry; hashes retained |
| Fixed revision, model, seed, and manifest | PASS | revision `5e4df7a...`, fixed model, seed `20260910` |
| Conditional acceptance never committed | PASS | no G4.10 conditional-acceptance diagnostics |
| Multi-addressee set survives visible handoff | PASS | no G4.9 response-set violations |
| No same-turn speech after terminal confirmation | PASS | no G4.10 post-terminal diagnostics |
| Every applicable legacy/G4.10 probe passes | FAIL | runs 518 and 520 have substantive failures; legacy handoff probe also needs alignment |
| Internally completed runs are externally valid | FAIL | run 516 is internally completed but externally premature |
| No phase reopening or material repetition | FAIL | runs 518 and 520 visibly reopen or repeat resolved work |
| Stable naturalness advantage over Baseline | FAIL | AI loses 6/6 dimensions; manual reading loses 3/4 pairs |

## Narrow next-step recommendation

Do not add more confirmation vocabulary. The next candidate should align
conversation scheduling with the already authoritative state:

1. represent an NPC-to-NPC question as a pending response edge and schedule the
   named NPC directly on the next autonomous step; do not make the player utter
   an administrative handoff;
2. once a field, phase, or candidate-question segment is satisfied, suppress
   semantically equivalent prompts and reject new focus on it unless a new
   player request or contradictory public evidence explicitly reopens it;
3. if ledger validation downgrades an approval, regenerate the public clause as
   conditional or blocked instead of allowing surface speech such as “I
   approve” or “the plan is approved” to survive;
4. reconcile accepted field events, the obligation graph, and completion state
   atomically so the interview cannot show an accepted completion event while
   retaining the same obligation as pending;
5. update the legacy cross-role probe to recognize the current deterministic
   handoff contract, while keeping the stricter direct-scheduling replacement
   as the desired runtime behavior.

G4.10 validates its three narrow commit-boundary fixes, but it demonstrates
that state correctness without floor and focus correctness can make dialogue
less natural. **Do not start external human review.**
