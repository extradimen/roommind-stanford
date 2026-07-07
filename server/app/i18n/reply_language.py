"""NPC dialogue language — English only for stability."""

from __future__ import annotations

REPLY_LANGUAGE = "en"


def detect_reply_language(user_input: str, ui_locale: str | None = None) -> str:
    """All user-visible NPC dialogue is English."""
    return REPLY_LANGUAGE


def speech_language_rule(lang: str = REPLY_LANGUAGE) -> str:
    return "- Reply in English only."


def decision_language_rule(lang: str = REPLY_LANGUAGE) -> str:
    return (
        "[Language] All user-visible fields (speak.content and speak-related reasoning) "
        "must be in English."
    )


def plan_fallback_text(responsibility: str, lang: str = REPLY_LANGUAGE) -> str:
    resp = (responsibility or "the negotiation").strip()
    return f"Focus on {resp}. Advance proactively while holding firm on core limits."


def idle_ack(lang: str = REPLY_LANGUAGE) -> str:
    return "Mm, I'm listening."


def processing_message(stage: str, lang: str = REPLY_LANGUAGE, **kwargs: str) -> str:
    name = kwargs.get("name", "")
    messages = {
        "seed_and_plan": "Initializing seed memories and action plans...",
        "perceive": "Agents perceiving world line and retrieving memories...",
        "agent_tick": f"{name} perceiving → retrieving → deciding → acting...",
    }
    return messages.get(stage, stage)


CHARACTER_EN_NAMES: dict[str, str] = {
    "supplier_ceo": "Mr. Wang (Supplier CEO)",
    "legal_counsel": "Attorney Li (Legal)",
    "procurement_ally": "Manager Zhang (Procurement Ally)",
}


def character_display_name(character_id: str, fallback: str, lang: str = REPLY_LANGUAGE) -> str:
    return CHARACTER_EN_NAMES.get(character_id, fallback)


def observation_user_speech(content: str, lang: str = REPLY_LANGUAGE, speaker_name: str = "") -> str:
    label = (speaker_name or "Buyer lead").strip()
    return f'{label} said: "{content}"'


def observation_self_speech(content: str, lang: str = REPLY_LANGUAGE) -> str:
    return f'I just said: "{content}"'


def observation_other_speech(name: str, content: str, lang: str = REPLY_LANGUAGE) -> str:
    return f'{name} said: "{content}"'


def observation_state_change(content: str, lang: str = REPLY_LANGUAGE) -> str:
    return f"Environment change: {content}"


def action_wait_message(display_name: str, lang: str = REPLY_LANGUAGE) -> str:
    return f"{display_name} chose to wait and did not speak this turn"


def action_speak_summary(content: str, lang: str = REPLY_LANGUAGE) -> str:
    return f'Spoke: "{content}"'


def action_plan_update(plan_text: str, lang: str = REPLY_LANGUAGE) -> str:
    return f"Updated plan: {plan_text}"


def action_internal_note(note: str, lang: str = REPLY_LANGUAGE) -> str:
    return f"(Inner note) {note}"


def action_internal_summary(note: str, lang: str = REPLY_LANGUAGE) -> str:
    return f"Inner note: {note}"
