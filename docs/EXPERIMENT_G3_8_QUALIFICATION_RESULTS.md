# G3.8 Qualification Results

## Disposition

**G3.8 fails the end-to-end simulation-realism qualification gate.** The
authoritative ledger and work reconciliation are present and the experiment is
technically complete, but none of the four RoomMind dialogues reaches the
closure lock. Manual paired reading shows that accepted public ledger events
are not sufficient to satisfy multi-party confirmation policies, the shared
comparison player does not reliably voice its own acceptance, named-owner and
schedule decisions are not normalized, and the coordinator therefore continues
past publicly plausible closure. This remains exploratory development evidence
and must not be used as confirmatory evidence or sent to external human review.

## Frozen experiment

- Batch: `5086c86f-6a49-4e4c-9ca0-ff6dc4222470`
- Generation: `G3.8`
- Architecture: `g3.8-authoritative-state-reducer-closure-lock`
- Source revision: `64cd7668e988d7dac720d1c0b396d40cb2838c0f`
- Manifest SHA-256:
  `23b34b1a5f6769394871220b2e1821592a25c6b7ec1b9df577a5e11f0b4d9bf9`
- Model: fixed `ollama/gpt-oss:120b`
- Design: four scenarios, one RoomMind and one traditional independent-agent
  Baseline run per scenario, concurrency one, maximum 20 turns
- Research use: exploration/development only

## Engineering and evidence integrity

- 8/8 dialogues were generated and frozen; dialogue failures were zero.
- Independent evaluation reached `evaluation_completed` with all 48 dimension
  records present. The first pass was partial in three cells; only missing
  dimensions were retried.
- All run-level evaluation error maps are empty after the targeted retry.
- The fixed generation/evaluation model label is `ollama/gpt-oss:120b`.
- Persisted transcript provenance contains a SHA-256 for every run and all
  applicable archive probes report true.
- The G3.8 closure-lock probe is vacuous for these RoomMind runs: it checks the
  consistency of a lock if present, but all four runs have no lock. Probe
  success therefore does not establish convergence.
- The first HTTP transfer of the large debug bundle ended with a truncated JSON
  body. A retried transfer produced a complete 7,278,649-byte JSON artifact.
  This is an export transport weakness, not a dialogue-generation failure.

## Independent six-dimension results

| Dimension | RoomMind | Baseline | Difference |
|---|---:|---:|---:|
| Role and strategic fidelity | 5.50 | 5.75 | -0.25 |
| Information boundaries | 5.75 | 5.75 | 0.00 |
| Temporal coherence | 5.50 | 6.00 | -0.50 |
| Interaction structure | 5.75 | 5.25 | +0.50 |
| Multi-party dynamics | 5.50 | 5.50 | 0.00 |
| Procedural fidelity | 5.75 | 5.50 | +0.25 |
| Mean across six dimensions | 5.625 | 5.625 | 0.000 |

The aggregate AI score is exactly tied. With only four matched pairs this is
descriptive development evidence, not a statistical superiority result. Manual
reading also exposes evaluator false positives: it treats invented capacity
data, emails, dashboards, snapshot IDs, live rollback actions, and impossible
current-world state as grounded merely because the dialogue repeats them.

## Convergence and mechanism activation

| Scenario | RoomMind turns | Stop reason | Open issues | Quote commits | Closure lock |
|---|---:|---|---:|---:|---|
| Supply-chain negotiation | 16 | no task progress | 4 | 0 | absent |
| Product launch | 20 | safety limit | 1 | 0 | absent |
| Panel interview | 20 | safety limit | 1 | 0 | absent |
| Incident command | 17 | no task progress | 3 | 0 | absent |

All four RoomMind sessions end as `stalled`. G3.8 does reconcile two derived
work items in both the product-launch and incident runs, so the new work-item
mechanism is active. It does not solve the remaining confirmation gap:

- negotiation ledger entities for price, delivery, and quality are `accepted`,
  but aggregate variables remain `proposed` because only the counterpart side
  is recorded;
- product launch confirms three prerequisite fields, while
  `launch_decision=phased_launch` remains `proposed` with only CFO acceptance;
- interview confirms the three evidence fields, while
  `candidate_questions_complete=true` remains `proposed` with only VP Product;
- incident command confirms the recovery plan, but executable containment is
  correctly withheld, next-review scheduling is `disputed`, and the named
  communications owner remains `unknown` despite clear public dialogue.

## Manual paired-transcript reading

### Supply-chain negotiation

