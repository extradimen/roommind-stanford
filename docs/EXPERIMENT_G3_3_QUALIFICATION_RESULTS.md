# G3.3 Staging Qualification Results

## Frozen batch

- Batch: `560252ab-1626-452b-801b-0ad0396e50b8`
- Source revision: `a52f94a88a395329c0f02025688d39022671dd3f`
- Model: `ollama/gpt-oss:120b`
- Design: four scenarios, one matched RoomMind/Baseline pair per scenario
- Result: 8/8 dialogues and 8/8 six-dimension evaluations completed; zero
  dialogue failures and zero degraded LLM fallbacks
- All eight exported transcript SHA-256 values were independently recomputed
  from persisted public messages and matched.

## Six-dimension AI results

| Dimension | RoomMind | Baseline | Difference |
|---|---:|---:|---:|
| Role and strategic fidelity | 5.75 | 5.50 | +0.25 |
| Epistemic fidelity | 4.00 | 4.75 | -0.75 |
| Temporal coherence | 4.75 | 4.50 | +0.25 |
| Interaction structure | 4.50 | 5.50 | -1.00 |
| Multi-party dynamics | 4.25 | 5.25 | -1.00 |
| Procedural fidelity | 5.00 | 5.25 | -0.25 |

These are development results from one replication per scenario. They are not
confirmatory evidence and no composite score is computed.

## Transcript audit

The governance mechanisms improved role discipline and temporal consistency,
but remained visible in public dialogue. RoomMind contained 31 lines matching
the recurring governance language (`remains open`, `responsible participant`,
or equivalent final-outcome disclaimers), compared with eight in Baseline.
All four RoomMind runs ended with `final_completion_status=stalled`; no
Baseline run carried that terminal label.

The dominant failure was an external-artifact loop: participants repeatedly
requested or promised an upload that a text meeting cannot deliver. The
interview also invented an upload, dashboard identifiers, metrics, and named
owners after the request loop. Therefore G3.3 passes engineering stability but
fails the realism qualification gate.

## Disposition

Do not use G3.3 as confirmatory evidence that RoomMind is more realistic. Move
to G3.4 local development with natural recovery language, bounded external
artifact handling, question-versus-evidence discipline, and explicit fallback
observability.

