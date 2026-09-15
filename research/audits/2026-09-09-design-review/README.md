# Design and evidence review — 2026-09-09

## Preservation contract

This review is additive. Historical experiment data, qualification reports,
failed batches, and user-owned untracked research directories remain intact.
`archive-before.json` inventories 135 existing experiment/document files
(57,528,458 bytes) by SHA-256. This covers the local repository archive,
including untracked experiment directories; it is not a backup of the server
database or a claim that every remote artifact has been downloaded.

Verify with:

```sh
python scripts/audit_research_archive.py --root . --verify research/audits/2026-09-09-design-review/archive-before.json
```

An inventory detects changes; it does not replace backups. Preserve existing
remote artifacts and Git history. Do not rewrite old reports to erase an
earlier interpretation. This addendum takes precedence for interpretation.

## Interpretation corrections

1. Earlier assistant transcript readings are assistant audits, not independent
   human expert ratings. No external human review is established by them.
2. The six dimension means remain descriptive evidence. Their pooled mean is
   not a registered primary outcome: `docs/COMPARISON_PROTOCOL.md` explicitly
   requires separate dimensions and no composite realism score.
3. One four-pair, one-repetition development batch cannot establish a stable
   advantage or a causal improvement over another generation. The stored seed
   is used to shuffle pending runs; the inspected chat request does not submit
   that seed to the model. A fixed model label does not guarantee identical
   stochastic outputs or immutable cloud model weights.
4. The old strict failure verdict survives because of concrete routing and
   terminal-floor violations. Broad claims of improvement do not follow from
   one clean probe result or a count of blocked utterances.
5. Missing tool results alone do not establish that every fact is invented.
   Scenario facts and authorized role seed facts must be considered. A claim
   of a newly completed action or newly supplied artifact needs different
   provenance from a pre-existing role fact.

## Verified architectural findings

- `server/app/agent/speech_safety.py:963` extracts `PublicationClaim` records
  primarily through phrase regular expressions. A typed output container does
  not make the extractor semantically comprehensive.
- The terminal interview guard checks selected question wording while phase
  equals `candidate_questions`; this is not an authoritative, monotonic
  session termination transition.
- `server/app/research_probes.py` imports the same speech guards used by
  generation. Shared code is useful for consistency, but shared false negatives
  prevent these probes from serving as independent correctness evidence.
- `server/tests/g4_15_frozen_failure_replay.py` runs detectors over copied old
  transcripts. It tests recognition of known failures, not whether new live
  scheduling/publication prevents the failure.
- `record_simulated_tool_result` exists in the ledger, but repository search
  found its callers only in tests. The inspected incident and supply-chain
  runs have empty tool-result registries.
- The incident template explicitly requires `containment_active == true` for
  completion, assigns it to the SRE's `can_execute`, and requires it before
  recovery. The normal evidence registration path for execution is missing.
  Successful containment is therefore not demonstrated as reachable through
  the intended trusted execution path. A deferred outcome can still be valid;
  it must not be mislabeled as evidence of a poor meeting by itself.
- Generative orchestration keeps several overlapping surfaces: ordered player
  targets, a mutable agent queue, required-response ids, directed pending ids,
  pending player response, and an intra-turn terminal flag. A single persistent
  ownership/termination model should replace these competing sources of truth.

## G4.15 source check

Run 556's archived seed memories contain the supplier reservation price, margin
and liability constraints, quality responsibility, and an 83 RMB procurement
benchmark. They do not contain the 1,200/1,950 daily capacity, successful
5,000-unit quality pilot, or attached analysis asserted at sequences 9 and 13.
Earlier public messages 1–8 do not supply those facts either. This supports
the unsupported-claim finding against the inspected seed/public record; it
does not establish complete initial-prompt provenance where the export omits
the full original role/scenario object.

Run 562's SRE seed legitimately contains the signal that the error spike began
after payment-router release 4.18. The future evidence model must permit this
role disclosure without demanding a newly executed tool result.

## Revised work breakdown and baseline

Progress is recorded by deliverable, not arbitrary total percentages. G4.15
execution/archival is complete; G4.15 qualification failed. These are separate
statuses. The following is a new design-review work package, not a reset of
the old experiment's progress.

| Deliverable | Status at this review |
| --- | --- |
| Inventory and verify local historical archive | Complete; 135 unchanged files |
| Review protocol, code, seeds, and failure evidence | Complete |
| Record interpretation corrections without rewriting history | Complete |
| Specify execution-boundary alternatives and validation contract | Complete; see design document |
| Resolve simulation execution versus discussion-only objective | Decision required |
| Implement authoritative routing/terminal and evidence changes | Not started |
| Independent end-to-end and held-out local checks | Not started |
| New live qualification, separate dimension evaluation and audit | Not started |

No source deployment, scenario mutation, new model call, or new experiment
occurred during this review. The implementation generation remains G4.15.
