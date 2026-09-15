# G2.2 critical grounded coordination qualification protocol

## Purpose

Test whether deterministic task-criticality and output-level evidence grounding repair the
G2.1 backlog/fiction failure without changing the Baseline, shared player policy, model,
scenario information, or evaluation rubric. This is development-only exploration.

## Frozen candidate

- Generation: `G2.2`
- Architecture: `g2.2-critical-grounded-coordinated-agents`
- Fixed provider/model: `ollama/gpt-oss:120b`
- Scenarios: supply-chain negotiation (1) and incident command (4)
- Conditions: RoomMind and unchanged independent-memory-agent Baseline
- Repetitions: 2 per condition/scenario (8 dialogues)
- Concurrency: 1; safety maximum: 20; maximum stagnant turns: 6
- New random seed: `202609023`
- AI evaluation starts only after all verbatim transcripts are frozen
- Human review does not start automatically

## Candidate mechanisms

1. The state evaluator must label an event task-critical and cite a public blocking reason.
   A deterministic validator accepts criticality only when the public claim overlaps an
   unresolved state or contains explicit blocking/dependency language.
2. Incidental offers remain in the audit ledger but do not enter the coordinator queue.
3. Overdue/blocked critical work outranks state variables initially; unresolved configured
   state outranks non-due work. A blocked item can hold focus for at most two consecutive
   turns when another unresolved state exists, after which focus rotates.
4. If no alternative exists, a repeated blocker becomes an explicit outcome-resolution
   focus requiring handoff, rejection, conditional closure, deferral, or failure.
5. NPC and player public-output validators reject newly invented attachments/uploads,
   external URLs, and 32–64 character hexadecimal hashes before persistence. A rejected
   candidate is regenerated; safe fallback remains available.
6. Forensic exports record grounding rejections, task-critical/incidental work counts,
   focus rotations, outcome-resolution turns, and G2.2 integrity probes.

## Deterministic gates

1. 8/8 runs terminate without code failure, orphaned worker, or missing transcript.
2. All transcript hashes are nonempty, unique, and independently recomputable.
3. All applicable probes pass, including independent memories, coordinator history/order,
   registered owners, grounded public evidence, and task-critical work focuses.
4. No completed result retains an unmet configured completion condition.
5. No blocked work issue occupies more than two consecutive ordinary work-focus turns when
   another configured state issue is unresolved.
6. Provider retries, grounding rejections, fallbacks, and transport errors are disclosed.

## Progression gates

The G2 progression gates remain unchanged:

1. At least three of four RoomMind sessions have a task-grounded terminal outcome.
2. No more than one RoomMind session reaches the safety limit.
3. RoomMind does not exceed Baseline in safety-limit endings.
4. Condition-blinded procedural fidelity is not lower than Baseline in either scenario.
5. No gain is accompanied by protected-information leakage or authority violation.

Failure freezes G2.2 as diagnostic evidence and leads to another candidate; it never permits
editing or excluding the failed runs.
