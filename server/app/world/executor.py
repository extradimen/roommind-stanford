"""Bounded internal simulation. No network, shell, or real-world side effects.

The same contract runs in both experimental conditions. Its state contains
only declared public world facts, never RoomMind's plans or governance state.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

KEY = "simulation_world"
SCHEMA = "roommind-simulation-executor-v1"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def contract(task_config: dict) -> dict:
    raw = task_config.get("simulation_executor") or {}
    if not raw:
        return {}
    if raw.get("schema") != SCHEMA:
        raise ValueError("Unknown simulation executor schema")
    if not isinstance(raw.get("initial_facts", {}), dict):
        raise ValueError("initial_facts must be an object")
    actions = raw.get("actions")
    if not isinstance(actions, dict):
        raise ValueError("actions must be an object")
    for name, action in actions.items():
        if (not isinstance(action, dict) or not isinstance(action.get("actors"), list)
                or not action["actors"] or not all(isinstance(a, str) and a for a in action["actors"])
                or not isinstance(action.get("field"), str) or not action["field"]):
            raise ValueError(f"Invalid simulation action: {name}")
        if action.get("outcome", "success") not in {"success", "failed"}:
            raise ValueError(f"Invalid configured outcome: {name}")
        if not isinstance(action.get("requires", {}), dict):
            raise ValueError(f"Invalid prerequisites: {name}")
        if not isinstance(action.get("parameters", {}), dict):
            raise ValueError(f"Invalid parameters: {name}")
        if "value" not in action:
            raise ValueError(f"Missing result value: {name}")
    return deepcopy(raw)


def world_view(task_config: dict, state: dict) -> dict:
    cfg = contract(task_config)
    if not cfg:
        return {}
    fingerprint = hashlib.sha256(canonical(cfg).encode()).hexdigest()
    saved = state.get(KEY)
    if saved is not None and saved.get("contract_sha256") != fingerprint:
        raise ValueError("Simulation contract changed during a session")
    return deepcopy(saved or {
        "schema": SCHEMA, "contract_sha256": fingerprint,
        "facts": deepcopy(cfg.get("initial_facts", {})), "requests": {},
    })


def prompt(task_config: dict, state: dict, actor_id: str) -> str:
    cfg = contract(task_config)
    if not cfg:
        return ""
    view = world_view(task_config, state)
    available = {name: action for name, action in cfg["actions"].items()
                 if actor_id in action["actors"]}
    return (
        "Internal simulated world (no real systems are affected). "
        "Only executor receipts establish executed actions. To request one, "
        'return action="execute" and simulation_action={"request_id":"stable unique id",'
        '"operation":"declared operation","parameters":{}}. '
        "Use only your authorized operations and declared parameters. "
        "Keep the same request_id when retrying the same request. "
        "The execute action extends the ordinary action enum below. "
        "The engine publishes the receipt instead of your draft. "
        "A blocked/failed receipt does not establish success.\n"
        + canonical({"actions": available, "facts": view["facts"]})
    )


def execute(task_config: dict, state: dict, *, actor_id: str,
            request: dict, turn_id: int) -> dict:
    cfg = contract(task_config)
    if not cfg:
        raise ValueError("Simulation executor is disabled")
    if not isinstance(request, dict):
        raise ValueError("Simulation request must be an object")
    rid = request.get("request_id")
    if not isinstance(rid, str) or not rid.strip() or len(rid) > 160:
        raise ValueError("A bounded nonempty request_id is required")
    operation = request.get("operation")
    parameters = request.get("parameters", {})
    if not isinstance(operation, str) or not isinstance(parameters, dict):
        raise ValueError("Invalid operation or parameters")
    payload = {"actor_id": actor_id, "operation": operation, "parameters": parameters}
    request_hash = hashlib.sha256(canonical(payload).encode()).hexdigest()
    view = world_view(task_config, state)
    key = canonical([actor_id, rid])
    prior = view["requests"].get(key)
    if prior:
        if prior["request_sha256"] != request_hash:
            raise ValueError("request_id reused with different parameters")
        return deepcopy(prior)
    action = cfg["actions"].get(operation)
    reason = ""
    status = "blocked"
    if action is None:
        reason = "unknown_operation"
    elif actor_id not in action["actors"]:
        reason = "actor_not_authorized"
    elif canonical(parameters) != canonical(action.get("parameters", {})):
        reason = "invalid_parameters"
    elif any(k not in view["facts"] or canonical(view["facts"][k]) != canonical(v)
             for k, v in action.get("requires", {}).items()):
        reason = "prerequisites_not_met"
    else:
        status = action.get("outcome", "success")
        reason = "executed_in_simulation" if status == "success" else "configured_failure"
    result = {
        "result_id": "sim-" + hashlib.sha256(
            canonical([view["contract_sha256"], actor_id, rid, request_hash]).encode()
        ).hexdigest(),
        "request_id": rid, "request_sha256": request_hash,
        "actor_id": actor_id, "operation": operation,
        "parameters": deepcopy(parameters), "turn_id": turn_id,
        "status": status, "reason": reason,
        "field": action["field"] if action and actor_id in action["actors"] else "",
        "value": deepcopy(action["value"]) if status == "success" else None,
    }
    result["content"] = (
        f"[Simulation receipt {result['result_id']}] {operation}: {status}; {reason}."
        + (f" {result['field']} = {canonical(result['value'])}." if status == "success" else "")
    )
    if status == "success":
        view["facts"][result["field"]] = deepcopy(result["value"])
    view["requests"][key] = deepcopy(result)
    state[KEY] = view
    return result


def request_execution(task_config: dict, state: dict, *, actor_id: str,
                      request: dict, turn_id: int) -> dict:
    """Reject malformed model requests without failing the dialogue.

    Validate frozen configuration outside the catch: changed contracts remain
    experiment errors, not something an agent may repair or silently ignore.
    """
    world_view(task_config, state)
    try:
        return execute(task_config, state, actor_id=actor_id, request=request, turn_id=turn_id)
    except (ValueError, TypeError) as error:
        receipt = {"actor_id": actor_id, "turn_id": turn_id, "status": "blocked",
                   "reason": "invalid_request", "detail": str(error),
                   "content": "[Simulation receipt] Request blocked: invalid request; no action executed."}
        state.setdefault("simulation_request_rejections", []).append(deepcopy(receipt))
        return receipt
