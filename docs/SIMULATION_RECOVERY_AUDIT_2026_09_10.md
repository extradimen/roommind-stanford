# Recovery and input-binding checkpoint

## Verified locally

The real application ORM models were exercised in a unique PostgreSQL schema:
receipt state and session messages survive commit/reconnect, both roll back on
an aborted transaction, startup schedules only eligible batches, interrupted
evaluation is queued, and completed evaluation results remain unchanged.
The fixture schema was removed; no existing application tables were modified.
Scheduling was mocked: this is not an end-to-end worker restart test.

New batches now capture scenario, world contract, role cards, and dispatch-rule
inputs with a digest. Checks run before session creation, before each autonomous
step and before batch evaluation. Legacy batches without bindings are untouched.
A real ORM test verified that changing the world contract fails this check.

18 component tests and the historical 135-file inventory verification pass.

## Blocking recovery defect discovered

`_run_batch` requeues interrupted running cells, and `_execute_run` creates a new
session. The implementation explicitly describes rerunning as new sessions.
Therefore this is NOT continuation of the original committed dialogue. Previous
claims about resumability must distinguish re-execution from continuation.

Before a new qualification: implement original-session continuation, preserve
committed turns and trace/history, verify failure boundaries and avoid duplicate
turn execution. Do not interpret the startup scheduling test as this evidence.

No deployment or new batch has started. Input binding is a drift detector, not
an immutable database snapshot against concurrent administrative writes.
