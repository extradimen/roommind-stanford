"""Counterfactual G4.11 diagnostics against frozen G4.10 failures."""

from __future__ import annotations

from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys

from app.research_probes import run_integrity_probes
from app.research_protocol import CURRENT_ARCHITECTURE_VERSION, CURRENT_GENERATION_ID


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: g4_11_frozen_behavior_replay.py DEBUG_BUNDLE.json.gz")
    with gzip.open(Path(sys.argv[1]), "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    by_id = {
        int(row["run"]["id"]): deepcopy(row["full_session"])
        for row in payload["runs"]
        if row["full_session"]["session"]["session_mode"] == "test"
    }
    probes_by_id = {}
    for run_id, bundle in by_id.items():
        run_config = bundle["session"]["run_config"]
        manifest = run_config.setdefault("research_manifest", {})
        run_config["generation_id"] = manifest["generation_id"] = CURRENT_GENERATION_ID
        run_config["architecture_version"] = manifest[
            "architecture_version"
        ] = CURRENT_ARCHITECTURE_VERSION
        probes_by_id[run_id] = run_integrity_probes(bundle)

    # Launch, planning, and incident runs all contain an NPC-directed question
    # followed by a player relay instead of the addressed role's response.
    for run_id in (516, 518, 522):
        probes = probes_by_id[run_id]
        assert probes["checks"][
            "g411_npc_questions_receive_direct_same_turn_response"
        ] is False
        assert probes["diagnostics"]["g411_direct_response_violations"]

    # Frozen public quotes also prove that a rejected structured transition
    # could previously survive as first-person confirmation wording.
    assert probes_by_id[516]["checks"][
        "g411_rejected_transitions_not_reintroduced_in_speech"
    ] is False
    assert probes_by_id[516]["diagnostics"][
        "g411_rejected_transition_surface_violations"
    ]

    print("G4.11 frozen G4.10 behavior replay: ok")


if __name__ == "__main__":
    main()
