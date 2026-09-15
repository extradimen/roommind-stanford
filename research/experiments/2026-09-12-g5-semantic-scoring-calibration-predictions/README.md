# Semantic-scoring development re-evaluation

The user authorized one external re-evaluation of the same eight internal
public dialogues with Ollama Cloud `gpt-oss:120b`. Execution used concurrency
one and at most two attempts per case. Credentials stayed in memory.

- 48 cases were processed in 52 requests.
- 46 cases completed strict validation; 2 ended as technical failures.
- Attempt reasons: 46 valid, 4 incomplete responses, 2 evidence-count errors.
- Valid outputs: 25 clear and 21 violation.
- Audit SHA-256:
  `43d5ee470aa6d5f13c23ab46a5a642d01a9254e6cf9eaef6c862f47ed8ddaad2`.

Against the frozen single-Codex expert diagnosis, agreement was 29/46 (63.0%).
The prior v4 agreement was 31/46 (67.4%). On the 44 cases completed in both
runs, agreement changed from 30/44 to 27/44, a decline of 6.8 percentage
points. Epistemic and interaction agreement improved, while role-strategy and
temporal agreement declined. Comparison SHA-256:
`d32c4c5a1a491137877fe04d20727e6bc7c58e9a09b695618f16f20934377c17`.

This is development-set reuse against one AI expert, not human-grounded
accuracy or evidence of an architecture effect. Further tuning on these same
cases would risk overfitting.
