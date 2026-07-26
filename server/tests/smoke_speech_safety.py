"""Regression checks for public NPC speech safety."""

from app.agent.speech_safety import (
    PUBLIC_RESPONSE_DRAFT,
    player_speech_rejection_reason,
    speech_rejection_reason,
)
from app.task_state import evaluate_conditions, initial_task_state


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
    print("NPC speech safety and task-state smoke test: ok")


if __name__ == "__main__":
    main()
