"""Offline source snapshot verification; no network, database writes or inference.

Source exports include private actor/auditor state. They are INTERNAL, not public
transcripts. Dialogue events are sealed; attempt/reopening metadata is a consistent
point-in-time snapshot and may acquire later recovery records in the live store.
"""
from copy import deepcopy
import json

from app.factorial_study import digest, verify_manifest
from app.g5.attempts import validate_record
from app.g5.freezing import make_freeze
from app.g5.measurement import require
from app.g5.world import Decision, Snapshot, resolve_payload, validate_spec


def source_bundle(world_id, spec, binding, events, attempts, reopening, seal):
    raw = {"schema": "g5-internal-source-snapshot-v1", "classification": "internal-audit-only",
        "metadata_scope": "consistent-snapshot-not-final-worker-quiescence", "world_id": world_id,
        "spec": spec, "binding": binding, "events": events, "attempts": attempts,
        "reopening": reopening, "seal": seal}
    result = {**deepcopy(raw), "sha256": digest(raw)}
    verify_source(result)
    return result


def verify_source(bundle, manifest=None):
    require(isinstance(bundle, dict) and set(bundle) == {"schema", "classification", "metadata_scope",
        "world_id", "spec", "binding", "events", "attempts", "reopening", "seal", "sha256"}, "Invalid source bundle")
    require(bundle["schema"] == "g5-internal-source-snapshot-v1"
        and bundle["classification"] == "internal-audit-only"
        and bundle["metadata_scope"] == "consistent-snapshot-not-final-worker-quiescence", "Invalid source scope")
    require(bundle["sha256"] == digest({k: v for k, v in bundle.items() if k != "sha256"}), "Source checksum mismatch")
    world_id, spec, binding = bundle["world_id"], bundle["spec"], bundle["binding"]
    require(isinstance(world_id, str) and bool(world_id), "World identity required")
    validate_spec(spec)
    events = bundle["events"]
    require(isinstance(events, list), "Event list required")
    previous, history, request_ids = digest([world_id, spec, binding]), [], set()
    for event in events:
        require(set(event) == {"seq", "event_id", "request_id", "request_hash", "payload"}
            and type(event["seq"]) is int and event["seq"] == len(history) + 1, "Invalid event sequence")
        require(isinstance(event["request_id"], str) and event["request_id"]
            and event["request_id"] not in request_ids, "Repeated event request identity")
        payload = event["payload"]
        actor, decision, audit = payload["actor"], payload["decision"], payload["audit"]
        require(event["request_hash"] == digest([actor, decision, audit]), "Event request checksum mismatch")
        require(event["event_id"] == digest([world_id, event["seq"], event["request_id"],
            event["request_hash"], previous, payload]), "Event hash chain mismatch")
        # ModelDecision adds evidence to Decision; preserve it verbatim while
        # independently recomputing the common executor's effects and visibility.
        require(set(decision) in ({"action", "content", "operation"},
            {"action", "content", "operation", "model_evidence_json"}), "Unknown decision representation")
        base = Decision(**{k: decision[k] for k in ("action", "content", "operation")})
        snapshot = Snapshot(world_id, spec, binding, history)
        resolved = resolve_payload(spec, snapshot.facts(world_id), actor, base, audit)
        resolved["decision"] = deepcopy(decision)
        require(resolved == payload, "Receipt/effects/visibility differ from registered executor")
        history.append(event)
        request_ids.add(event["request_id"])
        previous = event["event_id"]
    snapshot = Snapshot(world_id, spec, binding, events)
    require(bundle["seal"] is not None and bundle["seal"] == make_freeze(snapshot), "Missing or invalid final seal")
    require(isinstance(bundle["attempts"], list), "Attempt list required")
    for record in bundle["attempts"]:
        validate_record(record)
        require(record["actor"] in spec["roles"] and record["version"] <= len(events), "Attempt outside source world")
        if binding.get("request_budget") is not None:
            budget = binding["request_budget"]
            for item in record.get("model_io", []):
                require(item["budget_sha256"] == digest(budget), "Attempt capacity binding drift")
                if item["status"] == "received":
                    require(item["request_bytes"] <= budget["max_request_bytes"]
                        and item["response_bytes"] <= budget["max_response_bytes"], "Accepted IO exceeded budget")
                elif item["status"] == "request_capacity_exceeded":
                    require(item["request_bytes"] > budget["max_request_bytes"], "False request capacity failure")
                elif item["status"] == "response_capacity_exceeded":
                    require(item["response_bytes"] > budget["max_response_bytes"], "False response capacity failure")
    from app.g5.reopening import inspect, validate
    require(isinstance(bundle["reopening"], list), "Reopening list required")
    requests = {}
    for row in bundle["reopening"]:
        require(set(row) == {"request", "result"}, "Invalid reopening export")
        request = validate(row["request"])
        require(request["id"] not in requests, "Duplicate reopening export")
        requests[request["id"]] = row
        if row["result"] is not None:
            inspect(snapshot, request, request, row["result"], frozen=True)
    for event in events:
        request = event["payload"]["audit"].get("reopen_request")
        if request is not None:
            require(request["id"] in requests and requests[request["id"]]["request"] == request
                and (requests[request["id"]]["result"] or {}).get("event") == event,
                "Missing atomic reopening receipt")
    if manifest is not None:
        verify_manifest(manifest)
        assignment = binding["assignment"]
        require(type(assignment["ordinal"]) is int and 1 <= assignment["ordinal"] <= len(manifest["assignments"]), "Invalid assignment")
        require(binding["manifest_sha256"] == manifest["manifest_sha256"]
            and assignment == manifest["assignments"][assignment["ordinal"] - 1], "Source study mismatch")
        scenario = next(s for s in manifest["design"]["scenarios"] if s["id"] == assignment["scenario_id"])
        shared = manifest["design"]["arms"][assignment["arm"]]["shared"]
        require(digest(spec) == scenario["snapshot_sha256"]
            and digest(binding["stopping_policy"]) == shared["stopping_policy_sha256"], "Source world/stop drift")
        if "role_inputs" in binding:
            role_index = manifest["design"].get("scenario_role_inputs_sha256")
            expected_role_sha = (role_index[assignment["scenario_id"]]
                                 if role_index is not None else shared["role_inputs_sha256"])
            require(digest(binding["role_inputs"]) == expected_role_sha, "Role input drift")
        for name in ("components", "observation_window", "question_annotation", "session_annotation", "scheduling", "request_budget", "cognition_storage"):
            require(binding.get(name) == manifest["design"].get(name), "Source component drift: " + name)
    projections = {}
    scope = digest([world_id, binding])
    if "session" in binding:
        from app.g5.session_journal import replay
        projections["session"] = replay(scope, spec["roles"], events)
    if "questions" in binding:
        from app.g5.question_journal import replay
        projections["questions"] = replay(scope, spec["roles"], events)
    return {"world_id": world_id, "events": len(events), "attempt_records": len(bundle["attempts"]),
        "reopening_requests": len(requests), "seal_sha256": bundle["seal"]["sha256"],
        "source_sha256": bundle["sha256"], "projections": projections, "qualification": "not_inferred"}


def main():
    """Verify an explicitly supplied local snapshot, printing counts not private text."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("--manifest")
    args = parser.parse_args()
    with open(args.source, encoding="utf-8") as stream:
        bundle = json.load(stream)
    manifest = None
    if args.manifest:
        with open(args.manifest, encoding="utf-8") as stream:
            manifest = json.load(stream)
    result = verify_source(bundle, manifest)
    print(json.dumps({k: v for k, v in result.items() if k != "projections"}, sort_keys=True))


if __name__ == "__main__":
    main()
