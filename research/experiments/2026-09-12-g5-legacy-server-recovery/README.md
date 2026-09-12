# Authorized legacy SSH recovery — 2026-09-12

User authorized read-only SSH discovery/download from ubuntu@43.162.83.232.
No deployment, restart, POST, model call or old batch mutation. GET requests may
emit normal access/export telemetry, not changes to frozen dialogue records.

- `historical/`: 17 existing server files preserved byte-for-byte.
- `current/`: 54 current GET exports from 18 document-identified old batches:
  G2/G2.1–G2.3, G3.2–G3.9, G4.0/G4.1/G4.2.1/G4.3–G4.5.
- `recovery-receipt.json`: 71 successful transfers, origins, byte counts and
  matching remote-stream/local SHA256; 240,645,669 payload bytes.
- `audit.json`: 18 batches/144 runs, all recorded public transcript hashes and
  manifest hashes match. All statuses evaluation_completed. Six paired old and
  current exports have identical run IDs and public transcript hashes.
- `invalid-audit-only/` plus separate receipt: 3 exports of invalid G4.2 batch
  9dfe911a-6c05-4438-9fae-cefa274e56af. Ineligible for evidence; never resumed.

Audit content SHA256:
`9bdc4fa466b59cf9c5fff579ab865b8a280801dbcbf6479f8da108d990bb6125`.

Current exports are new serializations of stored records, not original export
bytes. Current debug probes may use current code and must not masquerade as old
generation probe results. Debug bundles contain private agent state and are not
blinded-review materials. No semantic re-rating or full manual transcript review
was performed. Hash matches do not reverse previous failed qualifications.

G3/G3.1 history describes local prequalification/replay/model stress work; this
task did not establish dedicated server qualification batches for them. Other
local pressure/pilot/invalid runs are not claimed exhaustively recovered.
All recovered slugs belong to the four already-exposed base families; no new
independent confirmation family is established. Frozen registries remain intact.

Scripts: `scripts/g5_recover_legacy_exports.py`,
`scripts/g5_audit_recovered_exports.py`. These are outside the 350-test core
receipt. Checks here are byte hashes, original public-transcript algorithm and
old/current comparisons. No unrelated core regression was rerun. Keep the old
handoff snapshot; new files require a new snapshot, never overwriting old evidence.
