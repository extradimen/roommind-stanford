"""Dependency-light G3 public-world ledger regression checks."""

from types import SimpleNamespace

from app.agent.speech_safety import speech_rejection_reason
from app.public_ledger import (
    commit_public_intent,
    ensure_public_ledger,
    validate_public_intent,
)


def main() -> None:
    operator = SimpleNamespace(
        character_id="ops_lead",
        authority={
            "can_confirm": ["service_status", "recovery_window"],
            "can_execute": ["recovery_window"],
        },
    )

    external = validate_public_intent(
        character=operator,
        turn_id=3,
        intent={
            "kind": "action",
            "subject": "deploy production fix",
            "transition": "accepted",
            "simulation_scope": "external",
        },
    )
    assert external["transition"] == "committed"
    assert external["validation"] == "downgraded"
    assert speech_rejection_reason(
        "We have completed the production deployment.",
        validated_intent=external,
    ) == "speech_exceeds_validated_lifecycle"

    state: dict = {}
    in_session = validate_public_intent(
        character=operator,
        turn_id=4,
        state=state,
        intent={
            "kind": "action",
            "subject": "calculate recovery window",
            "field": "recovery_window",
            "transition": "verified",
            "simulation_scope": "in_session",
            "inline_content": "Recovery window: 14:00-14:20 UTC, based on the stated timeline.",
        },
    )
    assert in_session["transition"] == "submitted"
    assert in_session["validation_reason"] == "material_lifecycle_requires_separate_transitions"

    event = commit_public_intent(
        state,
        intent=in_session,
        public_quote="The calculated recovery window is 14:00-14:20 UTC.",
        tick=2,
    )
    ledger = ensure_public_ledger(state)
    assert event["provenance"] == "prevalidated_agent_intent"
    assert ledger["simulation_clock"] == {"turn": 4, "tick": 2}
    assert ledger["entities"][event["entity_id"]]["lifecycle"] == "submitted"
    verified = validate_public_intent(
        character=operator,
        turn_id=5,
        state=state,
        intent={
            "kind": "action", "subject": "calculate recovery window",
            "field": "recovery_window",
            "transition": "verified", "simulation_scope": "in_session",
            "inline_content": "Recovery window independently checked against the stated timeline.",
        },
    )
    assert verified["transition"] == "verified"

    artifact = validate_public_intent(
        character=operator,
        turn_id=5,
        intent={
            "kind": "artifact",
            "subject": "audit report",
            "transition": "submitted",
            "simulation_scope": "in_session",
        },
    )
    assert artifact["transition"] == "committed"
    assert artifact["validation_reason"] == "artifact_terminal_transition_requires_inline_content"

    unauthorized = SimpleNamespace(character_id="observer", authority={})
    approval = validate_public_intent(
        character=unauthorized,
        turn_id=6,
        intent={
            "kind": "decision",
            "subject": "service status approval",
            "field": "service_status",
            "transition": "accepted",
        },
    )
    assert approval["transition"] == "proposed"
    assert approval["validation_reason"] == "actor_lacks_transition_authority"
    advisor = SimpleNamespace(
        character_id="advisor",
        authority={"can_propose": [], "can_confirm": [], "cannot_commit": ["service_status"]},
    )
    forbidden_commitment = validate_public_intent(
        character=advisor,
        turn_id=6,
        intent={
            "kind": "commitment", "subject": "approve service status",
            "field": "service_status", "transition": "committed",
        },
    )
    assert forbidden_commitment["transition"] == "proposed"
    assert forbidden_commitment["validation_reason"] == "actor_lacks_transition_authority"

    # Event IDs remain unique after the retained event window is compacted,
    # and a caller cannot silently move the shared simulation clock backward.
    ledger["event_counter"] = 300
    late = commit_public_intent(
        state,
        intent={
            **validate_public_intent(
                character=operator,
                turn_id=7,
                intent={"kind": "fact", "subject": "review started", "transition": "proposed"},
            )
        },
        public_quote="The review has started.",
        tick=2,
    )
    assert late["event_id"] == "ple-00301"
    regressed = commit_public_intent(
        state,
        intent=validate_public_intent(
            character=operator,
            turn_id=6,
            intent={"kind": "fact", "subject": "late observation", "transition": "proposed"},
        ),
        public_quote="This observation arrived late.",
        tick=1,
    )
    assert regressed["clock_valid"] is False
    assert ledger["simulation_clock"] == {"turn": 7, "tick": 2}

    print("public ledger smoke checks passed")


if __name__ == "__main__":
    main()
