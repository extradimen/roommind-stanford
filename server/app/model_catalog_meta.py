"""Classify catalog models as chat vs reasoning for admin UI hints."""

from __future__ import annotations

import re
from typing import Any, Literal

ModelKind = Literal["chat", "reasoning"]

# Explicit overrides win over pattern rules.
_EXPLICIT_KIND: dict[str, ModelKind] = {
    "glm-5.1": "reasoning",
    "glm-5": "reasoning",
    "glm-4.7": "reasoning",
    "kimi-k2.5:cloud": "reasoning",
    "moonshotai/Kimi-K2.5": "reasoning",
    "Qwen/Qwen2.5-7B-Instruct": "chat",
    "Qwen/Qwen3-8B": "reasoning",
    "deepseek-ai/DeepSeek-V4-Flash": "chat",
    "deepseek-v3.2:cloud": "chat",
    "gpt-oss:120b:cloud": "chat",
}

_RECOMMENDED_GLOBAL: dict[str, set[str]] = {
    "ollama": {"deepseek-v3.2:cloud", "gpt-oss:120b:cloud"},
    "siliconflow": {"Qwen/Qwen2.5-7B-Instruct", "deepseek-ai/DeepSeek-V4-Flash"},
}

_REASONING_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"glm[-.]?[45]", re.I),
    re.compile(r"qwen3", re.I),
    re.compile(r"kimi[- ]?k2", re.I),
    re.compile(r"deepseek[- ]?r1", re.I),
    re.compile(r"\b(o1|o3)\b", re.I),
    re.compile(r"thinking|reasoner|reasoning", re.I),
)

_CHAT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"instruct", re.I),
    re.compile(r"qwen2\.?5", re.I),
    re.compile(r"flash", re.I),
    re.compile(r"gpt-oss", re.I),
    re.compile(r"deepseek-v3", re.I),
    re.compile(r"llama.*instruct", re.I),
    re.compile(r"mistral", re.I),
)


def classify_model_kind(model_id: str, provider: str = "") -> ModelKind:
    mid = (model_id or "").strip()
    if not mid:
        return "chat"
    if mid in _EXPLICIT_KIND:
        return _EXPLICIT_KIND[mid]
    lower = mid.lower()
    for pat in _REASONING_PATTERNS:
        if pat.search(lower):
            return "reasoning"
    for pat in _CHAT_PATTERNS:
        if pat.search(lower):
            return "chat"
    # Ollama cloud tags without "instruct" are often reasoning-first today.
    if provider == "ollama" and ":cloud" in lower:
        return "reasoning"
    return "chat"


def is_recommended_global(model_id: str, provider: str) -> bool:
    return model_id.strip() in _RECOMMENDED_GLOBAL.get(provider, set())


def enrich_model_option(item: dict[str, Any], provider: str) -> dict[str, Any]:
    mid = str(item.get("id") or "").strip()
    kind = classify_model_kind(mid, provider)
    recommended = is_recommended_global(mid, provider)
    out = dict(item)
    out["kind"] = kind
    out["recommended"] = recommended
    return out


def enrich_provider_catalog(catalog: list[dict[str, str]], provider: str) -> list[dict[str, Any]]:
    enriched = [enrich_model_option(item, provider) for item in catalog]
    enriched.sort(
        key=lambda m: (
            0 if m.get("recommended") else 1,
            0 if m.get("kind") == "chat" else 1,
            str(m.get("id", "")).lower(),
        )
    )
    return enriched


def model_guidance_meta() -> dict[str, Any]:
    return {
        "kinds": {
            "chat": {
                "label_en": "Chat",
                "label_zh": "对话型",
                "summary_en": (
                    "Direct replies in content. Best default for NPC lines, short plans, and low latency. "
                    "Max tokens 512–2048 is usually enough."
                ),
                "summary_zh": (
                    "回答直接进入 content，适合 NPC 台词、短计划、低延迟。Max tokens 通常 512–2048 即可。"
                ),
            },
            "reasoning": {
                "label_en": "Reasoning",
                "label_zh": "推理型",
                "summary_en": (
                    "Uses internal reasoning before content. Needs higher max_tokens (≥1024 for opening plans). "
                    "If content is empty, raise max_tokens or pick a chat model for global default."
                ),
                "summary_zh": (
                    "先内部推理再输出 content。开局计划等步骤建议 max_tokens ≥1024。"
                    "若出现空回复，请提高 max_tokens 或改用对话型模型作为全局默认。"
                ),
            },
        },
        "roommind_recommendation_en": (
            "Recommended global default: a Chat model (e.g. Qwen2.5-7B-Instruct on SiliconFlow, "
            "or deepseek-v3.2:cloud / gpt-oss:120b:cloud on Ollama). "
            "Use Reasoning models for Agent decision roles only if max_tokens is high enough."
        ),
        "roommind_recommendation_zh": (
            "建议全局默认使用对话型（Chat）模型，例如 SiliconFlow 的 Qwen2.5-7B-Instruct，"
            "或 Ollama 的 deepseek-v3.2:cloud / gpt-oss:120b:cloud。"
            "推理型模型可用于 Agent 决策，但需足够高的 max_tokens（计划生成建议 ≥1024）。"
        ),
    }
