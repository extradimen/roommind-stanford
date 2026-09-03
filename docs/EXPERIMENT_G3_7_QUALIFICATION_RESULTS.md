# G3.7 Qualification Results

## Disposition

**G3.7 fails the overall simulation-realism qualification gate.** The frozen
batch is technically complete and G3.7 improves information-boundary and
multi-party scores, but all four RoomMind dialogues still terminate as
`stalled`. Manual paired reading confirms repeated reopening of resolved work,
public state diverging from aggregate state, and unsupported current-world
actions. This is exploratory development evidence only and must not be used as
confirmatory evidence or sent to external human review.

## Frozen experiment

- Batch: `b60e22d3-20b7-4818-b85b-027d3a1a4d18`
- Generation: `G3.7`
- Architecture: `g3.7-proposition-grounded-convergent-simulation`
- Source revision: `71422ecb124a20935081dfe78a06fc257da61be4`
- Model: fixed `ollama/gpt-oss:120b`
- Design: four scenarios, one RoomMind and one traditional independent-agent
  Baseline run per scenario, concurrency one, maximum 20 turns
- Research use: exploration/development only

## Engineering and evidence integrity

- 8/8 dialogues completed and were frozen; dialogue failures were zero.
- All eight transcript SHA-256 values were independently recomputed from the
  persisted public messages and matched the archived provenance.
- Independent evaluation initially completed 46/48 dimensions. Only the two
  missing dimensions were retried; the final archive contains 48/48 dimension
  records and 288/288 structurally valid metric records with reasons and
  transcript evidence.
- Evaluation errors were zero and the evaluator used the fixed
  `ollama/gpt-oss:120b` model.
- Seven of eight transcripts passed all applicable deterministic archive
  probes. RoomMind panel interview failed the visible-current-world-action
  probe at sequence 23.

These facts establish reproducibility and technical completeness, not realism.

## Independent six-dimension results

| Dimension | RoomMind | Baseline | Difference |
|---|---:|---:|---:|
| Role and strategic fidelity | 5.25 | 5.00 | +0.25 |
| Information boundaries | 5.75 | 5.25 | +0.50 |
| Temporal coherence | 4.00 | 5.25 | -1.25 |
| Interaction structure | 5.00 | 5.50 | -0.50 |
| Multi-party dynamics | 5.75 | 4.75 | +1.00 |
| Procedural fidelity | 4.25 | 5.50 | -1.25 |

G3.7 has the expected advantage in role-separated information and multi-party
contribution, but the two largest effects are negative: temporal coherence and
procedural fidelity. Four matched pairs are descriptive development evidence,
not a statistical superiority test.

## Convergence and mechanism activation

All four RoomMind sessions stalled:

| Scenario | Turns | Public messages | Stop reason | Final open issues |
|---|---:|---:|---|---:|
| Supply-chain negotiation | 20 | 55 | safety limit | 3 |
| Product launch | 14 | 36 | no task progress | 4 |
| Panel interview | 15 | 40 | no task progress | 4 |
| Incident command | 20 | 58 | safety limit | 7 |

Across RoomMind sessions, quote-confirmation commits, validated-draft use,
clause repair, and silent recovery were all zero. The incident run recorded one
persistent capability boundary and six public-grounding rejections, but did not
produce boundary closure. The intended G3.7 paths therefore existed in code
but did not reliably control the real multi-turn sessions.

## Manual paired-transcript reading

### Supply-chain negotiation

Baseline reached and retained a coherent agreement, although it invented an
attachment and was unrealistically smooth. RoomMind reached the principal
price, delivery, and quality terms, then promoted payment, warranty, liability,
capacity, and document follow-ups into further blockers. A later draft changed
the previously agreed warranty and liability terms and named the wrong
signatory role. The meeting ended at the safety limit. Baseline is more natural
and procedurally coherent in this pair; RoomMind offers stronger role
differentiation but fails closure.

### Product launch

Baseline reached a phased-launch decision and retained it, then continued with
some repetitive follow-up planning. RoomMind produced richer functional
disagreement and a plausible revised budget, but reopened the specialist-budget
issue after the launch and budget had been publicly approved. It then entered
an artifact-and-funding loop and stalled. RoomMind is more multi-party, while
Baseline is more decisive and temporally consistent.

### Panel interview

Baseline is highly repetitive: three interviewers repeatedly ask almost the
same unanswered product, engineering, and leadership questions over 75 public
messages. RoomMind is initially much more natural and differentiated. It
collects and explicitly confirms product, engineering, and leadership evidence
and the candidate closes their questions. The aggregate state nevertheless
leaves all four required fields open, re-asks already answered questions, and
turns the interview into a post-hire KPI/Confluence planning meeting. Sequence
23 also asserts a completed randomized A/B test and downstream outcomes as
current-world evidence without a registered simulated result; later messages
promise email, Slack, calendar, and dashboard actions. RoomMind is better than
Baseline on role differentiation but still fails continuity and closure.

### Incident command

Baseline fabricates extensive live actions and evidence: containment, forensic
capture, rollback metrics, repository storage, status-page publication, and
later restoration steps. It also becomes severely repetitive and contains
impossible timing (a 35-minute action before a 30-minute review).

RoomMind shows a more plausible initial security/SRE tension and clearer role
separation, but still fabricates exact AWS bucket, hash, WAF rule, deployment,
and health-check evidence. It confirms containment and rollback, then asks at
sequence 56 to activate containment again. The public dialogue contains enough
evidence to approve the plan, assign communications, and set the review, while
the aggregate variables remain merely `proposed` or `unknown`; the run reaches
the safety limit with seven open issues. RoomMind is cleaner than the Baseline
in role behavior, but not safely grounded or convergent.

## Root cause established from the debug bundle

1. **Public evidence and task variables are separate, inconsistent ledgers.**
   For example, interview work items for product and leadership evidence are
   `completed`, yet the corresponding completion variables remain `unknown` or
   `proposed`. Incident confirmations have the same split.
2. **The quote confirmation path is effectively inactive.** Explicit public
   confirmations produce zero quote-confirmation commits in every RoomMind
   run, so the closure reducer never sees the dialogue state the audience sees.
3. **Completion-scope protection is insufficient after agreement.** Optional
   documents, dashboards, schedules, and follow-up details continue to enter
   the work graph and consume coordinator focus.
4. **Capability and speech grounding are incomplete in practice.** Some unsafe
   clauses are rejected, but exact invented artifacts and operational evidence
   still reach public dialogue. The interview archive probe demonstrates one
   concrete false negative/semantic misclassification.
5. **The coordinator optimizes focus rotation without first reconciling public
   closure.** It rotates among stale `unknown` fields and eventually declares
   stagnation even when responsible participants have already confirmed them.

## What G3.7 did improve

1. No dialogue-generation failure or degraded LLM fallback occurred.
2. The structured independent evaluation is complete and auditable.
3. Multi-party contributions and information separation improved relative to
   the matched Baseline means.
4. Public grounding rejection and persistent capability-boundary telemetry are
   observable in a real incident run.
5. The RoomMind interview is materially less repetitive and more role-specific
   than its matched Baseline before closure fails.

## Qualification decision and next direction

G3.7 does not pass. The next architecture candidate must not add more prompts or
new scoring dimensions. It should establish one authoritative public-state
reducer that atomically maps quoted, authorized propositions into completion
variables and work-item state; add a closure lock that prevents optional work
from reopening resolved required fields; and require source-typed simulated
results for operational IDs, metrics, attachments, and publication claims.
Only after deterministic replay proves public state, work state, and completion
state agree should another matched real-model batch be run.
