"""Counterfactual coverage for G4.10 against frozen G4.9 failures."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
import sys

from app.research_probes import run_integrity_probes
from app.research_protocol import CURRENT_ARCHITECTURE_VERSION


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: g4_10_frozen_behavior_replay.py DEBUG_BUNDLE.json.gz")
    path = Path(sys.argv[1])
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    by_id = {int(row["run"]["id"]): row["full_session"] for row in payload["runs"]}

    launch = by_id[502]
    launch["session"]["run_config"]["research_manifest"][
        "architecture_version"
    ] = CURRENT_ARCHITECTURE_VERSION
    launch_probes = run_integrity_probes(launch)
    # The original three-person request is satisfied across the visible Dana
    # floor handoff, so that handoff is no longer a false request boundary.
    assert launch_probes["checks"]["g49_multi_addressee_responses_preserved"] is True
    # The same frozen run still proves why clause-local confirmation grounding
    # is required: a conditional CFO statement was committed as accepted.
    assert launch_probes["checks"]["g410_conditional_confirmations_not_committed"] is False
    assert launch_probes["diagnostics"]["g410_conditional_acceptance_events"]

    interview = by_id[504]
    interview["session"]["run_config"]["research_manifest"][
        "architecture_version"
    ] = CURRENT_ARCHITECTURE_VERSION
    interview_probes = run_integrity_probes(interview)
    assert interview_probes["checks"]["g410_terminal_confirmation_locks_floor"] is False
    assert interview_probes["diagnostics"]["g410_post_terminal_confirmation_speech"]

    print("G4.10 frozen G4.9 behavior replay: ok")


if __name__ == "__main__":
    main()
