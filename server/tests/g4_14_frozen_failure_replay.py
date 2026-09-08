"""Counterfactual G4.14 diagnostics against frozen G4.13 failures."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from app.research_probes import run_integrity_probes
from app.research_protocol import CURRENT_ARCHITECTURE_VERSION, CURRENT_GENERATION_ID


def main() -> None:
    assert CURRENT_GENERATION_ID == "G4.14"
    assert CURRENT_ARCHITECTURE_VERSION.startswith("g4.14-")
    artifact = (
        Path(__file__).resolve().parents[2]
        / "research/experiments/2026-09-08-g4-13-qualification/g4-13-debug-bundle.json"
    )
    with artifact.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    by_id = {
        int(row["run"]["id"]): deepcopy(row["full_session"])
        for row in payload["runs"]
        if row["full_session"]["session"]["session_mode"] == "test"
    }
    probes = {}
    for run_id, bundle in by_id.items():
        run_config = bundle["session"]["run_config"]
        manifest = run_config.setdefault("research_manifest", {})
        run_config["generation_id"] = manifest["generation_id"] = CURRENT_GENERATION_ID
        run_config["architecture_version"] = manifest[
            "architecture_version"
        ] = CURRENT_ARCHITECTURE_VERSION
        probes[run_id] = run_integrity_probes(bundle)

    assert probes[540]["checks"]["g414_publication_owner_and_artifact_grounding_converged"]
    for run_id in (542, 544, 546):
        assert not probes[run_id]["checks"][
            "g414_publication_owner_and_artifact_grounding_converged"
        ]
    assert not probes[542]["checks"]["g412_player_addressed_response_lock_respected"]
    assert not probes[544]["checks"]["g412_player_addressed_response_lock_respected"]
    assert not probes[546]["checks"]["g411_npc_questions_receive_direct_same_turn_response"]
    assert any(
        row["sequence_no"] in {26, 37}
        for row in probes[544]["diagnostics"]["unsupported_public_evidence"]
    )
    assert any(
        row["sequence_no"] == 22
        for row in probes[546]["diagnostics"]["unsupported_public_evidence"]
    )
    print("G4.14 frozen G4.13 failure replay: ok")


if __name__ == "__main__":
    main()
