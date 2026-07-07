"""Detect reply language and build LLM language instructions."""

from __future__ import annotations


def detect_reply_language(user_input: str, ui_locale: str | None = None) -> str:
    """Return 'zh' or 'en' for user-visible NPC speech."""
    text = (user_input or "").strip()
    cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    latin = sum(1 for c in text if c.isascii() and c.isalpha())

    if cjk >= 2 or (cjk >= 1 and latin == 0):
        return "zh"
    if latin >= 3:
        return "en"
    if ui_locale in ("en", "zh"):
        return ui_locale
    return "zh"


def speech_language_rule(lang: str) -> str:
    if lang == "en":
        return "- Reply in English. Match the language of the user's latest message."
    return "- 用中文回复，与用户最近一条消息使用相同语言。"


def decision_language_rule(lang: str) -> str:
    if lang == "en":
        return (
            "【Language】All user-visible fields (speak.content, and speak-related reasoning) "
            "must be in English, matching the user's latest message."
        )
    return "【语言】所有面向用户的字段（speak.content 及相关 reasoning）必须使用中文，与用户最近一条消息一致。"


def idle_ack(lang: str) -> str:
    return "Mm, I'm listening." if lang == "en" else "（嗯，我在听。）"


def processing_message(stage: str, lang: str, **kwargs: str) -> str:
    name = kwargs.get("name", "")
    if lang == "en":
        messages = {
            "seed_and_plan": "Initializing seed memories and action plans...",
            "perceive": "Agents perceiving world line and retrieving memories...",
            "agent_tick": f"{name} perceiving → retrieving → deciding → acting...",
        }
    else:
        messages = {
            "seed_and_plan": "初始化 Agent 种子记忆与行动计划...",
            "perceive": "各 Agent 正在感知世界线并检索记忆...",
            "agent_tick": f"{name} 感知 → 检索 → 决策 → 行动...",
        }
    return messages.get(stage, stage)


CHARACTER_EN_NAMES: dict[str, str] = {
    "supplier_ceo": "Mr. Wang (Supplier CEO)",
    "legal_counsel": "Attorney Li (Legal)",
    "procurement_ally": "Manager Zhang (Procurement Ally)",
}


def character_display_name(character_id: str, fallback: str, lang: str) -> str:
    if lang == "en":
        return CHARACTER_EN_NAMES.get(character_id, fallback)
    return fallback


def observation_user_speech(content: str, lang: str) -> str:
    if lang == "en":
        return f'Buyer said: "{content}"'
    return f"采购方说：「{content}」"


def observation_self_speech(content: str, lang: str) -> str:
    if lang == "en":
        return f'I just said: "{content}"'
    return f"我刚才说：「{content}」"


def observation_other_speech(name: str, content: str, lang: str) -> str:
    if lang == "en":
        return f'{name} said: "{content}"'
    return f"{name} 说：「{content}」"


def observation_state_change(content: str, lang: str) -> str:
    if lang == "en":
        return f"Environment change: {content}"
    return f"环境变化：{content}"


def action_wait_message(display_name: str, lang: str) -> str:
    if lang == "en":
        return f"{display_name} chose to wait and did not speak this turn"
    return f"{display_name} 选择观望，暂不发言"


def action_speak_summary(content: str, lang: str) -> str:
    if lang == "en":
        return f'Spoke: "{content}"'
    return f"发言：「{content}」"


def action_plan_update(plan_text: str, lang: str) -> str:
    if lang == "en":
        return f"Updated plan: {plan_text}"
    return f"更新计划：{plan_text}"


def action_internal_note(note: str, lang: str) -> str:
    if lang == "en":
        return f"(Inner note) {note}"
    return f"（内心）{note}"


def action_internal_summary(note: str, lang: str) -> str:
    if lang == "en":
        return f"Inner note: {note}"
    return f"内心整理：{note}"

