# Batch experiments

The client route `/batch-experiments` creates persistent server-side comparison jobs.
Closing the browser does not stop a job. Queued or running jobs are resumed after an
API restart; a run interrupted by the restart is repeated as a fresh session and the
abandoned session is not included in the result table.

## Experimental unit

One result row is one independent combination of:

- scenario;
- condition (`roommind` or `baseline`);
- repetition number.

Both conditions use the same scenario and a balanced AI player. The order of cells
is randomized with the recorded seed. The default concurrency is 2 and the server
hard limit is 4. This prevents unbounded LLM traffic while allowing practical batch
throughput. For final studies, keep concurrency, maximum turns, model configuration,
temperature, randomization seed, and evaluator model constant across conditions.

## Persistence and failure handling

The batch, each run, the generated session UUID, the external evaluation, and any
error are stored in PostgreSQL. Each dialogue turn is committed independently. A
failed run is recorded as a failed row and does not abort other cells. CSV exports
include completed, failed, and cancelled rows so exclusions remain auditable.

## Analysis

The CSV contains explicit `condition`, `scenario_id`, `repetition`, and `session_uuid`
columns plus completion, leakage, contradiction, repetition, responsibility, role,
and closure metrics. Statistical analysis should treat failed infrastructure runs as
missing with a documented exclusion rule; do not silently convert them into task
failures. Task failures that complete normally but fail external validation remain
valid observations.
