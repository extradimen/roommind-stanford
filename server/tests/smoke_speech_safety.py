"""Regression checks for public NPC speech safety."""

from app.agent.speech_safety import (
    PUBLIC_RESPONSE_DRAFT,
    player_speech_rejection_reason,
    speech_rejection_reason,
)
from app.task_state import advance_phase, evaluate_conditions, initial_task_state, normalize_evaluator_payload
from app.player_agent import normalize_player_content


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
    print("NPC speech safety and task-state smoke test: ok")


if __name__ == "__main__":
    main()
