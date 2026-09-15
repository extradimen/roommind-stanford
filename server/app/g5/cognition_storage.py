"""Lossless, explicitly opted-in cognition audit storage; never rewrites events.

Hashes refer to canonical JSON values, not Python equality (True != 1 here).
No summaries, pruning, external blobs or cross-role dictionaries are used.
"""
from copy import deepcopy
import json

from app.factorial_study import ARMS, digest


PROTOCOL = {"schema": "g5-lossless-cognition-delta-v1", "checkpoint_interval": 16,
            "encoding": "canonical-json-tree-prefix-v1"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def validate_spec(value):
    if canonical(value) != canonical(PROTOCOL):
        raise ValueError("Unknown cognition storage protocol")


def _delta(old, new):
    if canonical(old) == canonical(new):
        return ["keep"]
    replacement = ["set", new]
    candidate = replacement
    if isinstance(old, dict) and isinstance(new, dict):
        candidate = ["map", sorted(set(old) - set(new)),
                     {key: _delta(old[key], new[key]) if key in old else ["set", new[key]]
                      for key in sorted(new) if key not in old or canonical(old[key]) != canonical(new[key])}]
    elif isinstance(old, list) and isinstance(new, list):
        prefix = 0
        while prefix < min(len(old), len(new)) and canonical(old[prefix]) == canonical(new[prefix]):
            prefix += 1
        candidate = ["prefix", prefix, new[prefix:]]
    return candidate if len(canonical(candidate).encode()) < len(canonical(replacement).encode()) else replacement


def _apply(old, patch):
    if not isinstance(patch, list) or not patch:
        raise ValueError("Invalid cognition patch")
    op = patch[0]
    if op == "keep" and len(patch) == 1:
        return deepcopy(old)
    if op == "set" and len(patch) == 2:
        return deepcopy(patch[1])
    if op == "prefix" and len(patch) == 3 and isinstance(old, list):
        count, tail = patch[1:]
        if type(count) is int and 0 <= count <= len(old) and isinstance(tail, list):
            return deepcopy(old[:count] + tail)
    if op == "map" and len(patch) == 3 and isinstance(old, dict):
        deleted, changed = patch[1:]
        if (isinstance(deleted, list) and all(isinstance(k, str) for k in deleted)
                and len(set(deleted)) == len(deleted) and set(deleted) <= set(old)
                and isinstance(changed, dict) and not set(deleted) & set(changed)):
            result = {k: deepcopy(v) for k, v in old.items() if k not in deleted}
            for key, item in changed.items():
                if key not in old and (not isinstance(item, list) or len(item) != 2 or item[0] != "set"):
                    raise ValueError("New cognition field must be explicit")
                result[key] = _apply(old.get(key), item)
            return result
    raise ValueError("Invalid cognition patch operation")


def encode(state, previous, *, scope, actor, base_event, ordinal):
    if not isinstance(state, dict) or type(ordinal) is not int or ordinal < 1:
        raise ValueError("Cognition state/ordinal required")
    canonical(state)
    if state.get("owner", actor) != actor or state.get("scope", scope) != scope:
        raise ValueError("Cognition logical state identity mismatch")
    if "configuration" in previous and canonical(state.get("configuration")) != canonical(previous["configuration"]):
        raise ValueError("Cognition logical configuration changed")
    patch = _delta(previous, state)
    checkpoint = (ordinal - 1) % PROTOCOL["checkpoint_interval"] == 0 or len(canonical(patch).encode()) >= len(canonical(state).encode())
    return deepcopy({"schema": PROTOCOL["schema"], "scope": scope, "actor": actor,
        "ordinal": ordinal, "base_event": base_event, "base_sha256": digest(previous),
        "state_sha256": digest(state), "mode": "checkpoint" if checkpoint else "delta",
        "data": state if checkpoint else patch})


def decode(record, previous, *, scope, actor, base_event, ordinal):
    if not isinstance(record, dict) or set(record) != {"schema", "scope", "actor", "ordinal",
            "base_event", "base_sha256", "state_sha256", "mode", "data"}:
        raise ValueError("Invalid cognition storage record")
    if (record["schema"] != PROTOCOL["schema"] or record["scope"] != scope or record["actor"] != actor
            or type(record["ordinal"]) is not int or record["ordinal"] != ordinal
            or record["base_event"] != base_event or record["base_sha256"] != digest(previous)):
        raise ValueError("Cognition storage base/identity mismatch")
    if record["mode"] == "checkpoint":
        result = deepcopy(record["data"])
    elif record["mode"] == "delta":
        result = _apply(previous, record["data"])
    else:
        raise ValueError("Unknown cognition storage mode")
    if not isinstance(result, dict) or record["state_sha256"] != digest(result):
        raise ValueError("Cognition reconstruction checksum mismatch")
    # One deterministic representation per state, including periodic checkpoints.
    if canonical(record) != canonical(encode(result, previous, scope=scope, actor=actor,
                                             base_event=base_event, ordinal=ordinal)):
        raise ValueError("Noncanonical cognition storage record")
    return result


def advance(binding, world_id, actor, audit, cursor):
    state, base_event, count = cursor
    if "cognition_storage" not in binding:
        return deepcopy(audit.get("cognition_state", {})), count
    validate_spec(binding["cognition_storage"])
    called = audit.get("cognition_called")
    if type(called) is not bool or ("cognition_state" in audit) != called:
        raise ValueError("Cognition storage invocation mismatch")
    if "assignment" in binding and called != ARMS[binding["assignment"]["arm"]]["cognition"]:
        raise ValueError("Cognition storage condition mismatch")
    if not called:
        return {}, count
    return decode(audit["cognition_state"], state, scope=digest([world_id, binding]), actor=actor,
                  base_event=base_event, ordinal=count + 1), count + 1


def replay(binding, world_id, events, actor=None):
    """Reconstruct each actor independently; optional actor filters private bodies."""
    if "cognition_storage" in binding:
        validate_spec(binding["cognition_storage"])
    else:
        # Legacy read behavior: select the latest snapshot, no repeated copying.
        latest = {}
        for event in events:
            owner = event["payload"]["actor"]
            if actor is None or owner == actor:
                latest[owner] = (event["payload"]["audit"].get("cognition_state", {}), event["event_id"], 0)
        return deepcopy(latest)
    cursors = {}
    for event in events:
        owner = event["payload"]["actor"]
        if actor is not None and owner != actor:
            continue
        state, count = advance(binding, world_id, owner, event["payload"]["audit"],
                               cursors.get(owner, ({}, None, 0)))
        cursors[owner] = (state, event["event_id"], count)
    return cursors


def validate_commit(binding, world_id, events, actor, audit):
    if "cognition_storage" in binding:
        cursor = replay(binding, world_id, events, actor).get(actor, ({}, None, 0))
        advance(binding, world_id, actor, audit, cursor)
