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

After the gate freeze, the local untouched frame, role pack, and balanced eight-dialogue assignment were
created with hashes `b4535a7beece985c630c23653f3205a021c99608b4697ab84b11c0d0968eea37`,
`083178129d978918bbd4ac3146f519a43938bca2e06ac8e373c032321fe02125`, and
`1b5f48ef2d5532bd9330fe61a7c6fdd241541c6768adbb468360b0bcb924d0d0`. The four domains are
coastal shelter activation, field expedition launch, municipal water advisory, and microgrid service
handover. Automated checks confirm that domain IDs, role IDs, and public role names do not overlap the
v11 set. The execution module and resumable eight-dialogue entry point are locally ready, but no deployed
revision or external authorization is bound and no new dialogue has been generated.

## v12 execution failure and v13 recovery

The authorized v12 run sealed its first dialogue and stopped after three committed events in the
second. A cognition-planning response emitted two top-level goals without required child intentions,
raising `Goal requires child intentions`. The failed directory remains intact: SQLite integrity is
`ok`, with 19 committed events, 194 attempt rows, and one sealed source. The v12 execution binding is
`c5a5434bfb5157f8dda6d89b0fe3e8082510b8fd7db58214ff64688cbcfcb9cd`; the sealed source is
`4a81d822f60c996348cc190db7f5e8aeefb9871ad8d15076e946f62d7da6e2a4`. It remains a 1/8 failed
development batch and will not be pooled with its successor.

The cause was an execution-wrapper omission: v12 retained the base default of zero structured-output
revisions instead of carrying forward the qualified v11 settings. v13 restores
`reasoning_effort=low` and three structured revisions while holding the v3 worlds, roles, assignments,
model, 16-step stopping rule, and request budgets fixed. Its binding records the exact v12 predecessor.
Evaluation, the 32-dialogue screen, and confirmatory work remain disabled.

## v13 failure and proposed v14 repair

v13 used the intended three-revision budget. It sealed the first dialogue, committed 12 events in the
second, and then stopped after the question annotator returned the same schema conflict in all four
attempts: `kind=question` included a `question_id` field that is valid only for `kind=response`. The
generic “Invalid annotation fields” feedback did not identify the extra field. The preserved v13 store
passes SQLite integrity and contains 28 committed events, 320 attempt rows, and one sealed source. Its
execution binding is `a4c7e6d50bbbdbe026e3177da2e13b7feadf94138c97fc6b33c60b3f711105a4`; the sealed source is
`8bcfd812a9bc7da96ffce28a637437b4afd4dd13d2e91280778c4b502bfaa21f`.

The v14 candidate keeps fail-closed validation and does not silently delete fields or infer annotation
intent. On a field mismatch, its bounded repair feedback identifies missing and unexpected keys and
supplies the exact allowed key sets for questions and responses. This shared annotator change applies
equally to every arm. Worlds, roles, assignments, model, stopping rule, budgets, and evaluation barrier
remain fixed.

## v14 completion and scoring preflight

v14 completed all eight dialogues: two per arm, 16 events each, 128 committed events, 1,424 model
attempt records, eight seals, and zero reopenings. SQLite integrity is `ok`. The execution binding is
`89ccb30ec547c1542597f3c16aca143905b6c15fd3e604a951877f4d68e49354`; the public transcript content
hash is `f9a626e5ba3be2310d955d3ff2c5d16e397cb8562b20c788409ce88563c72994`. Offline verification passed
for all eight internal sources and reconciled their attempt counts exactly with SQLite.

Structural review found no protected value in public speech and verified registered action authority
through source replay. One microgrid dialogue contains four exact duplicate speech events, and two
dialogues end at the fixed 16-step cutoff with one pending question target each. These observations are
retained for blinded quality assessment; no dialogue was removed or selected based on them.

A local-only preflight froze all 48 dialogue-by-dimension scorer tasks and two independently ordered,
condition-free reference packets. The scorer input hash is
`3c6a948f396fa7d68426df10b506f342188eccf8b57088701c7e841e11744f48`; the preflight summary hash is
`1ff927a8488a995e5e893cc8a286fee6c1070b47316635121409586e2a8b370f`. The packets contain no model
predictions, condition labels, or source run IDs. No reference label or model score has been collected,
and external packet distribution remains unauthorized. The 32-dialogue screen stays paused.

Two isolated Codex AI reviewers then completed all 48 tasks independently. Reviewer A labeled 23 clear
and 25 violation; reviewer B labeled 25 clear and 23 violation. They agreed on 40 cells and disagreed on
eight. Their outputs were frozen before any scorer-output directory existed, with freeze hash
`b9e403f1129a44a5bf222d127c4ae395fa4432e54fa6b6312bb735d1c9a7a045`. A third Codex AI reviewer read
only an anonymous X/Y packet and adjudicated all eight disagreements without condition, reviewer-origin,
or model-score information. The final reference contains 22 clear and 26 violation labels, with eight
decisive labels in every dimension; its hash is
`d2c4420fc6d7241b315bd6ff53c0b0663ffcb60403c76c224e74a6c8f045e934`. These remain AI development
references rather than human gold labels.

