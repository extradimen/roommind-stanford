"""Replay G4.8 diagnostics against the frozen G4.7 qualification evidence."""

from __future__ import annotations

from copy import deepcopy
import gzip
import json
from pathlib import Path

from app.research_probes import run_integrity_probes
from app.research_protocol import CURRENT_ARCHITECTURE_VERSION


def main() -> None:
    artifact = (
        Path(__file__).resolve().parents[2]
        / "research/experiments/2026-09-06-g4-7-qualification/debug-bundle.json.gz"
    )
    with gzip.open(artifact, "rt", encoding="utf-8") as stream:
        payload = json.load(stream)

    failures: dict[int, set[str]] = {}
    for item in payload["runs"]:
        if item["run"]["condition"] != "roommind":
            continue
        bundle = deepcopy(item["full_session"])
        run_config = bundle["session"]["run_config"]
        run_config["architecture_version"] = CURRENT_ARCHITECTURE_VERSION
        run_config.setdefault("research_manifest", {})[
            "architecture_version"
        ] = CURRENT_ARCHITECTURE_VERSION
        result = run_integrity_probes(bundle)
        failures[int(item["run"]["id"])] = {
            name for name, passed in result["checks"].items() if passed is False
        }

    assert "g48_public_utterances_well_formed" in failures[482]
    assert "g48_live_artifact_receipts_grounded" in failures[482]
    assert "g48_no_speech_after_player_closure" in failures[484]
    assert "g48_cross_speaker_issue_repetition_absent" in failures[486]
    assert "g48_no_speech_after_player_closure" in failures[488]
    print("G4.8 frozen G4.7 behavior replay: ok")


if __name__ == "__main__":
    main()
