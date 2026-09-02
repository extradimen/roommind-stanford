# G3.2 Staging Qualification Results

Date: 2026-09-02

Status: failed engineering qualification; frozen development evidence only.

## Frozen batch

- Batch UUID: `7135ae99-d1c6-4f3a-842b-93a8a832009c`
- Source revision: `98cef2e8541cea75a503d522489d97a31457d004`
- Model: fixed `ollama/gpt-oss:120b`
- Design: four scenarios × RoomMind/Baseline × one repetition = eight runs
- Dialogue generation: 8/8 completed, zero technical failures, zero degraded
  fallbacks
- Independent six-dimension AI evaluation: 8/8 completed
- Human review: not started

All transcript SHA-256 values were present and distinct. All applicable
implementation-integrity probes passed. The dialogue artifacts therefore
remain useful for diagnosis even though G3.2 did not qualify.

## Six-dimension diagnostic result

| Dimension | RoomMind | Baseline | Difference |
|---|---:|---:|---:|
| Role and strategic fidelity | 4.50 | 4.50 | 0.00 |
| Epistemic fidelity | 4.25 | 5.50 | -1.25 |
| Temporal coherence | 3.25 | 3.50 | -0.25 |
| Interaction structure | 2.75 | 4.25 | -1.50 |
| Multi-party dynamics | 3.50 | 4.25 | -0.75 |
| Procedural fidelity | 3.50 | 4.75 | -1.25 |

These are development diagnostics, not confirmatory evidence. With one
repetition per cell and architecture-derived failure in the shared speech
boundary, no inferential claim is warranted.

## Deterministic and qualitative findings

All four RoomMind runs stopped with `governor_stop_reason=no_task_progress`,
`final_completion_status=stalled`, and zero grounded outcome-resolution events.
The supply-chain run was closest to usable, but still reopened written-payment
evidence after material terms had been discussed. Launch, interview and
incident runs contained repeated clarification/open-issue turns.

The interview pair isolated the principal regression. RoomMind recorded 47
public-output rejections: 17 final/retry pairs for
`retrospective_scope_not_grounded_in_quote`, 16 for `public_draft_echo`, plus
structured/truncated failures. The shared player then repeatedly emitted
`Could you clarify the most important unresolved issue ...`. Baseline used the
same shared player safety boundary and developed the same loop, so this batch
cannot isolate a RoomMind-versus-Baseline treatment effect.

The G3 ledger itself remained honest: every RoomMind run passed ledger
presence, provenance, lifecycle, monotonic-clock, inline-evidence and
completion-reconciliation probes. The failure was the opposite trade-off:
safe state with over-rejected, repetitive public speech.

## Disposition

G3.2 is frozen as a failed qualification. It must not be pooled with a later
generation or presented as evidence that RoomMind improves realism. G3.3 must
retain the authoritative public ledger while repairing false-positive
retrospective detection and the single global clarification fallback.
