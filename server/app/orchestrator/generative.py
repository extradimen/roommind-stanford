"""
Generative agents orchestrator — Stanford Smallville architecture.

Full loop per NPC per turn:
  Seed Memory  (injected once at session start)
      ↓
  Planning     (initial plan generated from seed, persisted as plan node)
      ↓  each turn:
  Perceive → Retrieve → React → Act
      ↓  when importance accumulator ≥ threshold:
  Reflection   (higher-order inference written back to memory stream)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.act import (
    action_to_npc_reply,
    execute_plan_fallback_speak,
    yield_speech_stream,
)
from app.agent.loop import run_agent_tick
from app.agent.memory_stream import AgentMemoryStore
from app.agent.reflect import ensure_initial_plan, ensure_seed_memories, maybe_reflect
from app.models.db import CharacterTemplate, DispatchRule, ScenarioTemplate
from app.orchestrator.common import NPCReply, OrchestratorResult, npc_replies_payload, orch_support
from app.orchestrator.defaults import ORCHESTRATION_MODE, agent_config
from app.orchestrator.llm_binding import resolve_llm
from app.world.timeline import WorldTimeline
from app.i18n.reply_language import processing_message
from app.player_character import resolve_player_character


class GenerativeOrchestrator:
    """
    Each NPC runs an independent memory stream.
    The shared world timeline is the only inter-agent channel.
    """

    async def process_turn_stream(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        scenario: ScenarioTemplate,
        characters: list[CharacterTemplate],
        dispatch_rules: list[DispatchRule],
        user_input: str,
        messages: list[dict[str, Any]],
        current_phase: str,
        shared_state: dict[str, Any],
        orchestration_config: dict[str, Any] | None,
        user_turn_count: int,
        reply_language: str = "en",
    ) -> AsyncIterator[dict[str, Any]]:

        llm_cfg = await orch_support.get_llm_config(db)
        orch_cfg = orchestration_config
        cfg = agent_config(orchestration_config)

        retrieval_k        = int(cfg.get("retrieval_k", 10))
        max_speakers       = int(cfg.get("max_speakers_per_turn", 2))
        reflect_threshold  = float(cfg.get("reflection_importance_threshold", 18.0))
        alpha              = float(cfg.get("retrieval_alpha", 1.0))
        beta               = float(cfg.get("retrieval_beta", 1.0))
        gamma              = float(cfg.get("retrieval_gamma", 1.0))
        msg_limit          = int(cfg.get("working_message_limit", 30))

        updated_state = dict(shared_state or {})
        timeline = WorldTimeline.from_shared_state(updated_state)
        timeline.sync_messages(
            messages[:-1] if messages else [],
            turn_id=max(0, user_turn_count - 1),
        )

        turn_id = user_turn_count
        tick = len([e for e in timeline.events if e.turn_id == turn_id])
        player = resolve_player_character(scenario)

        timeline.append(
            turn_id=turn_id,
            tick=tick,
            event_type="user_speech",
            actor_id="user",
            content=user_input,
            meta={
                "display_name": player["display_name"],
                "character_name": player["character_name"],
                "job_title": player["job_title"],
            },
        )
        tick += 1

        mentioned  = set(orch_support.match_mentioned_characters(user_input, characters))
        rule_hits  = orch_support.match_dispatch_rules(user_input, dispatch_rules)
        agent_order = self._agent_order(characters, mentioned, rule_hits)

        yield {
            "type": "processing",
            "stage": "seed_and_plan",
            "message": processing_message("seed_and_plan", reply_language),
        }

        decision_llm = resolve_llm(llm_cfg, orch_cfg, "decision")
        reflect_llm  = resolve_llm(llm_cfg, orch_cfg, "reflection")
        npc_llm_labels: dict[str, str] = {}
        agent_debug: dict[str, Any] = {}
        accumulators: dict[str, float] = dict(
            updated_state.get("_importance_accumulators") or {}
        )

        # ----------------------------------------------------------------
        # SEED MEMORY + PLANNING  (run once per session, idempotent)
        # Stanford: before any interaction, each agent has seed memories
        # and a coarse plan derived from them.
        # ----------------------------------------------------------------
        for char in characters:
            store = AgentMemoryStore(session_id, char.character_id)
            nodes = await store.load_all(db)

            # Layer 1: seed memories (injected once, never repeated)
            new_seeds = await ensure_seed_memories(
                db, store, character=char, scenario=scenario, nodes=nodes
            )
            if new_seeds:
                nodes.extend(new_seeds)

            # Layer 2: initial plan derived from seed memories
            await ensure_initial_plan(
                db,
                store,
                character=char,
                scenario=scenario,
                decision_llm=decision_llm,
                nodes=nodes,
            )

        yield {
            "type": "processing",
            "stage": "perceive",
            "message": processing_message("perceive", reply_language),
        }

        context     = timeline.speech_context(limit=msg_limit)
        replies: list[NPCReply] = []
        speak_quota = max_speakers

        # ----------------------------------------------------------------
        # PERCEIVE → RETRIEVE → REACT → ACT  (per agent, sequential)
        # ----------------------------------------------------------------
        for char in agent_order:
            cid   = char.character_id
            store = AgentMemoryStore(session_id, cid)
            nodes = await store.load_all(db)

            # Only show events that happened before this agent's tick
            new_events = [e for e in timeline.since_tick(turn_id, 0) if e.tick < tick]

            yield {
                "type": "processing",
                "stage": "agent_tick",
                "message": processing_message("agent_tick", reply_language, name=char.display_name),
                "speaker_id": cid,
            }

            loop_result = await run_agent_tick(
                db,
                character=char,
                scenario=scenario,
                store=store,
                nodes=nodes,
                new_events=new_events,
                user_input=user_input,
                turn_id=turn_id,
                tick=tick,
                conversation_context=context,
                current_phase=current_phase,
                decision_llm=decision_llm,
                npc_llm=resolve_llm(llm_cfg, orch_cfg, "npc", char),
                retrieval_k=retrieval_k,
                retrieval_alpha=alpha,
                retrieval_beta=beta,
                retrieval_gamma=gamma,
                speak_quota_remaining=speak_quota,
                mentioned=cid in mentioned,
                timeline=timeline,
                reply_language=reply_language,
            )
            npc_llm_labels[cid] = resolve_llm(llm_cfg, orch_cfg, "npc", char).label()

            action_result = loop_result.action_result
            agent_debug[cid] = {
                "action":            loop_result.action,
                "reasoning":         loop_result.reasoning,
                "observations_added": len(loop_result.new_observations),
                "retrieved":         loop_result.retrieved,
                "decision_preview":  loop_result.decision_raw,
                "world_events":      len(action_result.world_events) if action_result else 0,
            }
            if action_result and action_result.spoke:
                agent_debug[cid]["spoke_content"] = action_result.content
                agent_debug[cid]["emotion"]        = action_result.emotion
                agent_debug[cid]["gesture"]        = action_result.gesture

            # Accumulate importance for reflection trigger
            acc = accumulators.get(cid, 0.0)
            acc += sum(o.importance for o in loop_result.new_observations)
            accumulators[cid] = acc

            if loop_result.spoke and speak_quota > 0 and action_result:
                speak_quota -= 1
                replies.append(action_to_npc_reply(char, action_result))
                context += f"\n[{char.display_name}]: {loop_result.content}"

                async for evt in yield_speech_stream(char, action_result):
                    yield evt

            if loop_result.plan_update:
                agent_debug[cid]["plan_update"] = loop_result.plan_update

            if action_result and action_result.world_events:
                tick = max(e.tick for e in action_result.world_events) + 1

            # ----------------------------------------------------------------
            # REFLECTION  (triggered by accumulated importance)
            # Stanford: when sum of recent observation importance > threshold,
            # generate higher-order inferences and write back to memory stream.
            # ----------------------------------------------------------------
            nodes = await store.load_all(db)
            new_reflections, accumulators[cid], reflect_text = await maybe_reflect(
                db,
                store,
                character=char,
                nodes=nodes,
                turn_id=turn_id,
                threshold=reflect_threshold,
                accumulator=accumulators[cid],
                reflect_llm=reflect_llm,
                context=context,
            )
            if reflect_text:
                agent_debug[cid]["reflection"]            = reflect_text
                agent_debug[cid]["reflection_node_count"] = len(new_reflections)

        # ----------------------------------------------------------------
        # FALLBACK  (guarantee at least one reply per turn)
        # ----------------------------------------------------------------
        if not replies:
            for char in agent_order:
                if speak_quota <= 0:
                    break
                cid   = char.character_id
                store = AgentMemoryStore(session_id, cid)
                nodes = await store.load_all(db)
                fallback = await execute_plan_fallback_speak(
                    db,
                    character=char,
                    scenario=scenario,
                    store=store,
                    nodes=nodes,
                    user_input=user_input,
                    turn_id=turn_id,
                    tick=tick,
                    conversation_context=context,
                    current_phase=current_phase,
                    npc_llm=resolve_llm(llm_cfg, orch_cfg, "npc", char),
                    timeline=timeline,
                    reply_language=reply_language,
                )
                if not fallback or not fallback.spoke:
                    continue

                speak_quota -= 1
                agent_debug[cid] = {
                    **(agent_debug.get(cid) or {}),
                    "action":        fallback.action,
                    "reasoning":     fallback.reasoning,
                    "fallback_speak": True,
                    "spoke_content": fallback.content,
                    "emotion":       fallback.emotion,
                    "gesture":       fallback.gesture,
                }
                replies.append(action_to_npc_reply(char, fallback))
                context += f"\n[{char.display_name}]: {fallback.content}"

                async for evt in yield_speech_stream(char, fallback):
                    yield evt

                if fallback.world_events:
                    tick = max(e.tick for e in fallback.world_events) + 1
                break

        # ----------------------------------------------------------------
        # PERSIST STATE
        # ----------------------------------------------------------------
        updated_state[WorldTimeline.KEY] = timeline.to_list()
        updated_state["_importance_accumulators"] = accumulators
        updated_state["_last_debug"] = {
            "turn_id":                  turn_id,
            "world_events_this_turn":   len([e for e in timeline.events if e.turn_id == turn_id]),
            "mentioned":                list(mentioned),
            "rule_hits":                rule_hits,
            "agent_order":              [c.character_id for c in agent_order],
            "agents":                   agent_debug,
            "retrieval_weights":        {"alpha": alpha, "beta": beta, "gamma": gamma},
            "reflect_threshold":        reflect_threshold,
            "llm": {
                "decision":   decision_llm.label(),
                "reflection": reflect_llm.label(),
                "npc":        npc_llm_labels,
            },
        }

        yield {
            "type": "turn_result",
            "phase": current_phase,
            "shared_state": updated_state,
            "orchestration_mode": ORCHESTRATION_MODE,
            "replies": npc_replies_payload(replies),
            "_result": OrchestratorResult(
                replies=replies,
                phase=current_phase,
                shared_state=updated_state,
            ),
        }

    def _agent_order(
        self,
        characters: list[CharacterTemplate],
        mentioned: set[str],
        rule_hits: list[str],
    ) -> list[CharacterTemplate]:
        char_map = {c.character_id: c for c in characters}
        ordered: list[CharacterTemplate] = []
        seen: set[str] = set()

        for cid in list(mentioned) + rule_hits:
            if cid in char_map and cid not in seen:
                ordered.append(char_map[cid])
                seen.add(cid)

        rest = sorted(
            [c for c in characters if c.character_id not in seen],
            key=lambda c: c.sort_order,
        )
        ordered.extend(rest)
        return ordered


generative_orchestrator = GenerativeOrchestrator()
