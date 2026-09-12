# G5 independent human-reference review preflight v2

This directory is a local preparation artifact. It does not establish that any reviewer is
human or independent, and no person has been contacted or assigned.

The panel contains the same 48 development-calibration cases. Two reviewer packets use
different randomized orders and aliases, exclude source run IDs, source condition labels,
and all v1–v4 model predictions. Reviewers classify `clear`, `violation`, `uncertain`, or
`not_applicable`, cite immutable evidence IDs, and record a separate post-label condition
guess so residual blinding can be measured. A distinct third person adjudicates disagreements
only; original independent labels remain preserved.

Only the assigned reviewer packet and its response template may be distributed to that
reviewer. `coordinator.json`, the other packet and prior predictions must remain withheld.
External distribution and human review require separate explicit authorization.

Frozen local preflight facts:

- cases per reviewer: 48
- independent reviewer slots: 2
- disagreement-only adjudicator slots: 1
- manifest SHA-256: `6f3ccafb750c921bd7874e3af2123c932b58c7c0d2e36b3f8105dabc7b287adb`
- full SQLite/PostgreSQL acceptance: 366 passed, 0 failed/error/skipped
- acceptance SHA-256: `f8f474e3caba2dc662272502eee535b4a701233ddff1b03ad7bb06fc4e9fdc07`
- human reviewers assigned: 0
- human annotations collected: 0
