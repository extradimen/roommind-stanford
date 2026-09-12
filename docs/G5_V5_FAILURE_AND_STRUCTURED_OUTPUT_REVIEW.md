# G5 v5 failure archive and structured-output review

Date: 2026-09-12

## Disposition

V5 is a failed development execution. It completed and sealed three of eight
dialogues, then stopped before event 5 of the fourth world. No evaluation,
architecture-effect estimate or confirmatory inference is permitted.

The next action should not be another isolated prompt patch. V2, v3, v4 and v5
show that the complete real-model path has not yet qualified as a stable research
instrument. A common structured-output reliability layer and a new engineering
qualification ladder are required before another eight-dialogue development run.

## Archived evidence

- Source revision: `b22eb7c6ca7d7a294363ff1e85d8723579d37aac`
- Execution binding: `86b4efff3849ffe11de5f755532968a97bd66fd134a5b88a18a1416a26c44dd4`
- Predecessor: `3fd2adfe9c3eeea8942c2b69dd957422cb82034e141838ab6700826f30f21868`
- Four worlds, 52 committed events, 560 attempt records and three freezes
- Failed world: `research-data-release-v2`, arm D, version 4
- Failure: `Task transition needs observed evidence`
- SQLite `PRAGMA integrity_check`: `ok`
- Remote and local SHA-256 values match for all seven downloaded evidence files
- All three internal source bundles verify their event chains and final seals
- No experiment runner remains active

The three process-level failures at version 4 contain two, four and four received
model-I/O receipts. The repeated request/response hashes differ after feedback,
showing that the repair loop ran; every final candidate still violated the same
plan transition invariant. The failure was therefore semantic/schema conformance,
not transport interruption.

## Cross-interface review

| Structured model interface | Used in dialogue generation | Current validation | Bounded correction | Rejected raw output retained | Remaining failure mode |
|---|---:|---|---:|---:|---|
| Reflection | Cognition arms | Exact list/item fields and source IDs | No | No | One malformed or unavailable citation stops the world |
| Hierarchical plan/update | Cognition arms | Exact fields, identity, dependencies, source and status evidence | Yes, 2 | Hash/bytes only | V5 proved repeated semantic repair can still fail |
| Role decision | All arms | Exact action/content/operation envelope and registered operation | External speech revision does not repair malformed decision JSON | Hash only on success | Invalid JSON or unavailable operation can stop the world |
| Governance auditor | Governance arms | Envelope plus downstream finding validation | Speech can be revised, auditor structure itself cannot | No | Malformed findings stop governed arms asymmetrically |
| Session annotation | All arms | Exact kind and Unicode span | No | No | Invalid span/envelope can stop any arm |
| Question annotation | All arms | Targets, spans, IDs and pending-response ownership | Yes, 2 | Hash/bytes only | V4 showed target errors; other fields remain possible |

The system therefore has different recovery semantics for six model-produced
structures. Only plans and question annotations receive validator feedback. The
attempt journal collapses exact validation failures into broad error codes and
does not retain rejected bodies. This creates both an execution reliability risk
and an auditability risk.

## Required common layer before v6

1. Define one hash-bound `validated-structured-generation` contract used by all
   six interfaces. Each adapter keeps its own schema and semantic validator, but
   shares receipt capture, bounded revision, terminal failure classification and
   configuration-drift checks.
2. Return machine-readable feedback containing the validator code, field path,
   invariant and the allowed ID set relevant to that field. Do not normalize,
   invent or silently insert evidence.
3. Persist every rejected response in an internal-only rejection capsule with
   request/response hashes, raw bytes, parser error, semantic error, revision and
   component. Keep it outside public transcripts and evaluator inputs.
4. Separate parse, envelope, reference, transition, authority and transport
   failures in the attempt journal. Process restart must not reset the component's
   bounded revision budget for the same world version.
5. Freeze per-component revision limits in the four-arm binding. Shared components
   must use identical limits in all arms; treatment-specific components must use
   identical limits wherever that component is enabled.
6. Add a deterministic failure-injection matrix for every invalid field class,
   including repeated invalid candidates and restart after partial repair.

## Qualification ladder

Before another eight-dialogue run, use new, non-evidentiary smoke worlds and the
same fixed provider/model:

1. One call for every structured interface, including a forced invalid-first then
   valid-second response.
2. One 16-event world for each arm A–D.
3. Four worlds in the exact intended assignment order, with process interruption
   and same-binding recovery.
4. Only after all above pass without unclassified failures, freeze a new source
   revision and start a fresh eight-dialogue development execution.

Smoke-world outputs are engineering evidence and must be registered as exposed.
They cannot be inserted into the eight-dialogue scorer-development set or later
confirmation families.

## Research consequence

The present blocker is instrument reliability, not evidence that cognition or
governance helps or harms dialogue quality. Starting scorer calibration on the
three completed v5 sources would create selection bias because completion is
correlated with scenario, arm and model-schema behavior. The valid next research
gate remains one independently bound 8/8 development generation.
