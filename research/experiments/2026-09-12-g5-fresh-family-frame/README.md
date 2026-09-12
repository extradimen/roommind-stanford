# G5 fresh-family pre-generation frame

This frame was frozen before dialogue generation or reference labeling. It
contains four new scenario families with two distinct world instances each:

- library space allocation;
- research data release;
- museum loan and conservation;
- community transit adjustment.

Each world has four registered roles, public scenario facts, role-authorized
simulation actions, explicit prerequisites, and structured executor effects.
The eight snapshot hashes are distinct. Frame SHA-256:
`766f9dfb14dae5fd9fa576481a9c950f3a52bd9dcba7157c06e27d4fdb9ce352`.

The companion role pack fixes one player role and three NPC roles per world,
uses condition-neutral private instructions, and is bound to the frame hash.
Role-pack SHA-256:
`61e102a9de723cd947e45516979dd6f4de79c0b97bf5ed1b42336c05a302d0a4`.

No dialogue has been generated, no reference label has been collected, and no
external execution is authorized by this artifact. It is a sampling-frame
input, not evidence of scorer accuracy or an architecture effect.

The frozen scorer-validation plan assigns one dialogue per world and balances
the four architecture arms at two dialogues each. It explicitly forbids an
architecture-effect inference: its only purpose is a 48-case (eight scenarios
times six dimensions) blinded development check of the scorer. A later
complete-block screen would require 32 separately frozen dialogues. Plan
SHA-256: `cc1d4fd9f89173fd2936e583a995d31e15143100e2f659911114de97b54357ec`.
The plan has null source/model bindings and grants no execution authority.

Pre-execution review found that v1 had insufficient private-information and
role-strategy variation. It was never executed and is preserved as superseded
development history. Use the separately frozen v2 directory for any future
validation proposal; do not overwrite or relabel these v1 artifacts.

The frame-only checkpoint passed 374/374 tests. After adding the role pack,
full SQLite/PostgreSQL acceptance passed 376/376 tests with no failures,
errors, or skips. Final receipt SHA-256:
`c96e9f682d9aaacf1c827f82595c891e7a3f2c0964a7343f051446f29aaa4639`.
