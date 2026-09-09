"""Create exclusive, versioned full scenario snapshots; never edit originals."""
import argparse
import hashlib
import json
from pathlib import Path


def build(root, destination, version=2):
    # Exclusive directory prevents partially replacing any previous snapshot.
    destination.mkdir(parents=True, exist_ok=False)
    manifest = {"schema": "roommind-world-scenario-snapshots-v1", "evidence_use": "development_only",
                "scenarios": []}
    for source in sorted((root / "templates/scenarios").glob("*.json")):
        raw = source.read_bytes()
        scenario = json.loads(raw)
        origin = scenario["slug"]
        scenario["slug"] += f"-world-v{version}"
        scenario["title"] += f" (Simulated World v{version})"
        scenario["template_meta"] = {"source_slug": origin, "source_sha256": hashlib.sha256(raw).hexdigest(),
                                     "world_version": version}
        world = {"schema": "roommind-simulation-executor-v1", "initial_facts": {}, "actions": {}}
        if origin == "incident-response-command":
            world["actions"] = {
                "diagnose_scope": {"actors": ["sre_lead"], "field": "incident_scope_identified", "value": True},
                "preserve_evidence": {"actors": ["security_lead"], "field": "evidence_preserved", "value": True,
                                      "requires": {"incident_scope_identified": True}},
                "activate_containment": {"actors": ["sre_lead"], "field": "containment_active", "value": True,
                                         "requires": {"evidence_preserved": True}},
            }
            scenario["task_config"]["state_schema"]["evidence_preserved"] = {
                "type": "boolean", "description": "Evidence preserved by the internal simulation executor",
                "confirmation_policy": "responsible_participant",
                "propose_permissions": ["security_lead"], "confirm_permissions": ["security_lead"]}
            for char in scenario["characters"]:
                for action in world["actions"].values():
                    scenario["task_config"]["state_schema"][action["field"]]["execution_confirms"] = True
                    if char["character_id"] in action["actors"]:
                        for permission in ("can_execute", "can_propose", "can_confirm"):
                            values = char.setdefault("authority", {}).setdefault(permission, [])
                            if action["field"] not in values:
                                values.append(action["field"])
        scenario["task_config"]["simulation_executor"] = world
        output = json.dumps(scenario, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        filename = scenario["slug"] + ".json"
        with (destination / filename).open("x", encoding="utf-8") as stream:
            stream.write(output)
        manifest["scenarios"].append({"file": filename, "source_sha256": hashlib.sha256(raw).hexdigest(),
                                      "sha256": hashlib.sha256(output.encode()).hexdigest()})
    with (destination / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"created": len(manifest["scenarios"]), "directory": str(destination)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.root, args.output)
