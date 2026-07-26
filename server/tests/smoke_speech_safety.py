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
        "Thank you for the proposal. We can review the full package together."
    ) is None
    assert "bottom line" not in PUBLIC_RESPONSE_DRAFT.casefold()
    assert "active plan" not in PUBLIC_RESPONSE_DRAFT.casefold()
    print("NPC speech safety smoke test: ok")


if __name__ == "__main__":
    main()
