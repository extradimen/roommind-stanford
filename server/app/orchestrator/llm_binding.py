"""Resolve provider/model per orchestration role and per NPC character."""

from dataclasses import dataclass
from typing import Any

from app.models.db import CharacterTemplate, LLMConfig
from app.orchestrator.defaults import merge_llm_roles, merge_orchestration_config


@dataclass
class ResolvedLlm:
    provider: str | None
    model: str | None
    temperature: float
    max_tokens: int

    def label(self) -> str:
        p = self.provider or "default"
        m = self.model or "default"
        return f"{p}/{m}"


def resolve_llm(
    llm_cfg: LLMConfig | None,
    orchestration_config: dict[str, Any] | None,
    role: str,
    character: CharacterTemplate | None = None,
) -> ResolvedLlm:
    global_prov = llm_cfg.provider if llm_cfg else None
    global_model = llm_cfg.model if llm_cfg else None
    global_temp = llm_cfg.temperature if llm_cfg else 0.7
    global_max = llm_cfg.max_tokens if llm_cfg else 2048

    merged = merge_orchestration_config(orchestration_config)
    roles = merge_llm_roles(merged.get("llm_roles"))

    layer: dict[str, Any] = {}
    if role in ("npc", "npc_default"):
        layer = dict(roles.get("npc_default", {}))
    elif role in roles:
        layer = dict(roles.get(role, {}))

    char_layer: dict[str, Any] = {}
    if character and isinstance(character.llm_config, dict) and character.llm_config:
        char_layer = character.llm_config

    combined = {**layer, **char_layer}

    provider = combined.get("provider") or global_prov
    model = combined.get("model") or global_model
    temperature = float(combined.get("temperature", global_temp))
    max_tokens = int(combined.get("max_tokens", global_max))

    return ResolvedLlm(
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
