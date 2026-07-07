"""Stanford-style generative agent configuration defaults."""

from typing import Any

ORCHESTRATION_MODE = "generative"


def default_llm_roles() -> dict[str, Any]:
    return {
        "npc_default": {
            "provider": "siliconflow",
            "model": "moonshotai/Kimi-K2.5",
            "temperature": 0.7,
            "max_tokens": 512,
        },
        "decision": {
            "provider": "siliconflow",
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "temperature": 0.4,
            "max_tokens": 512,
        },
        "reflection": {
            "provider": "siliconflow",
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "temperature": 0.3,
            "max_tokens": 256,
        },
    }


def merge_llm_roles(raw: dict[str, Any] | None) -> dict[str, Any]:
    base = default_llm_roles()
    if not raw:
        return base
    merged = dict(base)
    for key, val in raw.items():
        if isinstance(val, dict) and key in merged:
            merged[key] = {**merged[key], **val}
        elif isinstance(val, dict):
            merged[key] = val
    return merged


def default_orchestration_config() -> dict[str, Any]:
    return {
        "llm_roles": default_llm_roles(),
        "agent": {
            "label": "生成式 Agent（斯坦福小镇）",
            "description": "世界线 + 独立记忆流：感知 → 检索 → 推理 → 行动",
            "max_speakers_per_turn": 2,
            "retrieval_k": 10,
            "retrieval_alpha": 1.0,
            "retrieval_beta": 1.0,
            "retrieval_gamma": 1.0,
            "reflection_importance_threshold": 18.0,
            "working_message_limit": 30,
        },
    }


def merge_orchestration_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    base = default_orchestration_config()
    if not raw:
        return base

    merged = dict(base)
    if isinstance(raw.get("llm_roles"), dict):
        merged["llm_roles"] = merge_llm_roles(raw["llm_roles"])

    agent = dict(base["agent"])
    # Migrate legacy nested modes.generative
    if isinstance(raw.get("modes"), dict):
        legacy = raw["modes"].get("generative") or raw["modes"].get("agent") or {}
        if isinstance(legacy, dict):
            agent.update({k: v for k, v in legacy.items() if k not in ("enabled", "label", "description")})
            legacy_mem = legacy.get("memory")
            if isinstance(legacy_mem, dict):
                agent.update(legacy_mem)
    if isinstance(raw.get("agent"), dict):
        agent.update(raw["agent"])
    merged["agent"] = agent
    return merged


def agent_config(config: dict[str, Any] | None) -> dict[str, Any]:
    return dict(merge_orchestration_config(config).get("agent", {}))
