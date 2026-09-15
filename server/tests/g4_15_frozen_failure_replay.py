"""Counterfactual G4.15 diagnostics against frozen G4.14 failures."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from app.research_probes import run_integrity_probes
from app.research_protocol import CURRENT_ARCHITECTURE_VERSION, CURRENT_GENERATION_ID


def main() -> None:
    assert CURRENT_GENERATION_ID == "G4.16"
    assert CURRENT_ARCHITECTURE_VERSION.startswith("g4.16-")
    artifact = (
        Path(__file__).resolve().parents[2]
        / "research/experiments/2026-09-08-g4-14-qualification/g4-14-debug-bundle.json"
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

    assert not probes[548]["checks"][
        "g415_typed_publication_and_terminal_phase_converged"
    ]
    assert probes[548]["diagnostics"]["g415_synthetic_fallback_fragments"]

    assert not probes[550]["checks"][
        "g415_typed_publication_and_terminal_phase_converged"
    ]
    assert any(
        row["sequence_no"] == 12
        and row["reason"] == "publication_claim_requires_simulated_tool_result"
        for row in probes[550]["diagnostics"]["g415_publication_claim_violations"]
    )

    assert not probes[552]["checks"][
        "g415_typed_publication_and_terminal_phase_converged"
    ]
    assert any(
        row["sequence_no"] == 13
        for row in probes[552]["diagnostics"]["g415_publication_claim_violations"]
    )
    assert any(
        row["sequence_no"] >= 30
        for row in probes[552]["diagnostics"]["g415_terminal_phase_reentries"]
    )

    assert not probes[554]["checks"][
        "g415_typed_publication_and_terminal_phase_converged"
    ]
    incident_reasons = {
        (row["sequence_no"], row["reason"])
        for row in probes[554]["diagnostics"]["g415_publication_claim_violations"]
    }
    assert (4, "publication_claim_requires_simulated_tool_result") in incident_reasons
    assert (6, "unregistered_participant_assignment") in incident_reasons
    print("G4.15 frozen G4.14 failure replay: ok")


if __name__ == "__main__":
    main()
