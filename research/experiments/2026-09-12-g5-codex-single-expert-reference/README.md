# G5 Codex single-expert development review

At the user's direction, Codex read all eight blinded public dialogues and assigned one label
for each of six dimensions: 48 decisions in total. This is an AI expert development review,
not a human annotation, not two independent ratings, and not confirmatory reference truth.

The decisions were made from `reviewer-a.json` without opening the coordinator's source
condition mapping. Each decisive row cites immutable evidence IDs and includes a rationale.
After the 48 labels were frozen, the coordinator mapping was joined only to compare the
single-expert labels with the earlier v4 `gpt-oss:120b` outputs and inspect condition-level
patterns. No external model was called in this phase.

## Results

- expert labels: 19 `clear`, 26 `violation`, 3 `uncertain`
- v4 completed outputs comparable: 46/48; two v4 cases remained technical failures
- exact label agreement on completed v4 outputs: 31/46 (67.4%)
- agreement by dimension: role strategy 8/8; procedural fidelity 6/8; temporal coherence
  6/8; interaction structure 4/6; multi-party dynamics 5/8; epistemic fidelity 2/8
- expert labels by condition: Baseline 9 clear, 14 violation, 1 uncertain; RoomMind 10 clear,
  12 violation, 2 uncertain

The condition split is mixed by family. RoomMind has fewer violations in the interview and
incident families, but more in market-launch and supply-chain. With one AI reviewer, four
development pairs, prior exposure, and no sampling model, this is diagnostic only and is not
evidence that either condition wins.

The largest scorer disagreement is epistemic fidelity. The v4 model often treated a coherent
public assertion as clear, while this review marked simulated attachments, uploads, checksum
receipts, or unverifiable historical claims as violation/uncertain. Long repeated question
loops and unresolved floor ownership were also under-detected in several v4 outputs.

## Files

- `codex-review.json`: the frozen 48-row blinded expert review
- `v4-comparison.json`: post-label join to source conditions and v4 model outputs

Internal review SHA-256 values are stored in each JSON file. These artifacts must never be
counted as `human_annotations_collected`, inter-rater reliability, scorer accuracy, or G5
confirmatory evidence. Independent human reference labeling remains the scientifically valid
next step if the study requires human-grounded claims.
