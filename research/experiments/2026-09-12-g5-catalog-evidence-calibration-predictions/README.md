# G5 immutable evidence-catalog development review v4

The user explicitly authorized retransmitting the same eight internal public dialogues to
Ollama Cloud `gpt-oss:120b` for this 48-case v4 development review. The frozen retry ceiling
was two attempts per case and 96 total requests.

- Frozen input SHA-256: `55f0de1fb8f61691030b7055fd21b6dfe92267c6bba877279fe1a6f82f7edc9b`
- Actual requests: 53
- Final cases: 48
- Strictly completed: 46
- Final technical failures: 2
- Completed predictions: 30 clear, 16 violation
- Attempt outcomes: 46 valid, 6 evidence-count violations, 1 unknown evidence ID
- Final failures: `legacy-460-interaction_structure_fidelity` and
  `legacy-462-interaction_structure_fidelity`
- Audit SHA-256: `de61866a82e743bb10649d30e8afa4cfc7638a6042578b94676abf7b384a8ac7`

All six evidence-count violations returned 6–10 citations despite a frozen maximum of five;
the unknown ID occurred only on an initial attempt that later succeeded. Every attempt has
immutable start, HTTP and parsed-result records. Credentials were used only in process memory
and are not present here. This measures protocol adherence, not reference-labelled accuracy
or a G5 treatment effect.
