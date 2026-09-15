# G2.3 qualification results (frozen diagnostic evidence)

## Artifact identity

- Batch: `79078212-aab9-45fa-baf1-cc64ba880a13`
- Generation: `G2.3`
- Architecture: `g2.3-grounded-bounded-focus-agents`
- Scope: development/qualification evidence, not confirmatory evidence
- Dialogue generation: 8/8 terminal
- Six-dimension AI evaluation: 48/48 completed
- Technical dialogue failures: 0
- Transcript integrity: all persisted transcript hashes recomputed exactly and
  all eight hashes were unique

The batch, public transcripts, debug bundle, final evaluation, manifests, and
hashes are frozen. They must not be regenerated or overwritten by G3.

## Matched-condition results

Mean AI ratings on the 1-7 realism scale:

| Dimension | RoomMind | Baseline |
|---|---:|---:|
| Role and strategic fidelity | 5.50 | 6.00 |
| Information boundaries | 5.25 | 6.25 |
| Temporal coherence | 4.50 | 6.25 |
| Interaction structure | 5.75 | 6.00 |
| Multi-party dynamics | 5.25 | 5.75 |
| Procedural fidelity | 5.00 | 6.50 |

Procedural fidelity by scenario was 4.50 versus 6.50 for supply chain and 5.50
versus 6.50 for incident command (RoomMind versus Baseline).

## Qualification decision

G2.3 failed qualification. Only two of four RoomMind dialogues reached a
completed state; two stopped with `no_task_progress`. Direct transcript review
found that both completed RoomMind dialogues closed prematurely. Across all
four matched pairs, the Baseline transcript was judged more natural and more
coherent during detailed reading of the 458 public messages.

The deterministic G2.3 probes all passed even though RoomMind still generated
unsupported status pages, attachments, storage locations, hashes, and completed
external actions. Nine visible safety fallback prompts also appeared in public
dialogue. This is evidence that the probes and post-hoc state extraction were
not sufficient to establish public-world truthfulness.

## Architectural implication

G2.3 selected a bounded coordinator focus and rejected known unsafe text
patterns, but still generated speech before deriving state. The system had no
single authoritative record capable of deciding whether an action actually
occurred, whether the speaker had authority, whether evidence existed, and
whether the result could count toward completion. This failure motivates G3's
pre-speech structured intent validation and authoritative Public World Ledger.
