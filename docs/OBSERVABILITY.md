# RoomMind observability and analysis exports

## Structured telemetry

The API writes structured events to `logs/telemetry.log`. The file rotates at
50 MB and keeps ten backups. Each line begins with `ROOMMIND_EVENT` followed by
one JSON object.

Recorded event families include:

- HTTP request start, finish, status, duration, request id, and exception type
- batch run, stage, turn, retry, stop, evaluation, and failure events
- LLM provider/model, attempt, token budget, input/output character counts,
  latency, finish reason, token usage when supplied, and transport/HTTP errors
- every public dialogue message with session, turn, sequence, speaker, source,
  timestamp context, content, emotion, and gesture

Authentication headers, API keys, and provider authorization values are never
logged. Public dialogue content is logged because the feature is intended for
research debugging; access to the server `logs/` directory should therefore be
restricted and normal retention rules should be applied.

Useful commands:

```bash
tail -f logs/telemetry.log
grep '"event": "llm.request.transport_error"' logs/telemetry.log
grep 'SESSION_UUID' logs/telemetry.log
grep '"event": "batch.run.failed"' logs/telemetry.log
```

## Session and batch exports

The existing session JSON remains the richest single-session artifact. It now
also contains `performance_trace`, including per-turn duration and LLM events.

The Batch Experiments page provides:

- **Download CSV**: one result row per run
- **All dialogue CSV**: one public utterance per row
- **All dialogue JSON**: every available session transcript, evaluation,
  performance trace, run error, and run result
- **Human review JSON**: optional condition-hidden review packets

Failed and still-running sessions are included in dialogue exports, so partial
work remains available for post-mortem analysis.
