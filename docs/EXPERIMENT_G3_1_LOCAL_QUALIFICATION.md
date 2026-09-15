# G3.1 canonical-ledger local qualification

## Purpose

G3.1 is a local exploratory correction to the G3 prototype. It addresses
deterministic counterexamples found before G3 was pushed or deployed. Earlier
G1-G2.3 evidence and the local G3 prequalification record remain unchanged.

- Generation: `G3.1`
- Architecture: `g3.1-canonical-ledger-open-scene-simulation`
- Evidence use: engineering exploration only
- Deployment: prohibited until local gates pass

## Treatment changes from G3

1. Player authority is derived from each configured field's player proposal,
   confirmation, and execution permissions.
2. Configured fields become canonical ledger entity IDs. Unconfigured material
   work uses a shared `work:` identity across action, artifact, and verification,
   with deterministic alias matching.
3. Lifecycle events retain actors by transition, allowing submission,
   verification, and acceptance roles to remain auditable.
4. Events that regress the simulation clock are rejected before they mutate
   canonical entities.
5. Material actions require a registered executable capability. Artifact and
   verification capabilities can be inferred from registered authority IDs.
6. Structured interviews use a retrospective evidence mode. Past-experience
   claims do not complete current simulated work, while newly invented URLs and
   hashes remain prohibited.
7. Retrospective mode is enabled by scenario policy rather than trusted from
   model output, so a live-operation agent cannot self-select the weaker rule.
8. A `submitted` ledger transition cannot be rendered publicly as “complete”;
   the copular completion-claim detector now handles both “is complete” and
   “has been completed” forms.
9. Cross-kind entities retain all observed kinds for support checks. A later
   verification no longer erases the fact that the same canonical entity was
   originally executed as an action.
10. Material lifecycle monotonicity now covers early states too: an already
    submitted, verified, or accepted item cannot regress to proposed,
    committed, or in-progress wording. A seeded 1,000-transition randomized
    check passed without any ranked lifecycle regression.
11. Public speech is checked against explicit `protected_secrets`, including
    distinctive phrases and numeric business terms. A real local-model turn
    exposed the supplier's private 82 RMB reservation price; the new filter
    rejected the same deliberately injected leak and returned a safe fallback.
12. The renderer now rejects verbatim public-draft echoes. A subsequent real
    turn exposed the internal instruction “Ask for the commercial conditions…”
    as dialogue, providing the counterexample for this rule.
13. `fallback_actions.default` is now treated only as an internal action
    instruction. It can no longer be copied into the transcript after model
    retries fail; only an explicitly authored `public_reply` can be emitted.
14. A structured public intent is re-grounded against the actual spoken quote
    at the commit boundary. A request such as “please provide the pricing
    structure” cannot mutate the ledger as though the requester submitted it.
15. The untrusted state evaluator now has a deterministic semantic boundary in
    addition to exact-quote matching. Field updates require a field anchor and
    the typed value in the cited quote; terminal outcomes require explicit
    closure language; action commitments require actor-owned commitment words.
16. Canonical identity matching normalizes ordinary singular/plural variants.
    `commitment` and `commitments` therefore cannot create artificial progress
    by splitting one public issue into two entities.
17. Once one actor has already recorded a non-material transition on a
    canonical entity, restating the same transition is non-progress and is not
    appended again. Another participant's first independent proposal remains
    auditable, preserving multi-party provenance without ledger spam.
18. Canonical field events now carry their explicit typed public value.
    `verified` or `accepted` cannot advance without a value grounded in the
    spoken quote, and a conflicting value cannot overwrite an accepted field.
    When the configured confirmation policy is satisfied by ledger actors, the
    value is projected deterministically into `task_state.variables`; the LLM
    evaluator is no longer the authority for an already accepted value.

## Results so far

The deterministic suites pass for player authority, cross-kind lifecycle
progression, reworded-subject canonicalization, field lifecycle monotonicity,
unregistered execution rejection, invalid-clock quarantine, and retrospective
scope policy. Application import, bytecode compilation, and diff checks also
pass.

The G3.1 evidence rule was replayed over the frozen G1.1 GPT-OSS 120B artifact
without regenerating any dialogue (`24` runs; `1,350` messages). Flags fell
from `34` under the first G3 rule to `31`: three legitimate past attachment or
email narratives in the structured interview were no longer classified as
live external actions. A fourth interview utterance said “see attached PDF”
in the current exchange and remains correctly rejected. All eight invented
interview URLs also remained flagged.
The remaining live-scene counts are `10` supply-chain, `6` launch-decision,
and `6` incident-command unsupported external artifact claims; RoomMind
accounts for `16` of those `22`, so this is an architecture problem rather
than a Baseline-only defect.

