import copy
import json
import tempfile
import unittest
from pathlib import Path

from app.factorial_study import freeze_design
from app.g5.memory import MemoryCognition
from app.g5.runtime import Runtime
from app.g5.world import Decision, World
from test_g5_runtime import manifest, spec


def view():
    return {"actor": "sre", "memory_scope": "world-one", "cognition_state": {},
            "facts": {"staffing": {"value": "two missing shifts", "source": "scenario", "disclosable": True}},
            "observations": [{"event_id": "e1", "kind": "claim", "actor": "security",
                              "content": "Staffing is complete."}]}


class MemoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_ingestion_idempotent_claim_not_fact(self):
        cognition = MemoryCognition()
        initial = view()
        first = await cognition(initial)
        initial["cognition_state"] = first
        second = await cognition(initial)
        self.assertEqual(first, second)
        self.assertEqual([n["kind"] for n in second["nodes"]], ["fact", "claim"])
        self.assertEqual(second["nodes"][1]["source"], "e1")

    async def test_world_role_and_config_mismatch_rejected(self):
        cognition = MemoryCognition()
        state = await cognition(view())
        for field, replacement in (("actor", "security"), ("memory_scope", "other-world")):
            changed = view()
            changed["cognition_state"] = state
            changed[field] = replacement
            with self.assertRaises(ValueError):
                await cognition(changed)
        changed = view()
        changed["cognition_state"] = state
        with self.assertRaises(ValueError):
            await MemoryCognition(top_k=1)(changed)

    async def test_fact_update_retains_old_source_as_historical(self):
        cognition = MemoryCognition(top_k=10)
        state = await cognition(view())
        updated = view()
        updated["cognition_state"] = state
        updated["facts"]["staffing"] = {"value": "filled", "source": "receipt2", "disclosable": True}
        result = await cognition(updated)
        self.assertEqual(result["nodes"][:2], state["nodes"])
        retrieved = result["context"]["retrieved"]
        historical = [n for n in retrieved if n["kind"] == "fact" and n["historical_fact"]]
        self.assertEqual(len(historical), 1)
        self.assertEqual(historical[0]["source"], "scenario")

    async def test_top_k_projection_does_not_send_whole_store(self):
        cognition = MemoryCognition(top_k=1)
        state = await cognition(view())
        context = cognition.policy_context(state)
        self.assertEqual(len(context["retrieved"]), 1)
        self.assertNotIn("nodes", context)
        context["retrieved"][0]["text"] = "mutated"
        self.assertNotIn("mutated", json.dumps(state))

    async def test_hybrid_is_explicit_and_invalid_scores_fail(self):
        with self.assertRaises(ValueError):
            MemoryCognition(semantic_scorer=lambda q, t: 0)
        cognition = MemoryCognition(semantic_scorer=lambda q, t: 1, semantic_id="local-test-v1")
        self.assertEqual((await cognition(view()))["context"]["retrieval"], "hybrid")
        invalid = MemoryCognition(semantic_scorer=lambda q, t: float("nan"), semantic_id="invalid")
        with self.assertRaises(ValueError):
            await invalid(view())

    async def test_corrupted_node_rejected(self):
        cognition = MemoryCognition()
        changed = view()
        changed["cognition_state"] = await cognition(changed)
        changed["cognition_state"]["nodes"][0]["text"] = "forged world fact"
        with self.assertRaises(ValueError):
            await cognition(changed)

    async def test_runtime_restart_persists_owner_memory_and_filters_other_roles(self):
        frozen = manifest()
        ordinal = next(row["ordinal"] for row in frozen["assignments"] if row["arm"] == "B")
        seen = []

        async def policy(role_view, feedback):
            seen.append(copy.deepcopy(role_view))
            return Decision("wait")

        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "memory.sqlite")
            world = World(path)
            try:
                runtime = Runtime(world=world, world_id="memory", spec=spec(), manifest=frozen,
                    ordinal=ordinal, policy=policy, max_steps=4, cognition=MemoryCognition())
                await runtime.step()
                first_state = world.observe("memory", "security")[1]["cognition_state"]
                world.close()
                world = World(path)
                runtime = Runtime(world=world, world_id="memory", spec=spec(), manifest=frozen,
                    ordinal=ordinal, policy=policy, max_steps=4, cognition=MemoryCognition())
                await runtime.step()
                await runtime.step()
                self.assertEqual(world.observe("memory", "security")[1]["cognition_state"], first_state)
                self.assertNotIn("protected-source", json.dumps(seen[1]))
                self.assertNotIn("nodes", seen[0]["cognition"])
                self.assertNotIn("cognition_state", seen[2])
                self.assertNotIn("memory_scope", seen[2])
                self.assertEqual(len(world.events("memory")), 3)
            finally:
                world.close()


if __name__ == "__main__":
    unittest.main()
