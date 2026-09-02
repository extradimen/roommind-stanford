"""Dependency-light G3 public-world ledger regression checks."""

from types import SimpleNamespace

from app.agent.speech_safety import speech_rejection_reason
from app.public_ledger import (
    commit_public_intent,
    ensure_public_ledger,
    ground_public_intent_in_quote,
    ledger_has_support,
    validate_public_intent,
)
from app.player_character import resolve_player_character


def main() -> None:
    requested_submission = {
        "kind": "issue", "subject": "pricing structure", "transition": "submitted", "commit_allowed": True,
        "validation": "accepted", "validation_reason": "",
    }
    rejected_request = ground_public_intent_in_quote(
        requested_submission,
        "Please provide the pricing structure before we finalize the contract.",
    )
    assert rejected_request["commit_allowed"] is False
    assert rejected_request["validation"] == "rejected"
    grounded_submission = ground_public_intent_in_quote(
        requested_submission,
        "We have provided the pricing structure in full below.",
    )
    assert grounded_submission["commit_allowed"] is True
    unrelated_proposal = ground_public_intent_in_quote(
        {"kind": "issue", "subject": "quality protocol", "transition": "proposed", "commit_allowed": True},
        "Could you provide the annual volume forecast?",
    )
    assert unrelated_proposal["commit_allowed"] is False

    player_profile = resolve_player_character(SimpleNamespace(
        scene_config={"player_character": {
            "character_name": "Alex", "job_title": "Incident Commander",
        }},
        task_config={"state_schema": {
            "service_status": {
                "propose_permissions": ["player", "ops_lead"],
                "confirm_permissions": ["player", "ops_lead"],
            },
            "rollback": {
                "execute_permissions": ["player"],
            },
            "open_issue": {
                "type": "string",
            },
        }},
    ))
    assert player_profile["authority"]["can_propose"] == ["open_issue", "rollback", "service_status"]
    assert player_profile["authority"]["can_confirm"] == ["service_status"]
    assert player_profile["authority"]["can_execute"] == ["rollback"]

    alias_state: dict = {}
    first_issue = validate_public_intent(
        character={**player_profile, "character_id": "user"}, state=alias_state,
        turn_id=1,
        intent={
            "kind": "issue", "subject": "Supplier pricing structure and volume commitments",
            "field": "service_status", "transition": "proposed",
        },
    )
    commit_public_intent(
        alias_state, intent=first_issue,
        public_quote="We need the supplier pricing structure and volume commitments.",
    )
    explicit_repeat = validate_public_intent(
        character={**player_profile, "character_id": "user"}, state=alias_state,
        turn_id=2,
        intent={
            "kind": "issue", "subject": "Supplier pricing structure and volume commitments",
            "field": "service_status", "transition": "proposed",
        },
    )
    assert explicit_repeat["commit_allowed"] is False
    assert explicit_repeat["validation_reason"] == "field_lifecycle_repeat_by_actor"
    singular_alias = validate_public_intent(
        character={**player_profile, "character_id": "user"}, state=alias_state,
        turn_id=2,
        intent={
            "kind": "issue", "subject": "Supplier pricing structure and volume commitment",
            "transition": "proposed",
        },
    )
    assert singular_alias["entity_id"] == "field:service_status"
    # Configured fields use the stronger field lifecycle rule above. The same
    # actor cannot manufacture progress by restating an already proposed field.
    assert singular_alias["commit_allowed"] is False

    operator = SimpleNamespace(
        character_id="ops_lead",
        authority={
            "can_confirm": ["service_status", "recovery_window", "production_deployment"],
            "can_execute": ["recovery_window", "production_deployment"],
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
    proposed_issue = {
        "kind": "issue", "transition": "proposed",
        "simulation_scope": "discussion",
    }
    assert speech_rejection_reason(
        "The engineering director has confirmed that the architecture is grounded in real-world data.",
        validated_intent=proposed_issue,
    ) == "speech_exceeds_validated_lifecycle"
    assert speech_rejection_reason(
        "The engineering team is aligned and ready to move forward.",
        validated_intent=proposed_issue,
    ) == "speech_exceeds_validated_lifecycle"
    assert speech_rejection_reason(
        "We need to confirm whether the engineering team is aligned before moving forward.",
        validated_intent=proposed_issue,
    ) is None
    assert speech_rejection_reason(
        "We need to verify whether the architecture has been confirmed by the owner.",
        validated_intent=proposed_issue,
    ) is None
    committed_issue = {
        "kind": "issue", "transition": "committed",
        "simulation_scope": "discussion",
    }
    assert speech_rejection_reason(
        "We will review the architecture before deciding.",
        validated_intent=committed_issue,
    ) is None
    assert speech_rejection_reason(
        "The architecture has been verified and approved.",
        validated_intent=committed_issue,
    ) == "speech_exceeds_validated_lifecycle"
    assert speech_rejection_reason(
        "Engineering evidence will be accepted to close the requirement.",
        validated_intent=proposed_issue,
    ) == "speech_exceeds_validated_lifecycle"
    assert speech_rejection_reason(
        "Engineering evidence could be accepted if the authorized reviewer confirms it.",
        validated_intent=proposed_issue,
    ) is None
    retrospective_issue = {
        "kind": "fact", "transition": "proposed",
        "simulation_scope": "retrospective",
    }
    assert speech_rejection_reason(
        "In my previous role, I verified the architecture with the engineering lead.",
        validated_intent=retrospective_issue,
    ) is None
    assert speech_rejection_reason(
        "I led a cross-functional launch and measured the outcome against our activation target.",
        validated_intent=retrospective_issue,
    ) is None
    assert speech_rejection_reason(
        "Could you clarify which prior project would be most relevant?",
        validated_intent=retrospective_issue,
    ) is None
    assert speech_rejection_reason(
        "I am verifying the architecture now and will proceed without further review.",
        validated_intent=retrospective_issue,
    ) == "retrospective_scope_not_grounded_in_quote"

    state: dict = {}
    in_session = validate_public_intent(
        character=operator,
        turn_id=4,
        state=state,
        intent={
            "kind": "action",
            "subject": "calculate recovery window",
            "field": "recovery_window",
            "value": "14:00-14:20 UTC",
            "transition": "verified",
            "simulation_scope": "in_session",
            "inline_content": "Recovery window: 14:00-14:20 UTC, based on the stated timeline.",
        },
    )
    assert in_session["transition"] == "submitted"
    assert in_session["validation_reason"] == "material_lifecycle_requires_separate_transitions"
    assert speech_rejection_reason(
        "The recovery-window work is complete.",
        validated_intent=in_session,
    ) == "speech_exceeds_validated_lifecycle"

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
            "kind": "verification", "subject": "recovery window calculation",
            "field": "recovery_window",
            "value": "14:00-14:20 UTC",
            "transition": "verified", "simulation_scope": "in_session",
            "inline_content": "Recovery window independently checked against the stated timeline.",
        },
    )
    assert verified["transition"] == "verified"
    verified_event = commit_public_intent(
        state,
        intent=verified,
        public_quote="I independently verified the 14:00-14:20 UTC recovery window.",
        tick=1,
    )
    assert verified_event["entity_id"] == event["entity_id"]
    assert verified_event["transition_from"] == "submitted"
    assert verified_event["transition_to"] == "verified"
    assert ledger_has_support(
        state,
        kind="action",
        subject="recovery_window",
        field="recovery_window",
        minimum={"verified", "accepted"},
    )
    regressive_action = validate_public_intent(
        character=operator,
        turn_id=6,
        state=state,
        intent={
            "kind": "action", "subject": "recovery window follow-up",
            "field": "recovery_window", "transition": "committed",
            "simulation_scope": "external",
        },
    )
    assert regressive_action["transition"] == "verified"
    assert regressive_action["commit_allowed"] is False
    assert regressive_action["validation_reason"] == "material_lifecycle_cannot_regress_or_repeat"

    # Closely reworded references to the same unconfigured work item must not
    # create one entity per intent kind or phrasing variant.
    alias_state: dict = {}
    proposed_work = validate_public_intent(
        character=operator,
        turn_id=5,
        state=alias_state,
        intent={
            "kind": "action", "subject": "prepare incident recovery evidence",
            "transition": "proposed", "simulation_scope": "discussion",
        },
    )
    proposed_event = commit_public_intent(
        alias_state,
        intent=proposed_work,
        public_quote="I propose preparing the incident recovery evidence.",
        tick=1,
    )
    reworded_work = validate_public_intent(
        character=operator,
        turn_id=6,
        state=alias_state,
        intent={
            "kind": "verification", "subject": "incident recovery evidence review",
            "transition": "proposed", "simulation_scope": "discussion",
        },
    )
    assert reworded_work["entity_id"] == proposed_event["entity_id"]

    artifact = validate_public_intent(
        character=operator,
        turn_id=5,
        intent={
            "kind": "artifact",
            "subject": "audit report",
            "field": "service_status",
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

    player = {"character_id": "user", "authority": {
        "can_propose": ["service_status"], "can_confirm": ["service_status"],
    }}
    player_acceptance = validate_public_intent(
        character=player,
        turn_id=7,
        intent={
            "kind": "decision", "subject": "accept service status",
            "field": "service_status", "value": "operational", "transition": "accepted",
        },
    )
    assert player_acceptance["transition"] == "accepted"
    missing_field_value = validate_public_intent(
        character=player, turn_id=7,
        intent={
            "kind": "decision", "subject": "accept service status",
            "field": "service_status", "transition": "accepted",
        },
    )
    assert missing_field_value["transition"] == "proposed"
    assert missing_field_value["validation_reason"] == "field_terminal_transition_requires_value"
    field_state: dict = {}
    accepted_event = commit_public_intent(
        field_state,
        intent=validate_public_intent(
            character=player, state=field_state, turn_id=7,
            intent={
                "kind": "decision", "subject": "accept service status",
                "field": "service_status", "value": "operational", "transition": "accepted",
            },
        ),
        public_quote="I accept the service status as operational.", tick=1,
    )
    regressive_proposal = validate_public_intent(
        character=player, state=field_state, turn_id=8,
        intent={
            "kind": "proposal", "subject": "reopen service status",
            "field": "service_status", "transition": "proposed",
        },
    )
    assert accepted_event["entity_id"] == "field:service_status"
    assert accepted_event["value"] == "operational"
    assert ensure_public_ledger(field_state)["entities"]["field:service_status"]["value"] == "operational"
    assert regressive_proposal["transition"] == "accepted"
    assert regressive_proposal["commit_allowed"] is False
    assert regressive_proposal["validation_reason"] == "field_lifecycle_cannot_regress"

    no_capability = validate_public_intent(
        character=unauthorized,
        turn_id=7,
        intent={
            "kind": "action", "subject": "complete an unregistered task",
            "transition": "submitted", "simulation_scope": "in_session",
            "inline_content": "A purported result.",
        },
    )
    assert no_capability["transition"] == "proposed"
    assert no_capability["validation_reason"] == "actor_lacks_transition_authority"

    retrospective_bypass = validate_public_intent(
        character=operator,
        turn_id=7,
        intent={
            "kind": "artifact", "subject": "claimed historical report",
            "transition": "submitted", "simulation_scope": "retrospective",
        },
    )
    assert retrospective_bypass["simulation_scope"] == "discussion"
    assert retrospective_bypass["transition"] == "proposed"
    assert retrospective_bypass["validation_reason"] == "retrospective_scope_not_enabled"
    enabled_retrospective = validate_public_intent(
        character=operator,
        turn_id=7,
        allow_retrospective=True,
        intent={
            "kind": "artifact", "subject": "claimed historical report",
            "transition": "submitted", "simulation_scope": "retrospective",
        },
    )
    assert enabled_retrospective["kind"] == "fact"
    assert enabled_retrospective["transition"] == "proposed"
    assert enabled_retrospective["simulation_scope"] == "retrospective"

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
    assert regressed["entity_id"] not in ledger["entities"]
    assert regressed not in ledger["events"]

    print("public ledger smoke checks passed")


if __name__ == "__main__":
    main()
