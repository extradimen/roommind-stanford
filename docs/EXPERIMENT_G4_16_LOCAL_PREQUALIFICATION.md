# G4.16 Shared Simulation and Resumable Evidence Governance

G4.16 is a development screening candidate following the strict G4.15 failure.
It does not reinterpret or replace any earlier transcript, score or disposition.

## Motivating evidence and correction

G4.15 completed technically but only one of four RoomMind runs passed applicable
probes and its six-dimension mean trailed Baseline. Manual audit found unsupported
current-world claims, response-owner failures, post-terminal speech and repetitive
safe fallback. Those data diagnose defects on a repeatedly tuned development set;
they do not establish stable or causal superiority for either architecture.

The earlier system also had no trusted executor for purported live actions, its
worker recovery recreated a session rather than continuing the committed session,
and its evaluator could see receipt-like prose without server-registry provenance.

## Candidate mechanisms

1. A bounded internal world executor has no network, shell or real-world effects.
   The same contract, prompt, operations and public facts are available to both
   conditions. Only an exact persisted receipt can change simulated world facts.
2. RoomMind may project a successful receipt into its typed task state through
   ordinary actor and phase authority. Baseline retains no RoomMind task state.
3. Evaluation and blinded-review packets receive a condition-neutral verified
   receipt sidecar. A receipt label, failed result or blocked result is not success.
4. A persistent ordered response queue preserves multi-addressee and nested
   NPC-to-NPC response ownership. Multi-vocative parsing is bounded and tested.
5. Interrupted workers retain the original session and resume at the next committed
   turn. Session identity and completed-turn counters must agree or recovery fails.
6. Scenario, role, world and applicable dispatch inputs are captured with per-cell
   hashes. Their aggregate hash is part of the checksummed research manifest and
   is verified before session creation, every dialogue step and evaluation.

## Scenario and evidence policy

The prior world-v1 and world-v2 snapshots remain preserved development artifacts.
G4.16 uses world-v3. Only the live incident scenario exposes executable operations;
adding an empty execute interface to negotiation, launch and interview was removed
as needless prompt noise. Static role facts and retrospective candidate statements
remain evidence in their declared scopes; they do not require an executor receipt.

These four source scenarios have been repeatedly inspected and are not held out.
Therefore G4.16, if launched, is `screening` and `candidate_selection_only`. Use two
repetitions per condition (16 dialogues, 96 independent dimension evaluations),
fixed model, dialogue concurrency 1, evaluation concurrency 1 and seed 20260916.
No confirmatory claim is permitted. A later confirmation must preregister unseen
scenario instances before their outputs are inspected.

## Local gates

- world-v3 manifest hashes and semantic action reachability pass;
- action fields, actors, execute/confirm authority and execution-confirm types agree;
- condition parity, prerequisite, rejection, idempotence and state persistence pass;
- spoof/replay handling and six-judge receipt propagation pass without hash changes;
- actual worker coroutine resumes the same ORM session after a committed turn;
- manifest/input drift fails closed, while historical unbound batches remain readable;
- public-ledger, speech-safety, LLM resilience and research-protocol smokes pass;
- applicable frozen G4.6–G4.15 replay checks pass;
- client and admin production builds pass;
- historical archive verification reports zero missing or changed files.

## Live gates

- only an explicitly authorized committed revision may be pushed and deployed;
- deployed revision, G4.16 identifiers, world-v3 hashes, provider/model and frozen
  manifest must match before dialogue generation;
- 16/16 dialogues freeze with zero technical failure or degraded output;
- interruption recovery, if exercised, retains the same session and transcript prefix;
- transcript hashes recompute before and after evaluation;
- 96/96 dimensions complete; partial retries target only missing dimensions;
- all G4.16 and applicable legacy probes pass, followed by manual reading of all
  eight matched pairs and an evidence-based strict disposition;
- no external human review starts automatically.

Local implementation checks do not authorize push, deployment, scenario import,
live model calls, batch creation or external review.

## Local result

PASS on 2026-09-10. The 25 focused tests, Python compilation, public-ledger,
speech-safety, LLM-resilience and research-protocol smokes, frozen G4.7–G4.15
replay chain, both isolated PostgreSQL tests, world-v3 semantic validator and
client/admin production builds passed. Builds emitted only the existing large-
chunk warning. The 135-file historical inventory verified with zero changes or
missing files. This remains local screening readiness, not a live result.
