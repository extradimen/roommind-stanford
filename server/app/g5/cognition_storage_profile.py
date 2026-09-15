"""Read-only lossless storage accounting; not a throughput/efficacy benchmark."""
from app.factorial_study import digest
from app.g5.artifacts import verify_source
from app.g5.cognition_storage import advance, canonical


def profile(source):
    verify_source(source)
    cursors, rows = {}, []
    for event in source["events"]:
        payload = event["payload"]
        actor, audit = payload["actor"], payload["audit"]
        state, count = advance(source["binding"], source["world_id"], actor, audit,
                               cursors.get(actor, ({}, None, 0)))
        cursors[actor] = (state, event["event_id"], count)
        if "cognition_state" in audit:
            rows.append({"seq": event["seq"], "actor": actor, "state_sha256": digest(state),
                "stored_bytes": len(canonical(audit["cognition_state"]).encode()),
                "logical_full_bytes": len(canonical(state).encode()),
                "mode": audit["cognition_state"].get("mode", "legacy-full")})
    stored, logical = sum(r["stored_bytes"] for r in rows), sum(r["logical_full_bytes"] for r in rows)
    raw = {"schema": "g5-cognition-storage-profile-v1", "evidence_use": "synthetic-engineering-only",
        "source_sha256": source["sha256"], "events": len(source["events"]), "states": rows,
        "stored_cognition_bytes": stored, "logical_full_cognition_bytes": logical,
        "saved_fraction": 1 - stored / logical if logical else None,
        "comparison": "same-run-canonical-state-vs-encoding-not-alternative-experiment",
        "source_bytes": len(canonical(source).encode()), "qualification": "not_inferred"}
    return {**raw, "sha256": digest(raw)}
