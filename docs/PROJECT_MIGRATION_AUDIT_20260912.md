# Project directory migration audit — 2026-09-12

The default project root is `/Users/michaelwang/Documents/ChatGPT/RoomMind-Stanford`.
The older `/Users/michaelwang/Documents/ChatGPT/RoomMind` repository is a separate
checkout and was inspected read-only. No files were written there.

## File and evidence integrity

- Revision: `f617c8697bc9a50b96514d89b51205a840a9c28c`.
- All 1,841 tracked files exist; tracked content is unchanged from this commit.
- Git object integrity check passed (unreferenced objects were retained).
- All 130 implementation/test files exactly match the existing 395-test v4
  acceptance receipt; receipt checksum, complete source set and test accounting
  also validate through `app.g5.local_handoff.acceptance`.
- All 1,209 research files in the latest pre-migration handoff
  `G5_LOCAL_HANDOFF_20260912_FRESH_EXECUTION_V2_FINAL.json` match their hashes.
- Current research inventory contains 1,222 files. All 12 entries in archived
  `SHA256SUMS` files validate. The failed v2 and v3 SQLite databases pass read-only
  integrity checks; execution-binding hashes and the one v3 sealed source validate.
- Read-only SSH confirms the stopped v3 server binding, database, log and sealed
  source match the migrated local archive byte-for-byte.
- No broken symlinks were found. Historical receipt text retains its original
  execution paths; changing those would alter historical evidence.

This establishes consistency with the available Git and hash inventories, not an
independent pre-move backup of every untracked file or scientific qualification.

## Local environment repair

The three moved virtual environments retained absolute paths to the former nested
directory. Replaced that prefix in 38 generated text files under `.venv`,
`.venv-test` and `.venv312` (entrypoint shebangs, activation scripts and environment
metadata). No installed package versions or research source files changed.

All three interpreters resolve to the new project. `.venv312` activation, pip,
required runtime imports and `pip check` pass. The v4 runner help entrypoint works.
Both client and admin production builds pass, with existing large-chunk warnings.

## Migration regression

Full G5 acceptance passed 395/395 tests from the new directory, with zero failures,
errors or skips and unchanged source. It used a newly initialized isolated local
PostgreSQL 16 database with a private Unix socket, stopped after the run. New
receipt: `G5_LOCAL_ACCEPTANCE_20260912_POST_MIGRATION.json`, SHA-256
`699fdd51c23bbb5acf306c81b01cae6bb50456d89db4c81fdea06634b292cbf8`.
New handoff: `G5_LOCAL_HANDOFF_20260912_POST_MIGRATION.json`. Prior receipts and
research artifacts are preserved.

## Continuation boundary

The staging checkout was safely advanced to
`f617c8697bc9a50b96514d89b51205a840a9c28c`. Existing server configuration
changes, backups and v2/v3 outputs remained in place.

Both old G5 heartbeat automations are paused. One contains the obsolete local
path, but cannot run while paused; it must not be reactivated unchanged. Any
continuing v4 monitor must target this task and the new project directory.

V4 used exactly eight development assignments with `ollama/gpt-oss:120b`, low
reasoning, max 16 steps, max one session revision and at most two plan-validation
corrections. Its later structured-output failure is recorded below.

## Continuation outcome

After migration acceptance passed, the first push attempt was rejected by automatic
approval review before execution. The user then explicitly authorized the archived
internal experimental source, SQLite and logs, the GitHub destination, staging
deployment and v4 execution. Commit `f617c86` was pushed to
`https://github.com/extradimen/roommind-stanford.git`; staging fast-forwarded from
`5f2124b` after confirming its local configuration and untracked experiment archives
would not be overwritten. Focused staging tests passed 24/24 and service readiness
passed. The v4 run started in a new `2026-09-12-g5-fresh-family-v4-online` directory
with binding `3fd2adfe9c3eeea8942c2b69dd957422cb82034e141838ab6700826f30f21868`.
V4 later stopped after 3/8 sealed dialogues because a question annotation had
invalid targets. The process is stopped, its 63-event SQLite state is intact, and
its artifacts were copied to the migrated project and verified. A v5 bounded
question-annotation repair passed 400/400 local tests including PostgreSQL. The
migration audit, receipts, failed archive and v5 recovery remain local pending a
new external-action decision.
