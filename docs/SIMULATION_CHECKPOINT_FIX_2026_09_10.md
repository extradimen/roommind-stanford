# Original-session continuation fix

This supersedes the recovery implementation defect recorded earlier today,
not the historical experiment results. Changes are local, not deployed.

- Interrupted runs retain their session UUID and original start timestamp.
- The batch marker and session completed-turn counter are checked before reuse;
  a missing or mismatched session fails closed instead of creating a replacement.
- Existing performance history is restored; recovery events are retained in the
  final dialogue result. Terminal sessions skip dialogue generation.
- A worker cancellation requeues its checkpoint unless the parent batch was
  explicitly cancelled. Explicit dialogue retries retain their separate behavior.

## Evidence

An isolated PostgreSQL test ran the actual `_execute_run` with a simulated LLM
step: resumed at turn 2, committed that turn, interrupted at turn 3, and resumed
again at turn 3. No session creation occurred, exactly two messages remained,
the original receipt state survived, and both recovery entries were retained.
Only the fixture's unique schema was removed after testing.

This tests coroutine cancellation and real ORM transactions, not an OS kill,
live-provider retries, concurrent workers, or a full staging restart. Those
limits remain explicit. New qualification has not started.
