"""Offline G5 contracts, NOT a dialogue backend or evidence of runtime parity.

Legacy two-condition manifests and generation constants are untouched.
Hashes bind separately archived specifications; their adequacy and actual
runtime compliance must be independently checked before a study runs.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
import re
from typing import Any

PROTOCOL = "g5-cognition-governance-factorial-v1"
ARMS = {
    "A": {"cognition": False, "governance": False},
    "B": {"cognition": True, "governance": False},
    "C": {"cognition": False, "governance": True},
    "D": {"cognition": True, "governance": True},
}
SHARED_FIELDS = {
    "world_sha256", "role_inputs_sha256", "base_scheduler_sha256",
    "observation_policy_sha256", "player_policy_sha256", "model_bindings_sha256",
    "tool_permissions_sha256", "stopping_policy_sha256", "evaluator_plan_sha256",
}
HASH = re.compile(r"[0-9a-f]{64}\Z")
REVISION = re.compile(r"[0-9a-f]{40}\Z")


def digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                     allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _hash(value: Any) -> bool:
    return isinstance(value, str) and bool(HASH.fullmatch(value))


def validate_design(design: dict[str, Any]) -> None:
    """Reject ambiguous assignments, unequal declared inputs and family reuse."""
    _require(isinstance(design, dict), "Design must be an object")
    expected = {"protocol", "source_revision", "stage", "scenarios", "used_families",
                "repetitions", "order_seed", "sampling_seed_policy", "arms",
                "analysis_plan_sha256", "sample_size_plan_sha256"}
    _require(expected <= set(design) and set(design) <= expected | {"components", "question_annotation", "scheduling", "session_annotation", "observation_window", "request_budget", "cognition_storage", "scenario_role_inputs_sha256"}, "Missing or unknown design fields")
    if "cognition_storage" in design:
        from app.g5.cognition_storage import validate_spec
        validate_spec(design["cognition_storage"])
    if "request_budget" in design:
        from app.g5.capacity import verify_declared_budget
        _require("components" in design, "Request budgets require strict component declarations")
        for key in ("components", "question_annotation", "session_annotation"):
            if key in design:
                verify_declared_budget(design[key], design["request_budget"])
    if "observation_window" in design:
        _require(isinstance(design["observation_window"], dict) and bool(design["observation_window"]),
                 "Explicit common observation window required")
    if "session_annotation" in design:
        _require(isinstance(design["session_annotation"], dict) and bool(design["session_annotation"]),
                 "Explicit shared session annotation specification required")
    if "scheduling" in design:
        _require(isinstance(design["scheduling"], dict) and bool(design["scheduling"]),
                 "Explicit shared scheduling specification required")
    if "question_annotation" in design:
        _require(isinstance(design["question_annotation"], dict) and bool(design["question_annotation"]),
                 "Explicit shared question annotation specification required")
    if "components" in design:
        components = design["components"]
        _require(isinstance(components, dict) and set(components) == {"policy", "cognition", "governance"},
                 "All three component specifications are required")
        _require(all(isinstance(value, dict) and value for value in components.values()),
                 "Nonempty component specifications required")
    _require(design["protocol"] == PROTOCOL, "Wrong study protocol")
    _require(isinstance(design["source_revision"], str)
             and bool(REVISION.fullmatch(design["source_revision"])), "Invalid source revision")
    _require(design["stage"] in ("exploration", "screening", "confirmation"), "Invalid stage")
    _require(type(design["repetitions"]) is int and design["repetitions"] > 0,
             "Repetitions must be a positive integer")
    _require(type(design["order_seed"]) is int, "Order seed must be an integer")
    _require(design["sampling_seed_policy"] in ("provider_seed_recorded", "unsupported_recorded"),
             "Record provider sampling support separately from order randomization")
    for field in ("analysis_plan_sha256", "sample_size_plan_sha256"):
        _require(_hash(design[field]), f"Invalid {field}")

    scenarios = design["scenarios"]
    _require(isinstance(scenarios, list) and bool(scenarios), "Scenarios must be a nonempty list")
    ids, families = set(), set()
    for item in scenarios:
        _require(isinstance(item, dict) and set(item) == {"id", "family", "snapshot_sha256"},
                 "Invalid scenario record")
        _require(all(isinstance(item[k], str) and item[k]
                     and item[k] == item[k].strip() for k in ("id", "family")),
                 "Scenario ID and family must be nonempty, whitespace-trimmed strings")
        _require(item["id"] not in ids, "Duplicate scenario ID")
        _require(_hash(item["snapshot_sha256"]), "Invalid snapshot hash")
        ids.add(item["id"])
        families.add(item["family"])
    used = design["used_families"]
    _require(isinstance(used, list)
             and all(isinstance(x, str) and x and x == x.strip() for x in used),
             "Used families must be an explicit list")
    _require(len(set(used)) == len(used), "Duplicate used family")
    if design["stage"] in ("screening", "confirmation"):
        _require(not families.intersection(used), "Held-out stage reuses a previously exposed family")
    scenario_roles = design.get("scenario_role_inputs_sha256")
    if scenario_roles is not None:
        _require(isinstance(scenario_roles, dict) and set(scenario_roles) == ids
                 and all(_hash(value) for value in scenario_roles.values()),
                 "Scenario role hashes must cover every scenario exactly")

    arms = design["arms"]
    _require(isinstance(arms, dict) and set(arms) == set(ARMS), "Exactly A/B/C/D are required")
    shared = None
    for name, switches in ARMS.items():
        arm = arms[name]
        _require(isinstance(arm, dict) and set(arm) == {"cognition", "governance", "shared"},
                 f"Unknown or missing arm fields: {name}")
        _require(all(type(arm[k]) is bool and arm[k] == v for k, v in switches.items()),
                 f"Incorrect mechanism switches: {name}")
        profile = arm["shared"]
        _require(isinstance(profile, dict) and set(profile) == SHARED_FIELDS,
                 f"Incomplete shared profile: {name}")
        _require(all(_hash(value) for value in profile.values()),
                 f"Invalid shared profile hashes: {name}")
        if shared is None:
            shared = profile
        _require(profile == shared, f"Non-factor difference in arm {name}")
        if scenario_roles is not None:
            _require(profile["role_inputs_sha256"] == digest(scenario_roles),
                     "Shared role-input index hash differs from scenario mapping")
        if "scheduling" in design:
            _require(profile["base_scheduler_sha256"] == digest(design["scheduling"]),
                     "Scheduling specification does not match frozen hash")
        if "observation_window" in design:
            _require(profile["observation_policy_sha256"] == digest(design["observation_window"]),
                     "Observation window differs from shared frozen hash")
        if "components" in design:
            _require(profile["model_bindings_sha256"] == digest(design["components"]),
                     "Component specifications do not match frozen binding hash")


def assignments(design: dict[str, Any]) -> list[dict[str, Any]]:
    """Randomized complete blocks, not identical model sampling randomness."""
    validate_design(design)
    rng = random.Random(design["order_seed"])
    blocks = [(s["id"], s["family"], rep)
              for s in sorted(design["scenarios"], key=lambda x: x["id"])
              for rep in range(1, design["repetitions"] + 1)]
    rng.shuffle(blocks)
    rows = []
    for scenario, family, rep in blocks:
        order = list(ARMS)
        rng.shuffle(order)
        block = digest([scenario, rep])
        for arm in order:
            rows.append({"ordinal": len(rows) + 1, "block_id": block,
                         "scenario_id": scenario, "family": family,
                         "repetition": rep, "arm": arm})
    return rows


def freeze_design(design: dict[str, Any]) -> dict[str, Any]:
    """Return a detached checksummed design; does not submit any model work."""
    rows = assignments(design)
    payload = {"design": copy.deepcopy(design), "assignments": rows,
               "expected_dialogues": len(rows),
               "evidence_use": {"exploration": "development_only",
                                "screening": "candidate_selection_only",
                                "confirmation": "held_out_confirmatory_evidence"}[design["stage"]]}
    return {**payload, "manifest_sha256": digest(payload)}


def verify_manifest(manifest: dict[str, Any]) -> None:
    """Check hashes AND regenerated assignments; rehashed incomplete blocks fail."""
    _require(isinstance(manifest, dict) and set(manifest) == {
        "design", "assignments", "expected_dialogues", "evidence_use", "manifest_sha256"},
        "Invalid manifest fields")
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    _require(manifest["manifest_sha256"] == digest(unsigned), "Manifest checksum mismatch")
    expected = freeze_design(manifest["design"])
    _require(digest(manifest) == digest(expected), "Manifest or assignment mismatch")
