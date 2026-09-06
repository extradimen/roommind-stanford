"""Replay G4.7 deterministic guards against frozen G4.6 counterexamples."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from app.agent.speech_safety import private_constraint_contradiction_reason
from app.player_agent import pending_public_questions, safe_comparison_player_fallback


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = (
    ROOT / "research" / "experiments" / "2026-09-06-g4-6-qualification"
    / "debug-bundle.json.gz"
)


def aliases_and_labels(directory: dict) -> tuple[dict[str, list[str]], dict[str, str]]:
    aliases: dict[str, list[str]] = {}
    labels: dict[str, str] = {}
    for actor_id, row in directory.items():
        aliases[str(actor_id)] = [
            str(value) for value in (
                row.get("display_name"), row.get("character_name"), row.get("job_title"),
            ) if value
        ]
        labels[str(actor_id)] = str(
            row.get("character_name") or row.get("display_name") or actor_id
        )
    return aliases, labels


def main() -> None:
    with gzip.open(ARTIFACT, "rt", encoding="utf-8") as handle:
        bundle = json.load(handle)
    runs = {int(row["run"]["id"]): row["full_session"] for row in bundle["runs"]}

    cases = {
        (474, 4): "supplier_ceo",
        (474, 23): "supplier_ceo",
        (476, 17): "cfo",
        (480, 29): "sre_lead",
        (480, 31): "sre_lead",
        (480, 34): "sre_lead",
    }
    for (run_id, player_sequence), expected_target in cases.items():
        full = runs[run_id]
        aliases, labels = aliases_and_labels(full["speaker_directory"])
        history = [
            row for row in full["messages"]
            if int(row.get("sequence_no") or 0) < player_sequence
        ]
        pending = pending_public_questions(
            history, participant_aliases=aliases, participant_labels=labels,
        )
        assert pending, (run_id, player_sequence, "missing pending question")
        assert pending[-1]["target_id"] == expected_target, (
            run_id, player_sequence, pending[-1], expected_target,
        )

    fallback, _ = safe_comparison_player_fallback(
        evidence_mode="live_operation",
        pending_questions=[{
            "speaker_id": "cfo",
            "question": "Could you share the updated model now so I can confirm the budget?",
            "target_id": "user",
        }],
        turn_id=9,
    )
    assert "For Could you" not in fallback
    assert "Could you share" not in fallback

    assert private_constraint_contradiction_reason(
        "All relevant support teams are fully trained and ready for launch.",
        private_constraints=["The support team is short two trained specialists."],
    ) == "private_constraint_contradiction"
    print("G4.7 frozen G4.6 behavior replay: ok")


if __name__ == "__main__":
    main()