The user then explicitly authorized the 48 frozen Ollama scorer tasks, at most 96 requests with every
raw response retained, while excluding the 32-dialogue screen. The authorization-record hash is
`b0151e890826b2b75efe04970dbfa6308dd170b0c6e56e3074914a3072f2d8ba`.

## v14 prospective gate result

The 48 frozen tasks used 50 requests. Forty-seven cells produced final predictions. One procedural
cell cited an unknown evidence ID on its first attempt and succeeded on retry. The microgrid-v2
temporal-coherence cell cited unknown evidence IDs on both permitted attempts and remains a final
technical failure. The output contains 34 clear predictions, 13 violation predictions, and one failed
cell; every raw HTTP response and attempt record is retained. The offline audit hash is
`d8c1e80b570a5864fd10d8c6dd6bfcd0d3a11a82539b5faffdf7353a71ceac75`.

Against the pre-scoring frozen two-AI reference, exact agreement is 34/48 (70.8%): 13 true positives,
21 true negatives, zero false positives, 13 false negatives, and one technical failure whose reference
label is clear. The false-positive rate is 0% and the false-negative rate is 50%. Agreement by dimension
is 75.0% epistemic fidelity, 87.5% interaction structure fidelity, 87.5% multi-party dynamics, 62.5%
procedural fidelity, 50.0% role strategy, and 62.5% temporal coherence. Thirteen of the fourteen
disagreements or failures are reference violations scored clear, so the dominant error is missed
violations rather than overcalling violations.

The prospectively frozen all-must-hold gate therefore fails five checks: 48/48 final completion, zero
technical failures after retry, at least 85% overall agreement, at most 15% false negatives, and at
least 75% agreement in every dimension. The comparison and gate artifact hash is
`d50bb9eeadf540d28de3e12a1de945e12c6b381e9461db86bedf3fcf2ad74c31`. This remains an AI-reference
development diagnostic and does not estimate human accuracy or an architecture effect. The
32-dialogue screen remains paused.

## Scorer v4 and the next untouched set

Scorer v4 addresses the thirteen v14 false negatives with six dimension-specific checks: affirmative
role-goal follow-through under current authoritative state, direct-knowledge limits from `visible_to`,
time-indexed interpretation of claims and receipts, semantic loops without responsive progress,
substantive multi-party influence beyond turn-taking, and completion/closure beyond correct operation
order. The catalog prompt also requires exact evidence-ID copying. One repair request is allowed only
after strict technical failure and must carry the failed raw response, precise local error code, and
complete valid-ID list; it does not silently strip or rewrite model output.

The v3 contract and prompt remain reconstructable at
`490ff3f1a9cb6c167b3c01d44672a7817ef1da6f8df0dc71c181565c987f8f57` and
`cb5056dc8951b1f0188e98ed735409d5b53cfa7e4f1d6fefd20f5aa4d40ce00e`, including exact v14 request
reconstruction. The v4 contract, prompt, and repair-instruction hashes are
`57d5ccf97ce8b1b05095653b2ed28f12cbba32cff187177c73117e99912e1faa`,
`ac969276d4cd7f3de35d297cd702f72858adbec88d9096f58281a0e5e30d77cc`, and
`d4b7234dba768b4e02331bdd6a2aace425de8f62f7a9c746b25c9b358b84589d`.

Before any new material was created, the same numerical gate was frozen for v4 at
`7967fac8a92743fe17e457a54fa6d5d20f266032d24c6e9d3a344959959370f0`. The subsequent untouched set
contains orchard frost response, archive collection transfer, satellite ground pass, and school-meal
allergen recall, with two worlds per family and two assignments per A/B/C/D arm. Its family IDs, role
IDs, role names, and public numbers are disjoint from the v11 and v14 sets. Frame, role-pack, and
assignment-plan hashes are `27f049c0a57a4ede71bcafeedf23681e84539801584ca11aa88f09f55cec8be2`,
`1417777806e9281db3253fc617026c1ab1a10e597bbe8aa6313cf11258cd9416`, and
`e2a24faa87702662509538b72c7f328755c49c063b15c0b2b854df4c315fff78`. This is local preparation only;
new dialogue generation, reference distribution, cloud scoring, and the 32-dialogue screen remain
unauthorized.

## v15 execution failure and proposed v16 recovery

