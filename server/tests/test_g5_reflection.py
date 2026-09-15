import copy
import unittest

from app.g5.memory import MemoryCognition
from app.g5.reflection import ReflectiveCognition
from test_g5_memory import view as memory_view


def view():
    result = memory_view()
    result["operations"] = ["contain"]
    return result


async def reflector(context):
    return [{"text": "Staffing may need clarification.", "source_ids": [context["memory"]["retrieved"][0]["id"]]}]


async def planner(context):
    return {"goal": "Clarify readiness", "steps": [{"actor": context["actor"], "intent": "ask",
        "text": "Ask about the staffing gap", "operation": "",
        "source_ids": [context["memory"]["retrieved"][0]["id"]]}]}


def cognition(reflect=reflector, plan=planner):
    return ReflectiveCognition(memory=MemoryCognition(), reflector=reflect, planner=plan,
                              reflector_id="script-reflect-v1", planner_id="script-plan-v1")


class ReflectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_unchanged_observations_do_not_repeat_generation(self):
        calls = []
        async def counted(context):
            calls.append("reflect")
            return await reflector(context)
        adapter = cognition(counted)
        source = view()
        state = await adapter(source)
        source["cognition_state"] = state
        self.assertEqual(await adapter(source), state)
        self.assertEqual(calls, ["reflect"])
        self.assertEqual(state["context"]["hypotheses"][0]["kind"], "hypothesis")
        self.assertEqual(state["context"]["plan"]["kind"], "intention")

    async def test_new_event_replans_without_overwriting_previous_plan(self):
        adapter = cognition()
        source = view()
        first = await adapter(source)
        source["cognition_state"] = copy.deepcopy(first)
        source["observations"].append({"event_id": "e2", "kind": "claim", "actor": "security",
                                       "content": "The scope changed."})
        second = await adapter(source)
        self.assertEqual(second["plans"][0], first["plans"][0])
        self.assertEqual(second["plans"][1]["supersedes"], first["plans"][0]["id"])
        self.assertEqual(first["memory"]["nodes"][0]["kind"], "fact")
        self.assertFalse(any(n["kind"] == "hypothesis" for n in second["memory"]["nodes"]))

    async def test_invented_or_duplicate_sources_rejected(self):
        for ids in (["invisible-source"], [], ["x", "x"]):
            async def forged(context):
                return [{"text": "Unfounded belief", "source_ids": ids}]
            with self.assertRaises(ValueError):
                await cognition(forged)(view())

    async def test_role_substitution_or_unknown_operation_rejected(self):
        for mutation in ("actor", "operation"):
            async def invalid(context):
                proposal = await planner(context)
                if mutation == "actor":
                    proposal["steps"][0]["actor"] = "security"
                else:
                    proposal["steps"][0].update(intent="execute", operation="real-world-upload")
                return proposal
            with self.assertRaises(ValueError):
                await cognition(plan=invalid)(view())

    async def test_protected_source_does_not_become_disclosable_reflection(self):
        source = view()
        source["observations"] = []
        source["facts"]["staffing"]["disclosable"] = False
        result = await cognition()(source)
        self.assertFalse(result["context"]["hypotheses"][0]["disclosable"])

    async def test_failed_planning_does_not_mutate_saved_state(self):
        source = view()
        first = await cognition()(source)
        source["cognition_state"] = copy.deepcopy(first)
        source["observations"].append({"event_id": "e2", "kind": "claim", "actor": "security", "content": "New scope"})
        async def failure(context):
            raise TimeoutError("scripted failure")
        with self.assertRaises(TimeoutError):
            await cognition(plan=failure)(source)
        self.assertEqual(source["cognition_state"], first)

    async def test_corrupt_history_and_cross_world_state_fail(self):
        source = view()
        first = await cognition()(source)
        source["cognition_state"] = copy.deepcopy(first)
        source["cognition_state"]["plans"][0]["proposal"]["goal"] = "tampered"
        with self.assertRaises(ValueError):
            await cognition()(source)
        source["cognition_state"] = first
        source["memory_scope"] = "another-world"
        with self.assertRaises(ValueError):
            await cognition()(source)

    async def test_runtime_commits_cognition_without_executing_plan(self):
        from app.g5.runtime import Runtime
        from app.g5.world import World, Decision
        from test_g5_runtime import spec, manifest
        world = World(":memory:")
        self.addCleanup(world.close)
        frozen = manifest()
        ordinal = next(row["ordinal"] for row in frozen["assignments"] if row["arm"] == "B")
        seen = []

        async def policy(context, feedback):
            seen.append(copy.deepcopy(context))
            return Decision("wait")

        runtime = Runtime(world=world, world_id="reflect", spec=spec(), manifest=frozen,
                          ordinal=ordinal, policy=policy, max_steps=4, cognition=cognition())
        await runtime.step()
        await runtime.step()
        await runtime.step()
        saved = world.observe("reflect", "security")[1]["cognition_state"]
        self.assertEqual(len(saved["plans"]), 1)
        self.assertFalse(world.facts("reflect")["contained"]["value"])
        self.assertEqual(seen[0]["cognition"]["plan"]["kind"], "intention")
        self.assertNotIn("plans", seen[0]["cognition"])


if __name__ == "__main__":
    unittest.main()
