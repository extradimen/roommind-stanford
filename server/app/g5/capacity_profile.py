"""Offline measurements of archived IO and audit growth, not model quality."""
from collections import Counter
import math

from app.factorial_study import digest
from app.g5.artifacts import verify_source
from app.g5.world import canonical


def profile(source):
    verify_source(source)
    stages = {}
    for record in source["attempts"]:
        for item in record.get("model_io", []):
            stages.setdefault(record["stage"], []).append(item)
    def stats(values):
        values = sorted(values)
        return {"count": len(values), "total": sum(values), "max": values[-1] if values else None,
                "p95_nearest_rank": values[math.ceil(.95 * len(values)) - 1] if values else None}
    events = [{"seq": event["seq"], "event_bytes": len(canonical(event).encode("utf-8")),
               "audit_bytes": len(canonical(event["payload"]["audit"]).encode("utf-8"))} for event in source["events"]]
    raw = {"schema": "g5-offline-capacity-profile-v1", "source_sha256": source["sha256"],
        "world_id": source["world_id"], "common_budget": source["binding"].get("request_budget"),
        "source_json_bytes": len(canonical(source).encode("utf-8")), "events": events,
        "stage_io": {stage: {"request_bytes": stats([r["request_bytes"] for r in rows]),
            "response_bytes": stats([r["response_bytes"] for r in rows if r["response_bytes"] is not None]),
            "statuses": dict(Counter(r["status"] for r in rows))} for stage, rows in sorted(stages.items())},
        "qualification": "not_inferred", "limitations": "Bytes of canonical adapter JSON, not tokens or wire payload. Stored audit snapshots may grow superlinearly. Missing instrumentation is not zero IO. No timing/throughput or real-model quality claim."}
    return {**raw, "sha256": digest(raw)}


def main():
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    args = parser.parse_args()
    with open(args.source, encoding="utf-8") as stream:
        result = profile(json.load(stream))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
