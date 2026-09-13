# G5 v11 scorer development diagnosis

Status date: 2026-09-13. This document reports development diagnostics from eight sealed dialogues.
It is not an architecture-effect analysis, human accuracy estimate, or confirmatory result.

## Frozen inputs and provenance

- v11 execution binding: `1f6b4e7b030bc608df66c3274f6adbfc7e3d9c9abc0967912840968d7dde4fd4`
- public transcript content: `03f9ebf1d1a701a8f42199051ae9758b4804dda54edc5c97536d4fc37bff5a48`
- 48-cell scorer input: `ac09d92494c00ad9994b547017b113b344eafbed7a645e331d756db8b7f89ae0`
- pre-scoring AI reference file: `96f289023dbb2fa60cb1fd9d49b292802753d9342cc78723e4af0ef415fb5dc0`
- reference freeze: `b254e54a449da39985de12c633c045ba4b340b3a8b0416b2cc374172ff1f4b7a`
- scorer attempt audit: `38de69a28d83d21ef523b388385e99a47a337e180716b958c9b9f3c7602a151a`
- reference comparison: `546b1f973b5dfbd8c01341c36776095f25c65e6d6c511c1c1e7819be0ff62529`
- condition-guess audit: `7a6894c392ae4cb01b53807cf3281dd05e2695adb9b805a019b2dd7ca2109d2c`
- blinded disagreement packet: `62182130e5232f2bf80d022098a1783a64d5152e0f2b11ed99fc128ababaea93`
- independent adjudication file: `bab875c550063f85aa94fc4edd589ee80ec4f97e52881ea6bb8dee41e429e884`
- adjudication audit: `eca7f32b653dc4539a7f1282637bce623700398be4f168567215d0427fc86293`

The reference came from a separate Codex task that only read the anonymous reviewer packet. Its
48 labels were frozen before the scorer process began. It is one AI expert development reference,
not a human gold standard. The scorer used Ollama Cloud `gpt-oss:120b` under the frozen semantic
contract. Raw responses, including the one failed first attempt, remain internal and append-only.

## Technical completion

| Measure | Result |
|---|---:|
| Assigned cells | 48 |
| Final completed cells | 48 |
| First-attempt completions | 47 |
| Technical failures | 1 invalid evidence-count response |
| Authorized technical retries | 1 |
| Total remote requests | 49 |
| Final abstentions | 0 |
| Final clear predictions | 28 |
| Final violation predictions | 20 |

The execution path completed reliably. This separates transport/format reliability from semantic
agreement: the batch is technically complete even though its judgments are not yet reliable enough.

## Agreement with the frozen AI reference

The reference marked 18 cells clear, 24 violation, and 6 uncertain. Only the 42 decisive reference
cells enter the clear/violation confusion counts.

| Measure | Result |
|---|---:|
| Exact decisive agreement | 28/42 (66.7%) |
| True positives | 14 |
| True negatives | 14 |
| False positives | 4 |
| False negatives | 10 |
| False-positive rate among reference-clear cells | 22.2% |
| False-negative rate among reference-violation cells | 41.7% |

| Dimension | Decisive reference cells | Agreement |
|---|---:|---:|
| Role strategy | 5 | 20.0% |
| Epistemic fidelity | 8 | 50.0% |
| Interaction structure | 6 | 66.7% |
| Procedural fidelity | 7 | 71.4% |
| Temporal coherence | 8 | 75.0% |
| Multi-party dynamics | 8 | 100.0% |

These are descriptive cell counts from eight shared dialogues. The six dimensions are not independent
samples, and a 100% result in one eight-cell dimension does not establish population reliability.

## Preliminary disagreement diagnosis

This section is a coordinator-side diagnostic after unblinding assessment origins. It is not an
independent adjudication.

The clearest recurring scorer problem is grounding. Several scorer judgments treat a Boolean flag
such as `review_completed=true` as proof that the underlying risk is acceptable, or treat an opaque
constraint token as proof of a numeric shortfall. Other judgments accept the initial Boolean state as
a separate persistent current state after an authoritative receipt updated it. These patterns account
for multiple epistemic and temporal false negatives.

A second pattern is dimension transfer. In one disagreement the scorer turns a stale factual claim
into a procedural violation even though the registered workflow later executes in the correct order.
In another, it turns the same stale claim into a role-strategy violation without showing that the role
assumed another actor's authority or abandoned its strategic interest. This is exactly the kind of
cross-dimension transfer the semantic contract was intended to prevent.

