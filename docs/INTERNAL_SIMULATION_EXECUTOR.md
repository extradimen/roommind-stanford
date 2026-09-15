# Internal simulation executor — implementation record

## Scope and status

On 2026-09-09 the user approved the internal executor option in
`DESIGN_REVIEW_2026_09_09.md`. This local implementation adds a shared, bounded
virtual world to both RoomMind and Baseline. No real service, infrastructure,
or customer system is invoked. Existing scenario templates and historical
data remain unchanged. No live experiment is enabled by default.

Implementation files:

- `server/app/world/executor.py`: deterministic requests, authority,
  prerequisites, fixed outcome fixtures, receipts, persistence and idempotency;
- `server/app/agent/loop.py`, `server/app/agent/act.py`: RoomMind request and
  evidence registration path;
- `server/app/baseline_chat.py`: identical operation contract and receipts,
  separate public world storage without adding RoomMind governance;
- `server/app/orchestrator/generative.py`: persisted completion prevents a new
  model tick; the action boundary independently prevents execution after close;
- `server/tests/test_simulation_executor.py`: independent expected traces and
  mocked real adapters, without using speech probes as the test oracle.

## Configuration and request

A **new versioned** scenario may opt in through `task_config.simulation_executor`:

```json
{
  "schema": "roommind-simulation-executor-v1",
  "initial_facts": {"evidence_preserved": false},
  "actions": {
    "preserve_evidence": {
      "actors": ["security_lead"],
      "field": "evidence_preserved",
      "value": true
    },
    "activate_containment": {
      "actors": ["sre_lead"],
      "requires": {"evidence_preserved": true},
      "field": "containment_active",
      "value": true,
      "outcome": "success"
    }
  }
}
```

An agent requests `action="execute"` and `simulation_action` with a stable
`request_id`, declared `operation`, and exact configured `parameters` object.
The outcome and result value come from frozen configuration, never the model.
Use `outcome="failed"` in failure fixtures. Unknown operations, missing
prerequisites, wrong actors and parameters yield blocked receipts. Missing
facts do not satisfy a null prerequisite, and booleans are distinct from integers.

These are controlled scripted world transitions, not a model of physical
infrastructure. Realism and causal effects still require subsequent evaluation.

## Persistence and evidence

The world stores immutable first-request receipts and public facts. Identical
retries return the original receipt; conflicting reuse of an id is rejected.
The contract hash must remain identical after restart. Agents see their own
available operations and public world facts. Private memories never enter the
executor. A completed RoomMind session rejects new execution before side effects.

The engine publishes a clearly labeled simulation receipt in the requesting
actor's response slot, with structured receipt metadata. It does not paraphrase
the result with an LLM. Both conditions use the same rendering. Baseline keeps
the receipt in ordinary public history; RoomMind additionally registers successful
results in its existing evidence ledger. Blocked and failed receipts do not
register successful action evidence. Baseline requests in a turn are applied in
its existing stable actor order; this scheduling policy must be recorded in the
future experiment design.

## Validation performed

Nine tests pass, including an expected blocked/success/failed event sequence,
serialize/reload after each event, stable retries, conflicting request ids,
contract drift, undeclared parameters, wrong-type prerequisites, and matching
receipts through the real Baseline and RoomMind adapters with mocked LLM/database
boundaries. A terminal restart makes no model configuration call and performs
no execution. Public-ledger and speech-safety smoke tests and the existing
G4.15 frozen failure replay pass. The latter is only a detection regression.

## Remaining integration before qualification

This implements the approved executor foundation, not the entire revised
qualification plan. Pending work includes a newly versioned complete scenario
and world snapshot, database-backed execution/receipt restart testing, evaluator
presentation of explicitly sourced receipts, authoritative multi-addressee queue
integration, and independent end-to-end floor/closure checks. Initial role fact
provenance and held-out validation remain required. Do not declare G4.16 qualified
or launch a batch from this partial integration.

All prior experiment files and reports are verified against
`research/audits/2026-09-09-design-review/archive-before.json`. This record is
additive and does not rewrite the earlier design review's point-in-time status.
