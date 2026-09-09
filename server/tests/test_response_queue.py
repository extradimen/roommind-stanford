import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.world.response_queue import ResponseQueue


class QueueTests(unittest.TestCase):
    def test_new_question_preserves_prior_history_without_duplicate_owner_block(self):
        q = ResponseQueue({})
        q.request("old", "user", ["a", "b"])
        q.blocked("a")
        q.request("new", "user", ["a"], first=True)
        q.answered("a", "m:4")
        self.assertEqual(q.pending(), ["b"])
        old = next(row for row in q.data["entries"] if row["request_id"] == "old" and row["target"] == "a")
        self.assertEqual(old["status"], "superseded")
        self.assertIsNone(old["answer"])

    def test_order_block_restart_nested_and_terminal(self):
        state = {}
        q = ResponseQueue(state)
        q.request("u:1", "user", ["a", "b"])
        self.assertFalse(q.can_respond("b"))
        with self.assertRaises(ValueError):
            q.answered("b", "wrong")
        q.blocked("a")
        q.save(state)
        q = ResponseQueue(json.loads(json.dumps(state)))
        self.assertEqual(q.pending(), ["a", "b"])
        q.answered("a", "m:2")
        q.request("a:2", "a", ["c"], first=True)
        self.assertEqual(q.pending(), ["c", "b"])
        q.answered("c", "m:3")
        q.close()
        self.assertEqual(q.pending(), [])
        b = next(row for row in q.data["entries"] if row["target"] == "b")
        self.assertEqual(b["status"], "closed_unanswered")
        self.assertIsNone(b["answer"])


class OrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_owner_is_not_replaced_then_resumes_in_order(self):
        from app.orchestrator.generative import generative_orchestrator
        from app.agent.act import ActionResult
        from app.models.db import CharacterTemplate, ScenarioTemplate
        chars = [CharacterTemplate(character_id=cid, character_name=name, display_name=name, job_title=name,
                                   aliases=[name], sort_order=i)
                 for i, (cid, name) in enumerate([("a", "Alice"), ("b", "Bob")])]
        scenario = ScenarioTemplate(title="Queue test", task_config={}, characters=chars,
                                    scene_config={})
        binding = SimpleNamespace(label=lambda: "test/test")
        seen = []
        responding = False

        async def tick(*args, **kwargs):
            cid = kwargs["character"].character_id
            seen.append(cid)
            return SimpleNamespace(
                action_result=ActionResult(character_id=cid, action="speak" if responding else "wait",
                                           spoke=responding, content=f"Reply from {cid}." if responding else ""),
                action="speak", reasoning="", new_observations=[], retrieved=[],
                decision_raw="", plan_update=None)

        async def stream(*args):
            if False:
                yield {}

        async def run(state, turn):
            events = [evt async for evt in generative_orchestrator.process_turn_stream(
                None, session_id=1, scenario=scenario, characters=chars, dispatch_rules=[],
                user_input="Alice and Bob, please answer.", messages=[], current_phase="opening",
                shared_state=state, orchestration_config={}, user_turn_count=turn)]
            return events[-1]

        with patch("app.orchestrator.generative.orch_support.get_llm_config", new=AsyncMock(return_value={})), \
             patch("app.orchestrator.generative.resolve_llm", return_value=binding), \
             patch("app.orchestrator.generative.AgentMemoryStore.load_all", new=AsyncMock(return_value=[])), \
             patch("app.orchestrator.generative.ensure_seed_memories", new=AsyncMock(return_value=[])), \
             patch("app.orchestrator.generative.ensure_initial_plan", new=AsyncMock()), \
             patch("app.orchestrator.generative.maybe_reflect", new=AsyncMock(return_value=([], 0, ""))), \
             patch("app.orchestrator.generative.run_agent_tick", side_effect=tick), \
             patch("app.orchestrator.generative.execute_plan_fallback_speak", new=AsyncMock(return_value=None)), \
             patch("app.orchestrator.generative.yield_speech_stream", side_effect=stream), \
             patch("app.orchestrator.generative.resolve_direct_question_targets", side_effect=[["a", "b"], []]), \
             patch("app.orchestrator.generative.resolve_direct_question_target", return_value=None):
            first = await run({}, 1)
            self.assertEqual(seen, ["a"])
            self.assertEqual(first["replies"], [])
            state = json.loads(json.dumps(first["shared_state"]))
            self.assertEqual(state["_pending_responses"], ["a", "b"])
            responding = True
            second = await run(state, 2)
            self.assertEqual(seen, ["a", "a", "b"])
            self.assertEqual(second["shared_state"]["_pending_responses"], [])
            self.assertEqual(len(second["replies"]), 2)


if __name__ == "__main__":
    unittest.main()
