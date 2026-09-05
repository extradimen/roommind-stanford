# G4.5 Obligation-Graph Governance Qualification Results

## Disposition

**G4.5 does not pass the strict simulation-realism qualification, but it is the
strongest directional result in the G4 series so far.** Batch
`e6bac6ed-12eb-4e14-b420-3372e45f3764` completed all eight matched dialogues
under the frozen `ollama/gpt-oss:120b` model with zero dialogue failures and
zero degraded LLM fallbacks. All 48 independent AI dimension ratings completed
after retrying only the missing dimensions of one partial evaluation. All eight
public-transcript SHA-256 values were independently recomputed and matched the
frozen exports.

RoomMind's descriptive six-dimension mean exceeded Baseline by 0.250 and manual
reading favored RoomMind in three scenarios. The candidate is not promoted to
external human review because one RoomMind incident dialogue still loops and
ends with contradictory evidence state, one legacy near-duplicate probe fails,
and the new cross-role-obligation probe produces one false positive because the
export omits the accepted public-intent metadata needed to distinguish a valid
confirmation from a restatement. These are development findings, not
confirmatory evidence of a treatment advantage.

## Frozen protocol

- Generation: `G4.5`
- Architecture: `g4.5-obligation-graph-governance`
- Source revision: `061e17e5b6192ee7b064e088ce4a783bc598cbce`
- Random seed: `20260905`
- Dialogue and evaluator model: `ollama/gpt-oss:120b`
- Dialogue concurrency: one
- Conditions: traditional independent-memory agents and RoomMind
- Dialogues: 8/8 frozen; dialogue failures: zero
- Independent evaluation: 48/48 dimensions complete
- Degraded LLM fallbacks: zero
- Transcript provenance: 8/8 SHA-256 recomputations match
- External human review: not started

## Independent AI evaluation

The six dimensions remain separate endpoints. The mean below is a descriptive
summary only.

| Dimension | Baseline mean | RoomMind mean | Difference |
|---|---:|---:|---:|
| Role and strategic fidelity | 5.25 | 5.00 | -0.25 |
| Information-boundary fidelity | 5.25 | 5.75 | +0.50 |
| Temporal coherence | 4.75 | 5.50 | +0.75 |
| Interaction structure | 5.00 | 5.25 | +0.25 |
| Multi-party dynamics | 5.00 | 5.00 | 0.00 |
| Procedural fidelity | 5.25 | 5.50 | +0.25 |
| Descriptive mean | 5.083 | 5.333 | +0.250 |

Paired descriptive differences were +0.500 for supply-chain negotiation,
-0.334 for product launch, +0.834 for the leadership interview and 0.000 for
incident command. A single AI judge therefore gives mixed rather than uniform
scenario evidence. In particular, it rates the artifact-fabricating, looping
Baseline launch transcript above the shorter RoomMind transcript; manual
reading treats that pair differently. This disagreement must remain visible
and is another reason not to treat the AI mean as a validated primary endpoint.

## Run outcomes and mechanism evidence

| Scenario | Baseline messages | RoomMind messages | RoomMind outcome | AI paired difference |
|---|---:|---:|---|---:|
| Supply-chain negotiation | 79 | 25 | completed in 9 turns | +0.500 |
| Product launch | 78 | 26 | completed in 10 turns | -0.334 |
| Leadership interview | 75 | 28 | completed in 12 turns | +0.834 |
| Incident command | 77 | 51 | conditional safety-timebox close in 20 turns | 0.000 |

The obligation graph was present and reconciled in all four RoomMind runs.
Negotiation, launch and interview ended through `completion_conditions_met`,
with authoritative closure locks and no open obligations. Incident command
ended truthfully as conditional with two open obligations rather than claiming
full completion. The four RoomMind runs recorded 13 obligation transitions and
no reopening; the incident run suppressed three cross-role obligation
duplicates. This is direct evidence that the new mechanism entered the live
generation path.

All model transport errors recovered: RoomMind recorded 22 LLM retry events but
no degraded fallback. The incident run required 11 retries, three safe
fallbacks, 11 silent recoveries, ten public-clause repairs and five public
grounding rejections. The resulting dialogue remained available and its
conditional end state was preserved, but the high repair load correlates with
its poor conversational quality.

## Manual reading of all four matched pairs

### Supply-chain negotiation

