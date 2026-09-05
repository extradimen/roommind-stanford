# G3 local prequalification — 2026-09-02

## Status

This is exploratory engineering evidence, not a confirmatory comparison and not
an external realism evaluation.  Revision `dd070fa` was kept unchanged while
the checks were run.  Nothing was pushed or deployed.

The local database path was qualified with an isolated SQLite database by
compiling PostgreSQL `JSONB` columns as SQLite `JSON`.  The schema created
successfully without reading or modifying staging data.  A matched one-scenario
RoomMind/Baseline harness was prepared with concurrency 1 and a 12-turn budget.
Live generation is pending a locally available model: the Mac is not signed in
to Ollama Cloud, and downloading a local model was suspended when network speed
made the remaining wait disproportionate.  Historical fixed-model evidence was
therefore used only for rule replay, not as a G3 outcome comparison.

## Deterministic falsification results

Four adversarial checks failed against the current G3 public-world ledger:

1. **Player authority is not projected into the ledger validator.**  The AI
   player is passed an empty authority object.  A configured-field acceptance,
   such as accepting `unit_price`, is downgraded from `accepted` to `proposed`.
2. **Verification fragments the entity.**  An `action` submission and a later
   `verification` of the same subject become separate entities.  The second
   event starts at `submitted` instead of advancing the action to `verified`.
3. **Subject rewording bypasses lifecycle identity.**  “calculate recovery
   window” and “recovery window calculation” create different entity IDs even
   when both use the same configured field.  Lifecycle sequencing therefore
   depends on the model reproducing an exact subject string.
4. **Invalid-clock events still mutate entities.**  A regressed event is marked
   `clock_valid=false` and does not move the ledger clock, but its entity is
   still written to the authoritative entity map.

An additional authority-path inspection found that an action whose `field` is
omitted and cannot be uniquely inferred bypasses `can_execute` enforcement.
Because `field` is optional in the generation contract, this is reachable in
ordinary model output.

## Historical transcript rule replay

The G3 public-evidence filter was replayed over the frozen G1.1 GPT-OSS 120B
artifact (`24` runs, `1,350` public messages).  It flagged `34` messages:

| Scenario | Baseline | RoomMind | Main reason |
|---|---:|---:|---|
| Supply-chain negotiation | 3 | 7 | claimed attachments/emails |
| Launch decision | 1 | 5 | claimed attachments/emails |
| Structured interview | 3 | 9 | past-tense evidence claims and invented URLs |
| Incident command | 2 | 4 | claimed external forensic artifacts |

Most live-task flags identify exactly the fabrication G3 is intended to stop.
The structured-interview flags reveal an open-scenario false-positive class:
a candidate may legitimately describe a past email, attachment, or action as
part of an experience narrative.  The current generic rule cannot distinguish
that retrospective claim from an action supposedly executed in the live text
simulation.

## Architectural implications

G3 should not progress to deployment or a new confirmatory batch in its current
form.  A G3.1 candidate should first:

- derive player authority from `task_config.state_schema` permissions;
- introduce a stable canonical entity key, preferring configured field/action
  IDs over free-form subject text and resolving aliases before validation;
- let verification advance the canonical action/artifact entity while
  preserving executor, submitter, verifier, and approver as distinct roles;
- reject or quarantine invalid-clock events before changing authoritative
  entities;
- require an authority-bearing field or registered capability for material
  actions and artifacts;
- add a scenario epistemic mode such as `live_operation`, `retrospective_claim`,
  and `in_session_work`, so open scenarios do not share one evidence rule;
- reconcile the task-variable state and Public World Ledger so they cannot
  report contradictory lifecycle states for the same configured field.

After those changes, rerun the same deterministic counterexamples, then the
prepared matched local dialogue pair.  Only a fixed-model server batch should
be used for comparison with earlier generations.