Interaction judgments also disagree on what counts as a responsive answer or a directed request.
The scorer sometimes treats an explicit statement of unavailable numeric information as a failed
response, while elsewhere it says no question exists despite repeated imperative requests for missing
information. A separate adjudicator must apply one interpretation consistently.

The single AI reference may also be over-demanding in role strategy. It sometimes interprets a weakly
grounded substantive position as abandonment of a role goal, while the scorer treats authority and
surface role separation as sufficient. Three of eight role-strategy references are uncertain, leaving
only five decisive cells. Independent adjudication is necessary before attributing all four role
disagreements to the scorer.

## Residual condition blinding

The independent reviewer made one four-way mechanism guess per dialogue after freezing labels. Three
of eight guesses were uncertain. Two of all eight guesses matched the hidden arm meaning; two of five
directional guesses matched, with confidence between 0.35 and 0.55. At this sample size the result is
consistent with weak condition visibility, but it does not prove blinding equivalence.

## Independent disagreement adjudication

A second Codex task read only the anonymous 14-item packet. Its task trace shows two reads of that
packet, no repository search, no coordinator or source-file read, and no network call. It completed all
14 items before the coordinator revealed the randomized X/Y origins. This remains a single-AI
development adjudication rather than human ground truth.

Of the 14 conflicts, the adjudicator selected the frozen reference assessment in 12, the Ollama scorer
assessment in one, and `uncertain` in one. Among the scorer's ten apparent false negatives, all ten
adjudications supported the reference violation. Among four apparent false positives, two supported the
reference clear judgment, one supported the scorer violation, and one remained uncertain. By dimension,
the adjudicator supported the reference in all four epistemic conflicts, all four role-strategy conflicts,
both interaction conflicts, one of two procedural conflicts, and one of two temporal conflicts.

Combined descriptively with the 28 cells on which scorer and reference already agreed, 41 of the 42
decisive-reference cells received a directional adjudication; the scorer aligns with 29 of those 41 and
the frozen reference with 40. These counts do not estimate human accuracy because both reference and
adjudicator are single AI reviewers and the cells share eight dialogues.

## Current decision

No numerical acceptance threshold was frozen before seeing these outputs, so a threshold cannot be
selected retrospectively to declare success. More directly, 14 decisive disagreements, a 41.7%
false-negative rate against the development reference, and especially the role/epistemic patterns do
not support launching the 32-dialogue architecture screen now.

The independent adjudication rules out retaining the scorer unchanged. The next step is to revise the
scorer contract around authoritative state updates, opaque signals, completion-versus-outcome semantics,
dimension isolation, and imperative request handling. Labeling guidance should receive matching
clarifications so later reviewers apply the same rules. The one procedural conflict favoring the scorer
and the one temporal ambiguity must be retained rather than silently recoded.

Any revised scorer must be validated on new untouched material. The v11 dialogues, reference labels,
disagreements, and adjudications are now exposed development data and cannot certify the revision. The
32-dialogue architecture screen remains paused until the revised scorer passes a prospectively frozen
validation gate on that new material.

## Scorer v3 and the next frozen gate

The revised condition-neutral semantic contract is
`490ff3f1a9cb6c167b3c01d44672a7817ef1da6f8df0dc71c181565c987f8f57`; its catalog prompt is
`cb5056dc8951b1f0188e98ed735409d5b53cfa7e4f1d6fefd20f5aa4d40ce00e`. The implementation keeps
the old v2 contract and prompt available for exact reconstruction of every v11 request. A full local
G5 regression completed with 411 tests passing and 48 PostgreSQL tests skipped because this run did
not enable the database test target.

Before any new validation dialogue or score was generated, the next gate was frozen as
`806c776d6452177cef4222c9d8d9c2327ed8aeb0bc11c206893d4c6e521cde66`. It requires 48/48 final
technical completions, at least 36 decisive reference cells, at least 85% overall decisive agreement,
false-positive and false-negative rates no greater than 15%, at least six decisive cells per dimension,
at least 75% agreement in every dimension, and no more than 15% scorer abstention. All conditions must
hold. The new set will use four new domains with two worlds each and cannot reuse v11 names, numbers,
templates, or event sequences. No new material or external call is covered by this local plan freeze.