Subsequent authorization covered only generation of the eight development dialogues through the
Ollama cloud model and retention of raw responses. It did not cover AI-reference construction,
scoring, or the 32-dialogue screen. v15 sealed five of eight dialogues and then failed on event three
of the sixth, in the satellite-ground-pass family. The preserved failed batch contains six worlds,
83 committed events, 902 model attempts, five freezes, and zero reopenings. SQLite integrity is `ok`
and the execution-binding hash is
`0a121e25e2c4bc3aa1d277dab58e507d3f269aed64613aedeaa5bc50dcd16463`. Raw attempts, generated source
bundles, the runner log, and SQLite remain in the separate `v15-development-online-failed` archive
and cannot be pooled with a recovery batch.

The failure arose during a `payload_coordinator` hierarchical-plan update. Four successive outputs
introduced a goal without a child intention, invented an unavailable operation, again introduced a
childless goal, and finally truncated the last character from an otherwise valid source ID. The final
error was `Updated task cites evidence outside supplied context`. Strict validation therefore blocked
an invalid commit as designed; the execution weakness was insufficiently explicit exact-copy feedback
after a source-reference rejection.

The v16 recovery candidate changes only structured-plan repair guidance and the revision allowance. It
returns the complete source-ID allowlist with a character-for-character copy instruction, repeats the
new-goal child requirement and the empty operation for non-execution, and permits four structured
revisions instead of three. The model, reasoning effort, eight worlds, arm allocation, 16-event limit,
stopping rules, scorer v4, and prospective gate are unchanged. v16 must rerun all eight dialogues in a
new directory and bind the v15 failed execution hash. The five sealed v15 dialogues remain failure
evidence and do not count toward v16 completion.

## v16 execution failure and proposed v17 recovery

v16 sealed four of eight dialogues and failed on event three of the fifth, in the orchard-frost
family. The preserved batch contains five worlds, 67 committed events, 678 model attempts, four
freezes, and zero reopenings. SQLite integrity is `ok`; the execution-binding hash is
`74c402748592cf17867a48dcb5787bed8405a2f68589727783e100d743114a6a`. All raw responses, source
bundles, logs, and SQLite remain in the separate `v16-development-online-failed` archive and cannot
be pooled with a recovery batch.

The model followed v16's exact-copy instruction. The actual defect was a mismatch between two local
sets: repair feedback advertised IDs from the complete private memory store, while incremental-update
parsing correctly accepted only evidence retrieved into the current model request. Some IDs declared
valid by the feedback were therefore rejected at the next layer. v17 makes the repair allowlist and
task-completion evidence list use the current retrieved set. The complete store remains available only
to revalidate sources already fixed in durable plan rows. This aligns feedback with validation without
expanding model-visible evidence. The model, materials, arm allocation, 16-event limit, stopping rules,
scorer v4, and prospective gate remain unchanged. v17 must rerun all eight dialogues in a new directory
and bind the v16 failed execution hash.

## v17 dialogue completion

v17 completed and sealed all eight development dialogues, with two assignments per A/B/C/D arm and
16 events per dialogue. The final archive contains 128 committed events, 1,434 model attempts, eight
freezes, and zero reopenings. SQLite integrity is `ok`; all eight source bundles pass manifest and seal
verification, and each transcript maps to the corresponding world, seal, and 16-event source. The
execution-binding hash is `b95cbe3786761ded454fc36ab5e40a0b771698cb5f6a78779733cbf7cfc92ec6`,
the transcript hash is `8900620420a654df6326de9fbfe9015740f73b93bb244b5a1bbfb0c71f0080c2`,
and the offline-audit hash is
`aa9b9844414233e52b0d5e451fa41542b9dfc6fe406f0068b1284b7d1f4c66d2`.

The eight-dialogue generation stage is complete. The v15 and v16 failures remain separate archives
and are not pooled with v17. No independent AI reference has yet been created for v17, scorer v4 has
not been run on its 48 cells, and the 32-dialogue complete-block screen remains paused.

## v17 independent AI reference freeze

Before any scorer-v4 call, the eight sealed v17 dialogues were converted into 48 dimension tasks and
two independently ordered blinded packets. The scorer-input hash is
`ea35300e0680a1146f0daf998a3d28ebfe786cdf587cd6e65430b97e589c68ea`; its scorer prompt, semantic
contract, and repair instruction exactly match the prospective v4 plan. The two AI reviewers labeled
35 clear/13 violation and 30 clear/18 violation. They agreed on 41 of 48 tasks. A third AI adjudicated
the seven disagreements without reviewer origins, arm conditions, or scorer outputs.

The frozen final reference has 48 decisive labels: 30 clear and 18 violation, with eight decisive
cells in every dimension. Its hash is
`a7b9dad9ede1d5cdab753be841b8c47551c89ed2eefdced2cc9797b892a89a30`. This remains an AI-only
development diagnostic rather than human gold and cannot estimate human accuracy or support a
confirmatory claim. Scorer v4 has not yet been called and the 32-dialogue screen remains paused.
