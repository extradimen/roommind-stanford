"""Semantic invariants for versioned internal-world scenario snapshots."""
import argparse
import hashlib
import json
from pathlib import Path

from app.world.executor import contract


def validate(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    errors = []
    for entry in manifest["scenarios"]:
        path = directory / entry["file"]
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            errors.append(f"{path.name}: manifest hash mismatch")
            continue
        scenario = json.loads(raw)
        world = contract(scenario.get("task_config") or {})
        if not world:
            continue
        roles = {row["character_id"]: row for row in scenario.get("characters") or []}
        schema = (scenario.get("task_config") or {}).get("state_schema") or {}
        reachable = dict(world.get("initial_facts") or {})
        remaining = dict(world["actions"])
        while remaining:
            progressed = False
            for name, action in list(remaining.items()):
                if all(reachable.get(key) == value for key, value in action.get("requires", {}).items()):
                    reachable[action["field"]] = action["value"]
                    del remaining[name]
                    progressed = True
            if not progressed:
                errors.append(f"{path.name}: unreachable actions {sorted(remaining)}")
                break
        for name, action in world["actions"].items():
            field = action["field"]
            if field not in schema or schema[field].get("execution_confirms") is not True:
                errors.append(f"{path.name}:{name}: execution field is not typed execution confirmation")
            for actor in action["actors"]:
                authority = (roles.get(actor) or {}).get("authority") or {}
                if actor not in roles:
                    errors.append(f"{path.name}:{name}: unknown actor {actor}")
                for permission in ("can_execute", "can_confirm"):
                    if field not in authority.get(permission, []):
                        errors.append(f"{path.name}:{name}: {actor} lacks {permission} for {field}")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    failures = validate(args.directory)
    print(json.dumps({"directory": str(args.directory), "passed": not failures,
                      "errors": failures}))
    if failures:
        raise SystemExit(1)
