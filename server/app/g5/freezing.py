"""Explicit final dialogue seal, distinct from reopenable session closure."""
from app.factorial_study import digest


def make_freeze(snapshot):
    spec, binding = snapshot.definition(snapshot.world_id)
    if binding.get("protocol") != "g5-local-reference-loop-v1":
        raise ValueError("Only explicit G5 reference worlds can be frozen")
    events = snapshot.events(snapshot.world_id)
    if "cognition_storage" in binding:
        from app.g5.cognition_storage import replay
        replay(binding, snapshot.world_id, events)
    limit = binding["stopping_policy"]["max_steps"]
    if len(events) > limit:
        raise ValueError("World exceeded its frozen step budget")
    reason = "step_limit" if len(events) == limit else None
    if reason is None and "session" in binding:
        from app.g5.session_journal import replay
        if replay(digest([snapshot.world_id, binding]), spec["roles"], events)["status"] == "closed":
            reason = "session_closed"
    if reason is None:
        raise ValueError("Running dialogue cannot be sealed")
    raw = {"schema": "g5-final-dialogue-seal-v1", "world_id": snapshot.world_id,
        "assignment": binding["assignment"],
        "manifest_sha256": binding["manifest_sha256"], "binding_sha256": digest(binding),
        "spec_sha256": digest(spec), "version": len(events), "events_sha256": digest(events),
        "stop_reason": reason, "task_success": "not_inferred"}
    return {**raw, "sha256": digest(raw)}
