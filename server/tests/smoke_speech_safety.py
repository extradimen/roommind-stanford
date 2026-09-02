"""Regression checks for public NPC speech safety."""

from app.agent.speech_safety import (
    PUBLIC_RESPONSE_DRAFT,
    player_speech_rejection_reason,
    speech_rejection_reason,
)
from types import SimpleNamespace

from app.orchestrator.common import orch_support
from app.task_state import (
    advance_phase,
    apply_evaluator_updates,
    evaluate_conditions,
    finalize_stalled_task_state,
    initial_task_state,
    normalize_evaluator_payload,
    public_task_result,
    prepare_turn_governance,
    set_progress_metadata,
    task_progress_signature,
)
from app.orchestrator.generative import generative_orchestrator
from app.player_agent import normalize_player_content, pending_public_questions


def main() -> None:
    leaked_plan = (
        "I will first confirm the purchase volume to set the foundation, aiming "
        "to lock an annual framework agreement for at least 100k units. My bottom "
        "line is a unit price no lower than 82 RMB and no uncapped penalty"
    )
    assert speech_rejection_reason(leaked_plan, active_plan_text=leaked_plan)
    assert speech_rejection_reason(
        "I appreciate the proposal, but the 5% cap is non"
    ) == "truncated"
    assert speech_rejection_reason(
        "I need 30% upfront and the balance within 30"
    ) == "truncated"
    assert speech_rejection_reason(
        "Thank you for the proposal. We can review the full package together."
    ) is None
    assert player_speech_rejection_reason(
        '{"content": "A truncated proposal", "intent": "compromise with long'
    ) == "structured_output"
    assert player_speech_rejection_reason(
        "Let’s review the complete package before deciding."
    ) is None
    assert normalize_player_content(
        '{"content":"I will answer with a concrete example.","intent":"opening"}'
    ) == "I will answer with a concrete example."
    assert normalize_player_content(
        '{"content":"{\\"content\\":\\"I am ready for the first question.\\"}"}'
    ) == "I am ready for the first question."
    nested_evaluation = '{"content":"{\\"phase\\":\\"evidence\\",\\"updates\\":[{\\"field\\":\\"outcome\\",\\"value\\":true,\\"status\\":\\"proposed\\"}]}"}'
    assert normalize_evaluator_payload(nested_evaluation)["updates"][0]["field"] == "outcome"
    assert "bottom line" not in PUBLIC_RESPONSE_DRAFT.casefold()
    assert "active plan" not in PUBLIC_RESPONSE_DRAFT.casefold()
    config = {
        "state_schema": {"outcome": {"type": "boolean"}},
        "phases": [{"phase_id": "active"}],
        "completion_conditions": {"all": [
            {"field": "outcome", "operator": "==", "value": True, "required_status": "confirmed"}
        ]},
    }
    state = initial_task_state(config)
    state["variables"]["outcome"].update(value=True, status="proposed")
    assert evaluate_conditions(config, state)["completion_status"] == "in_progress"
    state["variables"]["outcome"]["status"] = "confirmed"
    assert evaluate_conditions(config, state)["completion_status"] == "completed"

    # A conversational claim of completion cannot override unmet configured
    # conditions.  It becomes a truthful conditional/deferred terminal result.
    premature_state = initial_task_state(config)
    premature_state["outcome"] = {
        "type": "completed", "status": "explicit", "reason": "We are done", "evidence": []
    }
    evaluated_premature = evaluate_conditions(config, premature_state)
    assert evaluated_premature["completion_status"] == "deferred"
    assert evaluated_premature["outcome"]["claimed_type"] == "completed"
    assert evaluated_premature["outcome"]["unmet_conditions"] == ["outcome"]

    phase_config = {
        "state_schema": {
            "facts_known": {"type": "boolean"},
            "action_done": {"type": "boolean"},
        },
        "phases": [
            {"phase_id": "observe"},
            {"phase_id": "act", "entry_conditions": {"all": [
                {"field": "facts_known", "operator": "==", "value": True, "required_status": "confirmed"}
            ]}},
            {"phase_id": "close", "entry_conditions": {"all": [
                {"field": "action_done", "operator": "==", "value": True, "required_status": "confirmed"}
            ]}},
        ],
        "completion_conditions": {"all": []},
    }
    phase_state = initial_task_state(phase_config)
    phase_state["variables"]["facts_known"].update(value=True, status="confirmed")
    assert advance_phase(phase_config, phase_state) == "act"
    phase_state["variables"]["facts_known"].update(value=False, status="disputed")
    assert advance_phase(phase_config, phase_state) == "act", "phase progression must be monotonic"
    phase_state["variables"]["action_done"].update(value=True, status="confirmed")
    assert advance_phase(phase_config, phase_state) == "close"

    # Confirmations from authorized speakers commonly arrive in separate turns.
    # They must accumulate for the same typed value instead of being overwritten.
    cross_turn_config = {
        "state_schema": {
            "outcome": {
                "type": "boolean",
                "propose_permissions": ["player", "owner"],
                "confirm_permissions": ["player", "owner"],
                "confirmation_policy": "player_and_responsible_participant",
            }
        },
        "phases": [{"phase_id": "work"}, {"phase_id": "done", "entry_conditions": {"all": [
            {"field": "outcome", "operator": "==", "value": True, "required_status": "confirmed"}
        ]}}],
        "completion_conditions": {"all": [
            {"field": "outcome", "operator": "==", "value": True, "required_status": "confirmed"}
        ]},
    }
    owner = SimpleNamespace(character_id="owner", authority={"can_confirm": ["outcome"]})
    cross_state = initial_task_state(cross_turn_config)
    apply_evaluator_updates(
        task_config=cross_turn_config,
        state=cross_state,
        parsed={"updates": [{
            "field": "outcome", "value": True, "status": "confirmed",
            "proposed_by": "user", "confirmed_by": ["user"],
            "evidence": [{"speaker_id": "user", "quote": "I confirm outcome true"}],
        }]},
        characters=[owner],
        player_text="I confirm outcome true",
        npc_turns=[],
    )
    assert cross_state["variables"]["outcome"]["status"] == "proposed"
    assert cross_state["variables"]["outcome"]["confirmations"] == ["user"]
    before_signature = task_progress_signature(cross_state)
    apply_evaluator_updates(
        task_config=cross_turn_config,
        state=cross_state,
        parsed={"updates": [{
            "field": "outcome", "value": True, "status": "confirmed",
            "proposed_by": "owner", "confirmed_by": ["owner"],
            "evidence": [{"speaker_id": "owner", "quote": "Outcome true is confirmed"}],
        }]},
        characters=[owner],
        player_text="Thank you",
        npc_turns=[{"speaker_id": "owner", "content": "Outcome true is confirmed"}],
    )
    assert cross_state["variables"]["outcome"]["status"] == "confirmed"
    assert set(cross_state["variables"]["outcome"]["confirmations"]) == {"user", "owner"}
    assert cross_state["completion_status"] == "completed"
    assert cross_state["phase"] == "done"
    assert task_progress_signature(cross_state) != before_signature
    assert public_task_result(cross_state)["variables"]["outcome"]["value"] is True

    # A later proposal cannot silently reopen a confirmed item.
    apply_evaluator_updates(
        task_config=cross_turn_config,
        state=cross_state,
        parsed={"updates": [{
            "field": "outcome", "value": False, "status": "proposed",
            "proposed_by": "user", "confirmed_by": [],
            "evidence": [{"speaker_id": "user", "quote": "I propose outcome false"}],
        }]},
        characters=[owner],
        player_text="I propose outcome false",
        npc_turns=[],
        turn_id=3,
    )
    assert cross_state["variables"]["outcome"]["value"] is True
    assert cross_state["variables"]["outcome"]["status"] == "confirmed"
    assert cross_state["variables"]["outcome"]["superseded_proposals"][-1]["value"] is False

    # Evidence remains valid across harmless whitespace changes, and an omitted
    # proposer can be recovered from the verified public speaker.
    inferred_state = initial_task_state(cross_turn_config)
    apply_evaluator_updates(
        task_config=cross_turn_config,
        state=inferred_state,
        parsed={"updates": [{
            "field": "outcome", "value": True, "status": "proposed",
            "proposed_by": "", "confirmed_by": [],
            "evidence": [{"speaker_id": "owner", "quote": "Outcome true is proposed"}],
        }]},
        characters=[owner],
        player_text="",
        npc_turns=[{"speaker_id": "owner", "content": "Outcome true\n is   proposed"}],
    )
    assert inferred_state["variables"]["outcome"]["status"] == "proposed"
    assert inferred_state["variables"]["outcome"]["proposals"][-1]["proposed_by"] == "owner"

    # A claimed confirmation without an exact public evidence excerpt is rejected.
    bad_state = initial_task_state(cross_turn_config)
    apply_evaluator_updates(
        task_config=cross_turn_config,
        state=bad_state,
        parsed={"updates": [{
            "field": "outcome", "value": True, "status": "confirmed",
            "proposed_by": "owner", "confirmed_by": ["owner"],
            "evidence": [{"speaker_id": "owner", "quote": "invented confirmation"}],
        }]},
        characters=[owner],
        player_text="",
        npc_turns=[{"speaker_id": "owner", "content": "I need more information."}],
    )
    assert bad_state["variables"]["outcome"]["status"] != "confirmed"

    # Generic event governance is scenario-neutral. A promise is distinct from
    # delivery, duplicate promises do not create progress, and explicit
    # deferral is a valid terminal outcome for open-ended simulations.
    event_state = initial_task_state({
        "state_schema": {}, "phases": [{"phase_id": "active"}],
        "completion_conditions": {"all": []},
    })
    apply_evaluator_updates(
        task_config={"state_schema": {}, "phases": [{"phase_id": "active"}], "completion_conditions": {"all": []}},
        state=event_state,
        parsed={"updates": [], "events": [{
            "event_type": "artifact_offered", "subject": "capacity evidence",
            "status": "proposed", "actor_id": "owner",
            "summary": "Owner promises the evidence.",
            "evidence": [{"speaker_id": "owner", "quote": "I will send the capacity evidence"}],
        }]},
        characters=[owner], player_text="",
        npc_turns=[{"speaker_id": "owner", "content": "I will send the capacity evidence."}],
        turn_id=1,
    )
    assert event_state["work_items"]["capacity_evidence"]["status"] == "promised"
    coordinated = prepare_turn_governance(
        event_state,
        characters=[owner],
        turn_id=3,
        safety_max_turns=10,
        max_stagnant_turns=6,
    )
    focus = coordinated["progress"]["focus"]
    assert focus["issue"] == "work:capacity_evidence"
    assert focus["owner_ids"] == ["owner"]
    assert focus["due_now"] is True
    assert coordinated["coordination_history"][-1]["turn_id"] == 3

    # Player-only work is tracked in the ledger but is not selected as an NPC
    # coordinator focus because the shared comparison player cannot see the
    # private RoomMind coordinator.
    player_only_state = initial_task_state({
        "state_schema": {}, "phases": [{"phase_id": "active"}],
        "completion_conditions": {"all": []},
    })
    player_only_state["work_items"] = {
        "player_report": {
            "required": True, "status": "promised", "owner_id": "player",
            "target_id": "", "promised_turn": 1,
        },
        "owner_report": {
            "required": True, "status": "promised", "owner_id": "owner",
            "target_id": "", "promised_turn": 2,
        },
    }
    player_focus = prepare_turn_governance(
        player_only_state, characters=[owner], turn_id=4,
        safety_max_turns=10, max_stagnant_turns=6,
    )["progress"]["focus"]
    assert player_focus["issue"] == "work:owner_report"
    assert player_focus["owner_ids"] == ["owner"]
    promised_signature = task_progress_signature(event_state)
    apply_evaluator_updates(
        task_config={"state_schema": {}, "phases": [{"phase_id": "active"}], "completion_conditions": {"all": []}},
        state=event_state,
        parsed={"updates": [], "events": [{
            "event_type": "artifact_offered", "subject": "capacity evidence",
            "status": "proposed", "actor_id": "owner",
            "summary": "Same promise again.",
            "evidence": [{"speaker_id": "owner", "quote": "I will send the capacity evidence"}],
        }]},
        characters=[owner], player_text="",
        npc_turns=[{"speaker_id": "owner", "content": "I will send the capacity evidence."}],
    )
    assert task_progress_signature(event_state) == promised_signature
    apply_evaluator_updates(
        task_config={"state_schema": {}, "phases": [{"phase_id": "active"}], "completion_conditions": {"all": []}},
        state=event_state,
        parsed={"updates": [], "events": [{
            "event_type": "artifact_submitted", "subject": "capacity evidence",
            "status": "completed", "actor_id": "owner",
            "summary": "Capacity evidence delivered with figures.",
            "evidence": [{"speaker_id": "owner", "quote": "Here is the capacity evidence"}],
        }]},
        characters=[owner], player_text="",
        npc_turns=[{"speaker_id": "owner", "content": "Here is the capacity evidence: 5,200 units monthly."}],
    )
    assert event_state["work_items"]["capacity_evidence"]["status"] == "submitted"
    assert task_progress_signature(event_state) != promised_signature
    submitted_signature = task_progress_signature(event_state)
    apply_evaluator_updates(
        task_config={"state_schema": {}, "phases": [{"phase_id": "active"}], "completion_conditions": {"all": []}},
        state=event_state,
        parsed={"updates": [], "events": [{
            "event_type": "artifact_reviewed", "subject": "capacity evidence details",
            "work_item_key": "capacity_evidence", "status": "completed", "actor_id": "owner",
            "summary": "Capacity evidence reviewed.",
            "evidence": [{"speaker_id": "owner", "quote": "I reviewed the capacity evidence"}],
        }]},
        characters=[owner], player_text="",
        npc_turns=[{"speaker_id": "owner", "content": "I reviewed the capacity evidence."}],
    )
    assert event_state["work_items"]["capacity_evidence"]["status"] == "completed"
    assert task_progress_signature(event_state) != submitted_signature

    invalid_review_state = initial_task_state({
        "state_schema": {}, "phases": [{"phase_id": "active"}],
        "completion_conditions": {"all": []},
    })
    apply_evaluator_updates(
        task_config={"state_schema": {}, "phases": [{"phase_id": "active"}], "completion_conditions": {"all": []}},
        state=invalid_review_state,
        parsed={"updates": [], "events": [{
            "event_type": "artifact_reviewed", "subject": "unsubmitted report",
            "status": "completed", "actor_id": "owner",
            "summary": "Claims to review a missing report.",
            "evidence": [{"speaker_id": "owner", "quote": "I reviewed the report"}],
        }]},
        characters=[owner], player_text="",
        npc_turns=[{"speaker_id": "owner", "content": "I reviewed the report."}],
    )
    assert "unsubmitted_report" not in invalid_review_state["work_items"]
    assert invalid_review_state["event_ledger"][-1]["transition_valid"] is False

    info_state = initial_task_state({
        "state_schema": {}, "phases": [{"phase_id": "active"}],
        "completion_conditions": {"all": []},
    })
    apply_evaluator_updates(
        task_config={"state_schema": {}, "phases": [{"phase_id": "active"}], "completion_conditions": {"all": []}},
        state=info_state,
        parsed={"updates": [], "events": [{
            "event_type": "information_provided", "subject": "service impact details",
            "status": "completed", "actor_id": "owner",
            "summary": "Impact facts provided.",
            "evidence": [{"speaker_id": "owner", "quote": "The outage affects payment traffic"}],
        }]},
        characters=[owner], player_text="",
        npc_turns=[{"speaker_id": "owner", "content": "The outage affects payment traffic only."}],
    )
    assert info_state["work_items"]["service_impact"]["status"] == "completed"

    closure_state = initial_task_state(cross_turn_config)
    closure_state["variables"]["outcome"].update(value=True, status="proposed")
    apply_evaluator_updates(
        task_config=cross_turn_config, state=closure_state,
        parsed={"updates": [], "events": []}, characters=[owner],
        player_text="The meeting is now adjourned.", npc_turns=[],
    )
    assert closure_state["completion_status"] == "deferred"
    assert closure_state["outcome"]["status"] == "explicit_closure"
    set_progress_metadata(event_state, stagnant_turns=3, turn_id=7, progress_made=False)
    assert public_task_result(event_state)["progress"]["stagnant_turns"] == 3
    stalled = finalize_stalled_task_state(event_state, turn_id=10)
    assert stalled["completion_status"] == "stalled"
    assert stalled["outcome"]["type"] == "stalled"

    pending = pending_public_questions([
        {"speaker_id": "user", "speaker_type": "user", "content": "Please advise."},
        {"speaker_id": "first", "speaker_type": "npc", "content": "Can you provide the evidence?"},
        {"speaker_id": "second", "speaker_type": "npc", "content": "What decision do you recommend?"},
    ])
    assert [row["speaker_id"] for row in pending] == ["first", "second"]

    chars = [
        SimpleNamespace(character_id="first", display_name="First", character_name="First", job_title="Lead", aliases=[], sort_order=0),
        SimpleNamespace(character_id="second", display_name="Second", character_name="Second", job_title="Advisor", aliases=[], sort_order=1),
    ]
    assert orch_support.match_mentioned_characters("Second, answer before First.", chars) == ["second", "first"]
    assert [
        char.character_id for char in generative_orchestrator._agent_order(
            chars, [], [], ["second"]
        )
    ] == ["second", "first"]
    print("NPC speech safety and task-state smoke test: ok")


if __name__ == "__main__":
    main()
