"""Regression assertions for the exact public failures frozen in G4.12."""

from __future__ import annotations

from types import SimpleNamespace

from app.agent.speech_safety import (
    player_speech_rejection_reason,
    speech_rejection_reason,
)
from app.orchestrator.generative import lock_player_response_order
from app.research_protocol import CURRENT_ARCHITECTURE_VERSION, CURRENT_GENERATION_ID


def main() -> None:
    assert CURRENT_GENERATION_ID == "G4.15"
    assert CURRENT_ARCHITECTURE_VERSION.startswith("g4.15-")

    # Runs 532/534/536: named addressees retain their public order even when
    # ordinary dispatch and focus would otherwise prefer another role.
    roles = [
        SimpleNamespace(character_id="sales_vp"),
        SimpleNamespace(character_id="operations_director"),
        SimpleNamespace(character_id="cfo"),
    ]
    ordered = lock_player_response_order(
        roles, ["cfo", "operations_director"]
    )
    assert [row.character_id for row in ordered] == [
        "cfo", "operations_director",
    ]

    # Run 534: polite wording cannot reintroduce a rejected repeated terminal
    # transition at the visible speech boundary.
    assert speech_rejection_reason(
        "I’m pleased to confirm the phased national launch. Let’s proceed.",
        validated_intent={
            "kind": "decision",
            "field": "launch_decision",
            "transition": "accepted",
            "commit_allowed": False,
            "validation": "downgraded",
            "validation_reason": "field_lifecycle_repeat_by_actor",
            "simulation_scope": "discussion",
        },
    ) == "speech_exceeds_validated_lifecycle"

    # Run 536: retrospective mode does not excuse a present-tense dashboard
    # storage claim without a registered simulated-tool result.
    assert player_speech_rejection_reason(
        "All results are stored in the sprint performance dashboard, including "
        "the A/B test metrics and stakeholder interview findings.",
        validated_intent={
            "kind": "statement",
            "transition": "proposed",
            "commit_allowed": True,
            "simulation_scope": "retrospective",
            "evidence_source": "public_statement",
        },
    ) == "current_world_completion_requires_simulated_tool_result"

    print("G4.13 frozen G4.12 failure replay: ok")


if __name__ == "__main__":
    main()