A fresh matched pair was run with local `qwen3.5:0.8b` as an adversarial
engineering stress model. It is not a realism benchmark and is not comparable
to prior GPT-OSS 120B generations. Baseline ran to its 10-turn safety limit
(`40` messages) and contained `22` exact-repetition excess messages. The final
RoomMind diagnostic stopped truthfully after four turns (`8` messages) with
`no_task_progress` / `stalled`. Its configured fields remained `unknown`, no
terminal agreement was manufactured, and the protected 82 RMB reservation
price was absent. The small model's dialogue was repetitive and commercially
weak in both conditions, so these counts establish failure containment only,
not RoomMind's comparative naturalness.

The real-model sequence produced three useful counterexamples before the final
contained run. First, a protected reservation value escaped; second, an
internal fallback instruction was spoken verbatim; third, the state evaluator
copied `delivery_days=30`, `quality_protocol=true`, and a completed outcome from
schema/context despite the quote saying the deal could not yet be finalized.
Each contaminated RoomMind run was stopped and retained locally, the defect was
reproduced in a deterministic regression test, and only the RoomMind side was
regenerated. On the final run the same first-turn clarification left all three
variables unknown, the public ledger empty, work items empty, and outcome open.
This before/after control demonstrates that deterministic grounding—not a
different model sample—removed the false state.

An additional deterministic end-to-end integration run has completed against
an isolated SQLite database with a scripted LLM adapter. Both Baseline and
RoomMind reached `dialogue_completed` without errors. Baseline stopped at its
10-turn safety limit; RoomMind stopped after four turns with `no_task_progress`,
and its 12 spoken intents were committed with a monotonic `(turn, tick)` clock
into two canonical proposal entities with no rejections. This qualifies wiring,
persistence, export, stopping, and ledger-event integration, but is explicitly
not evidence of dialogue naturalness or comparative realism.

The full (non-public) RoomMind export from that integration run passed every
registered integrity probe, including independent memory partitions, bounded
coordination, public grounding, ledger provenance, monotonic simulation clock,
valid lifecycle sequencing, and completion reconciliation. Baseline correctly
does not pass RoomMind-architecture probes; those checks are treatment-integrity
checks rather than comparative outcome metrics.

A second scripted end-to-end run forced the shared AI player to accept
`unit_price` on turn 1 and then propose reopening it on later turns. Commit-time
state validation retained exactly one `field:unit_price` event and kept its
lifecycle `accepted`; the later regressive intents did not mutate the ledger.
The player's generated words were not regenerated, preserving the shared
public-only player policy while making RoomMind's acceptance state authoritative.

The final fixed-revision qualification used source commit
`4c02922428952f57f26a9f078b00020fb0aa4f7e`. Both matched conditions reached
`dialogue_completed` without technical failure. Baseline ran 10 turns / 40
messages. RoomMind stopped at four turns / 12 messages with
`no_task_progress` and `stalled`. The RoomMind transcript SHA-256 is
`484243d92aa07f93e44f05b315fd25c3e9ba3485c90a862f8b4b58386647fe7f`.
Its ledger contained two canonical entities and four events: one value-free
player field proposal plus one first proposal from each of the three NPCs. It
contained no value-free accepted field, no repeated event by the same actor,
and all three configured variables remained unknown rather than being falsely
completed.

The full internal export passed every applicable deterministic integrity probe:
public transcript structure, registered speakers, comparison model lock,
independent RoomMind memory partitions, coordination history and focus bounds,
public evidence grounding, ledger provenance, material inline evidence,
monotonic clock, valid entity lifecycle, and completion reconciliation. These
are implementation-integrity gates, not realism scores.

## Open limitations before server qualification

- Participation-mode human text has no model-produced structured public intent.
  NPC actions are ledger-governed, but a human claim such as “I uploaded the
  report” is not yet represented through the same deterministic action gateway.
  This does not affect the autonomous matched-pair qualification, but a future
  production iteration needs either an explicit user action UI or a claim-only
  ingestion rule that cannot manufacture completion.

## Disposition

Local G3.1 engineering qualification passes. This authorizes preservation and
push of the milestone commits. It does not authorize staging deployment or a
confirmatory realism experiment; those require a fixed production-capable
model and a separately frozen server qualification manifest.

## Local gates

All must pass before a local milestone commit is considered:

- existing G3 public-ledger and speech-safety smoke suites;
- player configured-field acceptance;
- cross-kind action-to-verification lifecycle progression;
- subject-alias canonicalization;
- no entity mutation from invalid-clock events;
- no unregistered material-action execution;
- retrospective artifact narrative allowed, invented URL/hash rejected;
- historical transcript rule replay reports live-task and retrospective flags
  separately;
- application import, compile, and diff checks;
- at least one matched RoomMind/Baseline dialogue pair when a fixed local or
  authenticated cloud model is available.

Live dialogue results obtained from a small local model are engineering
diagnostics only and cannot be compared numerically with the fixed GPT-OSS 120B
generational studies.
