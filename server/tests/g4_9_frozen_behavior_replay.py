"""Replay G4.9 diagnostics against the frozen G4.8 qualification evidence."""

from __future__ import annotations

from copy import deepcopy
import gzip
import json
from pathlib import Path

from app.research_probes import run_integrity_probes
from app.research_protocol import CURRENT_ARCHITECTURE_VERSION, CURRENT_GENERATION_ID


def main() -> None:
    artifact = (
        Path(__file__).resolve().parents[2]
        / "research/experiments/2026-09-06-g4-8-qualification/debug-bundle.json.gz"
    )
    with gzip.open(artifact, "rt", encoding="utf-8") as stream:
        payload = json.load(stream)

    failures: dict[int, set[str]] = {}
    diagnostics: dict[int, dict] = {}
    for item in payload["runs"]:
        if item["run"]["condition"] != "roommind":
            continue
        bundle = deepcopy(item["full_session"])
        run_config = bundle["session"]["run_config"]
        run_config["generation_id"] = CURRENT_GENERATION_ID
        run_config["architecture_version"] = CURRENT_ARCHITECTURE_VERSION
        manifest = run_config.setdefault("research_manifest", {})
        manifest["generation_id"] = CURRENT_GENERATION_ID
        manifest["architecture_version"] = CURRENT_ARCHITECTURE_VERSION
        result = run_integrity_probes(bundle)
        run_id = int(item["run"]["id"])
        failures[run_id] = {
            name for name, passed in result["checks"].items() if passed is False
        }
        diagnostics[run_id] = result["diagnostics"]

    assert "g49_multi_addressee_responses_preserved" in failures[494]
    assert diagnostics[494]["g49_multi_addressee_response_violations"]
    assert "g49_generated_routing_prompts_absent" in failures[494]
    assert "g49_generated_routing_prompts_absent" in failures[496]
    assert "g49_retrospective_authorship_preserved" in failures[496]
    assert diagnostics[496]["g49_retrospective_authorship_violations"]
    print("G4.9 frozen G4.8 behavior replay: ok")


if __name__ == "__main__":
    main()
