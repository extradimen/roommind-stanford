"""Public receipt sidecar, matched against server-owned session state.

This is provenance within the trusted application, not a cryptographic proof
against a database administrator. Never accept a receipt label by itself.
"""
from copy import deepcopy

from app.world.executor import KEY, world_view


def verified_receipts(task_config: dict, shared_state: dict, messages: list) -> list:
    if not task_config.get("simulation_executor"):
        return []
    containers = [shared_state.get("task_state") or {},
                  shared_state.get("_baseline_simulation") or {}]
    worlds = [state for state in containers if KEY in state]
    if len(worlds) > 1:
        raise ValueError("Ambiguous simulation receipt registries")
    if not worlds:
        return []
    registry = world_view(task_config, worlds[0])["requests"]
    evidence = []
    for message in messages:
        if message.get("speaker_type") != "npc":
            continue
        for receipt in registry.values():
            if (message.get("speaker_id") == receipt.get("actor_id")
                    and message.get("content") == receipt.get("content")
                    and isinstance(message.get("turn_id"), int)
                    and message["turn_id"] >= receipt["turn_id"]):
                evidence.append({"sequence_no": message.get("sequence_no"),
                                 "receipt": deepcopy(receipt),
                                 "scope": "internal_simulation_only"})
                break
    return evidence