Baseline reaches a coherent 84 RMB / 30-day / quality-protocol package in nine
turns, although it invents production capacity and future document delivery and
the procurement analyst repeatedly advocates paying more than the negotiated
price. RoomMind initially has credible role separation and uses capacity and
quality evidence, but publicly invented metrics are accepted as if supplied.
After all three principal terms are spoken as confirmed, the shared player asks
for legal contacts and the quality director introduces a new finance-clearance
gate outside her role. The run ends waiting for a clearance that the original
contract conditions did not require. Baseline is more convergent; RoomMind is
not more natural overall in this pair.

### Product launch

Both conditions are verbose and continue after a plausible phased-launch
decision. Baseline invents a budget and calendar actions but reaches a joint
decision. RoomMind develops more differentiated operational and financial
concerns, then publicly records CFO approval and the player records joint
approval. It nevertheless fails to capture the player's acceptance of
`phased_launch`, reopens the already-addressed specialist gap, and spends the
last turns requesting the same mitigation outline. The AI dimension means tie,
but manual review favors neither transcript as a clean realistic close.

### Panel interview

RoomMind is clearly better than Baseline in the first two-thirds of this pair.
Baseline's three panelists ask overlapping questions, and the Engineering
Director even answers a candidate question in the candidate's voice. RoomMind
keeps stronger functional roles, obtains specific product, engineering, and
leadership examples, and explicitly marks each evidence category. However, the
candidate fabricates an ADR and a manager quotation on demand; panel members
invent an internal roadmap, Grafana status, current latency, and recruiting
timeline. The candidate and VP both publicly close candidate questions, but the
state remains proposed, so the interview continues for six unnecessary turns.
RoomMind wins this matched pair while still failing its own closure gate.

### Incident command

Baseline is highly unrealistic: it simulates live containment, forensic
snapshots, rollback, immutable timestamps, status-page publication, and service
restoration without tools, while repeatedly asking for milestones already
reported. RoomMind initially improves epistemic caution by holding remediation
until evidence lock-down, and it correctly refuses to confirm executable
containment in aggregate state. It still lets speakers invent health checks,
snapshot IDs, write-block state, and an attached log excerpt. Natural owner and
review decisions are not normalized, and after authorizing recovery it creates
another evidence check and stops before Communications can answer. RoomMind is
safer than Baseline but still neither grounded nor convergent.

## Root cause established from the frozen artifacts

1. **The remaining split is confirmation-policy completion, not ledger
   creation.** G3.8 successfully creates accepted field entities, but policies
   requiring the player plus another role remain incomplete because the shared
   player summarizes or proceeds without an atomic `I confirm ...` utterance.
2. **The reducer recognizes narrower language than real participants use.**
   Phrases such as “with all ... confirmed, I propose we formalize”, “record our
   joint approval”, “I have no further questions”, “you are assigned as owner”,
   and imperative scheduling are semantically decisive but are not safely
   projected into their configured fields.
3. **String assignment lacks identity binding.** A communications lead saying
   “I confirm I’m the owner” cannot populate a nonempty owner string because the
   projector does not bind the authorized speaker to their registered display
   name.
4. **The shared player policy and RoomMind coordinator cannot close each
   other's half of a joint policy.** The comparison player intentionally cannot
   inspect RoomMind private state, while the coordinator only routes NPC
   speakers. If the player does not explicitly accept a public term, RoomMind
   can only ask the already-confirmed NPC again.
5. **Speech-level grounding remains weaker than state grounding.** Invalid live
   actions may be rejected from authoritative state while still appearing in
   the visible transcript, which harms realism and misleads the AI evaluator.
6. **The evaluator over-credits self-consistent fabrication.** Its explanations
   repeatedly call invented values “grounded” because they were stated earlier.
   Six-dimension AI scores must therefore remain secondary to deterministic
   probes and blinded/manual transcript reading.

## Qualification decision and G3.9 direction

G3.8 does not pass and must not enter external human review. G3.9 should remain
small and evidence-driven:

1. derive an explicit public-confirmation checklist for the shared player from
   the public task specification and transcript only, preserving comparison
   fairness;
2. atomically normalize authoritative summary approval, no-further-questions,
   named self-assignment, and authorized imperative scheduling without accepting
   questions, conditions, negation, or unsupported execution;
3. bind an authorized assignee's first-person ownership to the registered
   character identity;
4. make the integrity gate fail when a configured RoomMind task ends stalled,
   lacks a required closure lock, or has accepted ledger fields that disagree
   with aggregate variables;
5. strengthen visible-speech filtering for unsupported current-world artifacts
   and operations separately from retrospective evidence.

Only deterministic replay and a database-backed local matched run should be
attempted before another staging generation is frozen.