RoomMind is substantially shorter and more coherent. It obtains explicit,
authorized confirmations of price, delivery and inspection protocol instead of
Baseline's long post-agreement loop and fabricated emails, spreadsheets and
SOP artifacts. The flagged sequence 11 is not a substantive duplicate: the
Supplier CEO confirms the 84 RMB price and then routes the protocol question to
Emma. The offline probe lacks the accepted-intent marker that caused runtime to
preserve this material confirmation. Remaining weaknesses are an incorrect
reference to the 83 RMB market benchmark as capacity utilization and an ally
offering to circulate documents beyond a procurement analyst's natural role.
This pair favors RoomMind.

### Product-launch decision

Baseline reaches a decision and then continues for many turns, repeatedly
claiming dashboards, emails, uploads and calendar actions that have no tool
evidence. RoomMind reaches a bounded phased-pilot decision quickly, keeps the
budget and safeguards visible and avoids unsupported completed artifacts. It
does, however, call future safeguards “in place” before their scheduled
completion and leaves a `[date + 7 days]` placeholder in public speech. Manual
reading modestly favors RoomMind despite the AI judge's lower score.

### Leadership interview

Baseline permits a panel pile-on, repeats nearly identical questions and later
contradicts the candidate's previously settled experiment size. RoomMind routes
questions sequentially, obtains distinct product, engineering and leadership
evidence, then gives the candidate space to ask questions. Some final
confirmation language is redundant and one director comments on completion
authority outside their remit, but the interaction is far more natural and
temporally coherent. This pair clearly favors RoomMind.

### Incident command

Both conditions are poor. Baseline is longer and fabricates rollback timing,
integrity checks, status-page publication and placeholder metrics. RoomMind
blocks several unsupported terminal claims and preserves a conditional rather
than false-complete outcome, but it still invents conflicting live metrics,
claims signed logs were shared and verified without a registered simulated tool
result, introduces an unregistered `Jordan Patel`, repeatedly waits for that
non-participant, and later contradicts whether Security received the artifacts.
Sequence 16 repeats the earlier containment-status statement and correctly
fails the legacy near-duplicate probe. This pair is mixed; governance safety is
better, while conversational realism remains inadequate.

## Integrity and qualification gates

| Gate | Result | Evidence |
|---|---|---|
| Frozen source, model, seed and transcripts | Pass | manifest verified; 8/8 hashes recomputed |
| Engineering completion | Pass | 8/8 dialogues, 48/48 dimensions, zero dialogue failures |
| No degraded LLM output | Pass | zero degraded fallbacks; retries recovered |
| Obligation graph and open-set reconciliation | Pass | all four RoomMind runs reconcile |
| Completed runs require satisfied obligations | Pass | negotiation, launch and interview close with zero open obligations |
| Authorized obligation targets | Pass | no incapable obligation target |
| Truthful bounded close | Pass | incident retains two open obligations as conditional |
| Cross-role obligation repetition | **Measurement fail** | sequence 11 is a valid accepted confirmation, but export lacks intent metadata |
| Legacy same-speaker repetition | **Fail** | incident sequence 16 repeats containment status |
| Consistent paired realism progression | **Fail** | one AI pair regresses and one ties; manual incident pair remains inadequate |
| Manual role, evidence and temporal realism | **Fail** | incident contains contradictory and unsupported current-world claims |

## Successor requirement

The next iteration should be a narrow G4.5.1/G4.6 correction rather than a new
broad prompt architecture:

1. export the validated public intent, material-transition marker and simulated
   tool provenance used at runtime, so offline probes can distinguish accepted
   confirmations from paraphrases;
2. apply the same proposition-level duplicate boundary to safe-fallback and
   repaired clauses, including same-speaker repeats;
3. require a registered simulated tool result before public claims that logs,
   hashes, uploads, publications or live metrics have been produced or verified;
4. prohibit in-session blocking ownership from being transferred to an
   unregistered person and route the obligation back to an authorized present
   participant;
5. keep “planned”, “in progress” and “verified complete” evidence states
   distinct, and prevent placeholders from surviving into public speech.

G4.5 should be retained as exploratory evidence. It demonstrates that the
obligation graph materially improves closure and often improves naturalness,
but the incident-command stress case shows that repair-path output is not yet
governed by the same evidence and repetition invariants as ordinary output.
