# G3.6 Qualification Results

## Disposition

**G3.6 fails the overall simulation-realism qualification gate.** The
generation is technically stable and materially improves visible action
grounding in the incident scenario, but all four RoomMind dialogues still
terminate as `stalled`. The result is frozen development evidence and must not
be treated as confirmatory evidence or sent to external human review.

## Frozen experiment

- Batch: `8d1ff739-be70-4e45-8feb-3826f37061bb`
- Generation: `G3.6`
- Architecture: `g3.6-quote-grounded-capability-aware-simulation`
- Source revision: `29def4cd35798b5e45cebc2d3ba418527d01178f`
- Model: fixed `ollama/gpt-oss:120b`
- Design: four scenarios, one RoomMind and one traditional independent-agent
  Baseline run per scenario, concurrency one, maximum 20 turns
- Research use: exploration/development only

## Engineering and evidence integrity

- 8/8 dialogues completed and were frozen.
- Dialogue failures: 0.
- Degraded LLM fallbacks: 0.
- All eight transcript hashes were independently recomputed and matched.
- All applicable RoomMind deterministic integrity probes passed.
- Independent evaluation initially completed 47/48 dimensions. Only the one
  missing dimension was retried; the other 47 were retained.
- Final evaluation contains 48/48 dimension scores and 288/288 structurally
  complete metric records with nonempty reasons and transcript evidence.

This establishes engineering stability and evaluation completeness, not
simulation realism.

## Independent six-dimension results

| Dimension | RoomMind | Baseline | Difference |
|---|---:|---:|---:|
| Role and strategic fidelity | 5.50 | 5.50 | 0.00 |
| Information boundaries | 5.00 | 4.75 | +0.25 |
| Temporal coherence | 4.25 | 4.75 | -0.50 |
| Interaction structure | 5.00 | 5.25 | -0.25 |
| Multi-party dynamics | 5.00 | 5.00 | 0.00 |
| Procedural fidelity | 5.00 | 4.50 | +0.50 |

Unlike G3.5, G3.6 is no longer lower on every dimension. The result is mixed:
two small advantages, two ties, and two disadvantages. With only four matched
pairs, these descriptive means cannot support a general superiority claim.

## Convergence and mechanism use

All four RoomMind runs stalled:

| Scenario | Turns | Stop reason | Capability-boundary turns |
|---|---:|---|---:|
| Supply-chain negotiation | 20 | safety limit | 0 |
| Product launch | 13 | no task progress | 0 |
| Panel interview | 20 | safety limit | 0 |
| Incident command | 8 | no task progress | 6 |

Across RoomMind runs, quote-confirmation commits, validated public-draft use,
clause repair, and silent recovery were all zero. The new capability-boundary
path activated only in incident command. Therefore the batch exercised the
new action boundary, but did not demonstrate that the confirmation and local
repair paths improve ordinary multi-turn convergence.

## Manual paired-transcript reading

### Supply-chain negotiation

Baseline reached an explicit agreement more directly but fabricated email
delivery, attachments, document receipt, and review. RoomMind avoided most of
those completed external-action claims and kept the PDF as future follow-up,
but introduced a secondary liability negotiation, repeatedly reopened matters
that had already been stated as confirmed, and reached the 20-turn limit.
RoomMind was epistemically safer but less efficient and less naturally closed.

The RoomMind transcript also contains `Sample log entries attached`, which was
not flagged by the G3.6 archive probe. This is a concrete attachment-detector
false negative.

### Product launch

Baseline completed a concise phased-launch decision, although it was overly
smooth and asserted readiness evidence generously. RoomMind produced richer
functional concerns but contradicted itself: budget was confirmed and later
described as pending, operational readiness was confirmed and reopened, and a
new decision call became an unnecessary final gate. One player utterance also
contained a visibly corrupted copied fragment (`ge once we scale...`). The
meeting stalled despite having publicly stated all principal confirmations.

### Panel interview

Both conditions were repetitive. Baseline was particularly severe, asking
almost the same multi-part questions across many turns. RoomMind was more
role-differentiated and produced a more plausible evidence sequence, matching
the independent evaluator's relative preference. It nevertheless repeated
already answered questions, failed to close after all three evidence areas had
been confirmed, and introduced conflicting technical/result details (including
different latency and conversion figures and a technically dubious
`client-side caching layer using Redis`). RoomMind was better than its matched
Baseline here, but not qualification-quality.

### Incident command

Baseline repeatedly invented completed log capture, snapshots, rollback,
restoration, hashes, evidence storage, and customer publication; it also leaked
an internal JSON fragment into public dialogue. RoomMind was substantially
safer and more realistic in recognizing that verification results were not
available in the text session and deferring them. This is the clearest G3.6
improvement.

However, RoomMind still publicly stated `All traffic to the affected service
has been blocked` without a registered simulated-tool result. The current
scanner does not recognize this passive completed-action form. After entering
the capability boundary, the coordinator also returned to requesting firewall
and load-balancer log excerpts for several turns instead of closing
conditionally, so the session still stalled.

## What G3.6 actually solved

1. The new visible-current-world-action probe identifies many fabricated
   operational claims that older ledger-shape checks missed.
2. RoomMind incident dialogue avoids most of the extensive live-operation
   fabrication produced by Baseline.
3. Capability-boundary state appears in real multi-turn telemetry and can keep
   unavailable verification in a pending state.
4. The complete run is technically stable and independently auditable.

## Remaining causal failures

1. **Speech grammar coverage is incomplete.** Passive completion, terse
   attachment statements, and semantic paraphrases can bypass phrase-driven
   detection.
2. **Capability boundary is advisory rather than terminal.** Later player and
   coordinator turns can ask for the unavailable evidence again.
3. **Public confirmation and aggregate completion still diverge.** Explicit
   acceptance in dialogue did not produce any quote-confirmation commits in
   this batch.
4. **Issue creation remains too permissive.** Side issues and follow-up
   documents can become new blockers after the primary decision is already
   defensible.
5. **The shared AI player emits visible governance templates and can copy
   malformed fragments.** This reduces naturalness and may affect both
   conditions, while RoomMind is more exposed because it tends to run longer.
6. **The system lacks a deterministic closure reducer.** When configured
   fields are publicly confirmed or honestly deferred, the meeting can still
   continue until stagnation or the safety limit.

## G3.7 direction

Do not widen the experiment. A later candidate should:

1. replace phrase-only action detection with normalized clause propositions
   covering active, passive, perfect, terse, and paraphrased completion;
2. persist capability-boundary resolution so unavailable evidence cannot be
   re-requested unless a new registered tool result appears;
3. derive field confirmation from authoritative quoted propositions rather
   than optional evaluator labels or fragile surface matching;
4. add a deterministic closure reducer that ends completed, conditional,
   deferred, or failed meetings once all required fields are resolved;
5. prevent incidental post-decision issues from becoming required blockers;
6. remove governance-template language from the shared public player and add
   direct-question sanitation;
7. add regression probes for the exact false negatives and contradictions
   observed in this frozen batch before another real-model run.

