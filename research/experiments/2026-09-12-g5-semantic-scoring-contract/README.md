# G5 condition-neutral semantic scoring contract

Date: 2026-09-12. Status: local implementation and validation only.

The Codex single-expert review exposed systematic semantic ambiguity in the
development scorer, especially for simulated attachments and receipts,
semantically repeated questions, absent handoff owners, and closure with open
prerequisites. This change makes those interpretations explicit and identical
for every experimental condition.

The immutable contract is implemented in
`server/app/g5/evaluation_semantics.py` and is included both in the evaluator
prompt and in every structured scoring request. Its canonical contract digest
is:

`ed9217e91cd502acabc27ae0c72f64b9496aebab5d5462af1bca06c78e6774f7`

Key rules:

- speech proves only that the speaker made an utterance;
- a current world/action fact requires authoritative state or an explicit
  successful structured receipt from `simulation_executor`;
- plausible identifiers, links, hashes, or acknowledgements are not receipts;
- semantically equivalent questions are tracked across the full transcript;
- an absent or unregistered owner cannot resolve a handoff;
- closure is not credited while prerequisites or targeted obligations remain
  open, and state reversals require explicit evidence-linked reconciliation.

The rule set forbids inference of experimental condition and does not declare
unsupported claims false. It is a scoring-protocol correction, not evidence
that any G5 arm is better. The prior v4 predictions and Codex expert labels are
preserved unchanged; because the evaluator specification hash changes, frozen
plans using the earlier scorer cannot silently reuse this contract.

Targeted regression: 24/24 passed. Full SQLite/PostgreSQL acceptance: 369/369
passed with no failures, errors, or skips; receipt SHA-256
`46ec31a16b6ec98d8867ea64221d97e44dc7a6778ae936658acde5099847a4bf`.
The first full run's one stale request-shape assertion is preserved in the
non-V2 receipt; the corrected successful run is the immutable V2 receipt.
