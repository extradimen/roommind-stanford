"""Regression checks for public NPC speech safety."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


module_path = Path(__file__).parents[1] / "app" / "agent" / "speech_safety.py"
spec = spec_from_file_location("speech_safety", module_path)
assert spec and spec.loader
speech_safety = module_from_spec(spec)
spec.loader.exec_module(speech_safety)

PUBLIC_RESPONSE_DRAFT = speech_safety.PUBLIC_RESPONSE_DRAFT
speech_rejection_reason = speech_safety.speech_rejection_reason
player_speech_rejection_reason = speech_safety.player_speech_rejection_reason

progress_path = Path(__file__).parents[1] / "app" / "session_progress.py"
progress_spec = spec_from_file_location("session_progress", progress_path)
assert progress_spec and progress_spec.loader
session_progress = module_from_spec(progress_spec)
progress_spec.loader.exec_module(session_progress)


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
    phases = ["opening", "discovery", "bargaining", "closing"]
    assert session_progress.infer_session_phase(
        phases,
        turn_id=3,
        player_text="We propose 86 RMB with payment terms.",
        npc_texts=["Our price is 88 RMB."],
    ) == "bargaining"
    assert session_progress.has_mutual_agreement(
        "This is our final offer; can we agree?",
        ["That works. We have a deal."],
        turn_id=4,
    )
    assert session_progress.infer_session_phase(
        phases,
        turn_id=4,
        player_text="Let’s shake and move forward together.",
        npc_texts=["I need to review the proposal."],
    ) == "closing"
    print("NPC speech safety smoke test: ok")


if __name__ == "__main__":
    main()
