"""Generative agent memory stream — Stanford-style observation / reflection / plan / act."""

from app.agent.act import (
    ActionResult,
    AgentDecision,
    action_to_npc_reply,
    decision_from_llm,
    execute_decision,
    execute_plan_fallback_speak,
    render_npc_speech,
)
from app.agent.memory_stream import AgentMemoryStore, MemoryNode, retrieve_memories
from app.agent.reflect import maybe_reflect
from app.agent.loop import AgentLoopResult, run_agent_tick

__all__ = [
    "ActionResult",
    "AgentDecision",
    "AgentLoopResult",
    "AgentMemoryStore",
    "MemoryNode",
    "action_to_npc_reply",
    "decision_from_llm",
    "execute_decision",
    "execute_plan_fallback_speak",
    "maybe_reflect",
    "render_npc_speech",
    "retrieve_memories",
    "run_agent_tick",
]
