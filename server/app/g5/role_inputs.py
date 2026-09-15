"""Explicit, frozen role cards; do not infer disclosure rules from old prompts.

Knowledge/evidence stays in world facts. These cards provide public identity and
private behavior instructions. Scenario authors must classify those inputs.
"""
from copy import deepcopy


def validate_inputs(inputs, roles):
    if not isinstance(inputs, dict) or set(inputs) != set(roles):
        raise ValueError("Exactly the registered role cards are required")
    for actor, card in inputs.items():
        if not isinstance(card, dict) or set(card) != {"public", "private"}:
            raise ValueError("Role card needs separate public/private sections")
        public, private = card["public"], card["private"]
        if not isinstance(public, dict) or set(public) != {"name", "job_title", "side", "kind"}:
            raise ValueError("Invalid public role identity")
        if public["kind"] not in ("npc", "player"):
            raise ValueError("Role kind must explicitly identify NPC or player")
        if not all(isinstance(public[k], str) and public[k].strip() for k in public):
            raise ValueError("Public identity must contain strings")
        if not isinstance(private, dict) or set(private) != {"persona", "goals", "instructions"}:
            raise ValueError("Invalid private behavior specification")
        if not isinstance(private["persona"], str) or not isinstance(private["instructions"], str):
            raise ValueError("Private instructions must be strings")
        if not isinstance(private["goals"], list) or not all(isinstance(x, str) for x in private["goals"]):
            raise ValueError("Goals must be a string list")


def actor_view(view, inputs):
    validate_inputs(inputs, view["participants"])
    actor = view["actor"]
    if actor not in inputs:
        raise ValueError("Unknown role")
    return {**deepcopy(view),
            "public_roster": {role: deepcopy(card["public"]) for role, card in inputs.items()},
            "own_role": deepcopy(inputs[actor])}
