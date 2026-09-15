"""Counterfactual G4.12 diagnostics against frozen G4.11 failures."""

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
        raise SystemExit("usage: g4_12_frozen_behavior_replay.py DEBUG_BUNDLE.json.gz")
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

    # The frozen launch, interview, and incident sessions prove that a player
    # could address one role while another role consumed the floor, or receive
    # no response from the named role at all.
    for run_id in (526, 528, 530):
        probes = probes_by_id[run_id]
        assert probes["checks"]["g412_player_addressed_response_lock_respected"] is False
        assert probes["diagnostics"]["g412_player_response_lock_violations"]

    # The interview session contains four unsupported claims that a roadmap,
    # plan, or design artifact had been placed in a shared folder/drive/repo.
    unsupported = probes_by_id[528]["diagnostics"]["unsupported_public_evidence"]
    assert {row["sequence_no"] for row in unsupported}.issuperset({20, 23, 24, 31})

    # Every frozen RoomMind transcript contains at least one rejected public
    # transition whose visible wording still exceeded the validated lifecycle.
    for probes in probes_by_id.values():
        assert probes["checks"][
            "g411_rejected_transitions_not_reintroduced_in_speech"
        ] is False

    print("G4.12 frozen G4.11 behavior replay: ok")


if __name__ == "__main__":
    main()
