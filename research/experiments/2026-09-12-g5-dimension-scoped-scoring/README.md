# G5 dimension-scoped semantic scoring

Date: 2026-09-12. Status: local implementation; no external execution.

The first condition-neutral semantic contract improved epistemic and interaction
diagnosis on reused development material but reduced aggregate agreement with a
single Codex expert pass. Case-level inspection showed that interaction rules
were sometimes applied to role-strategy judgments and that date conflicts could
still be missed.

The successor contract therefore has one common evidence model and six mutually
explicit dimension scopes. Every request receives only its requested scope.
The prompt forbids transferring a defect from another dimension unless that
scope explicitly makes it relevant. Legacy short dimension names are mapped to
their canonical G5 names. The complete v1 contract and prompt remain available
for byte-for-byte reconstruction of the already-frozen external requests.

- v1 semantic contract SHA-256:
  `ed9217e91cd502acabc27ae0c72f64b9496aebab5d5462af1bca06c78e6774f7`
- dimension-scoped v2 contract SHA-256:
  `86157439752f7dba607de9af1d74acfa3ece4f997ed89f775d358bc6646f684d`
- targeted regression: 26/26 passed;
- full SQLite/PostgreSQL acceptance: 371/371 passed with no failures, errors,
  or skips; receipt SHA-256
  `f6ab6e36df0009cd7c23e8eef7ccd7a391365a0f0f6d1823420f673ce218198f`.

No valid fresh holdout can be carved from the recovered legacy material. The
registered holdout audit covers eight families, all with prior development
exposure; `registered_exposure_free` is false and semantic novelty is not
established. Audit SHA-256:
`c4dce0186cf37adf160eaba1bf03ad544cdf37e748f7c1a594d3a60841703a33`.

Consequently the v2 contract must not be tuned or scored again on those 48
cases. Its next empirical use requires newly registered scenario families,
frozen before dialogue generation or reference labeling.
