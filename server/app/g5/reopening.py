"""Version-bound reopening receipts. No lease and no exactly-once model-call claim.

Concurrent contenders may compute, but the world transaction publishes one result.
Input and terminal receipt are append-only; technical failure leaves input pending.
"""
from copy import deepcopy
from app.factorial_study import digest
from app.g5.world import Conflict

PROTOCOL = "identity-episode-version-next-scheduled-role-v2"


def validate(request):
    if not isinstance(request, dict) or set(request) != {"id", "episode", "version"}:
        raise ValueError("Reopening requires id, episode and version")
    if (not isinstance(request["id"], str) or not request["id"].strip()
            or len(request["id"]) > 128 or request["id"] != request["id"].strip()):
        raise ValueError("Invalid reopening identity")
    if any(type(request[k]) is not int or request[k] < 1 for k in ("episode", "version")):
        raise ValueError("Invalid reopening target")
    return deepcopy(request)


def inspect(snapshot, request, original, result, *, frozen=False):
    validate(request)
    _, binding = snapshot.definition(snapshot.world_id)
    if binding.get("stopping_policy", {}).get("reopening") != PROTOCOL:
        raise ValueError("Reliable reopening protocol not frozen")
    if original is not None and original != request:
        raise Conflict("Reopening identity reused with a different target")
    if result is not None:
        if original is None:
            raise ValueError("Receipt without registered request")
        if result.get("status") == "committed":
            event = result.get("event")
            events = snapshot.events(snapshot.world_id)
            if (not isinstance(event, dict) or event not in events
                    or event["seq"] != request["version"] + 1
                    or event["payload"]["audit"].get("reopen_request") != request):
                raise ValueError("Reopening receipt does not match the verified event log")
        elif result not in ({"status": "reopen_stale", "task_completed": None}, {"status": "reopen_frozen", "task_completed": None}):
            terminal(result)
        return deepcopy(result)
    if frozen:
        return {"status": "reopen_frozen", "task_completed": None}
    from app.g5.session_journal import replay
    spec, binding = snapshot.definition(snapshot.world_id)
    events = snapshot.events(snapshot.world_id)
    state = replay(digest([snapshot.world_id, binding]), spec["roles"], events)
    if (len(events) != request["version"] or state["episode"] != request["episode"]
            or state["status"] != "closed"):
        return {"status": "reopen_stale", "task_completed": None}
    return None


def terminal(result):
    if result not in ({"status": "reopen_declined", "task_completed": None},
                       {"status": "cutoff", "reason": "step_limit", "task_completed": False}):
        raise ValueError("Unsupported reopening terminal result")


def publication(request, expected_version, decision, audit):
    if (expected_version != request["version"] or audit.get("reopen_request") != request
            or decision.action != "speak" or (audit.get("session_annotation") or {}).get("kind") != "reopen"):
        raise ValueError("Reopening publication must match target and public consent")


class Resolved(Conflict):
    def __init__(self, result):
        super().__init__("Reopening already resolved")
        self.result = deepcopy(result)
