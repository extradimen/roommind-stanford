import copy
import unittest

from app.factorial_study import ARMS, digest, freeze_design
from app.g5.components import specification
from app.g5.memory import MemoryCognition
from app.g5.reflection import ReflectiveCognition
from app.g5.runtime import Review, Runtime
from app.g5.world import Decision, World
from test_g5_inputs_attempts import cards
from test_g5_runtime import spec, manifest


class Policy:
    specification = {"adapter": "script-policy-v1"}
    async def __call__(self, view, feedback):
        return Decision("wait")


class Governance:
    specification = {"adapter": "script-governance-v1"}
    async def __call__(self, view, decision):
        return Review(True)


def strict_manifest():
    design = manifest()["design"]
    components = {"policy": specification(Policy()), "cognition": specification(MemoryCognition()),
                  "governance": specification(Governance())}
    design["components"] = components
    for arm in design["arms"].values():
        arm["shared"]["model_bindings_sha256"] = digest(components)
        arm["shared"]["role_inputs_sha256"] = digest(cards())
    return freeze_design(design)


class ComponentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.world = World(":memory:")
        self.addCleanup(self.world.close)

    def runtime(self, arm, cognition=None, policy=None, role_inputs=True):
        frozen = strict_manifest()
        return Runtime(world=self.world, world_id=arm, spec=spec(), manifest=frozen,
            ordinal=next(r["ordinal"] for r in frozen["assignments"] if r["arm"] == arm),
            policy=policy or Policy(), cognition=cognition,
            governance=Governance() if ARMS[arm]["governance"] else None,
            max_steps=4, role_inputs=cards() if role_inputs else None)

    async def test_all_four_arms_accept_matching_components(self):
        for arm in ARMS:
            runtime = self.runtime(arm, MemoryCognition() if ARMS[arm]["cognition"] else None)
            await runtime.step()
            self.assertEqual(len(self.world.events(arm)), 1)

    async def test_changed_retrieval_config_rejected_before_world_creation(self):
        with self.assertRaisesRegex(ValueError, "specification changed"):
            self.runtime("B", MemoryCognition(top_k=1))
        with self.assertRaises(ValueError):
            self.world.definition("B")

    async def test_mid_run_mutation_cannot_commit(self):
        memory = MemoryCognition()
        runtime = self.runtime("B", memory)
        await runtime.step()
        memory.top_k = 1
        with self.assertRaises(ValueError):
            await runtime.step()
        self.assertEqual(len(self.world.events("B")), 1)

    async def test_mutation_during_policy_blocks_commit(self):
        class Mutating(Policy):
            async def __call__(self, view, feedback):
                self.specification = {"adapter": "changed"}
                return Decision("wait")
        runtime = self.runtime("A", policy=Mutating())
        with self.assertRaises(ValueError):
            await runtime.step()
        self.assertEqual(self.world.events("A"), [])

    async def test_missing_role_cards_and_unbound_callbacks_rejected(self):
        with self.assertRaises(ValueError):
            self.runtime("A", role_inputs=False)
        async def unbound(view, feedback):
            return Decision("wait")
        with self.assertRaises(ValueError):
            self.runtime("A", policy=unbound)

    async def test_changed_component_bundle_hash_rejected(self):
        design = strict_manifest()["design"]
        design["components"]["policy"]["adapter"] = "changed"
        with self.assertRaises(ValueError):
            freeze_design(design)


class ColdStartTests(unittest.IsolatedAsyncioTestCase):
    async def run_plan(self, intent):
        async def reflector(context):
            return []
        async def planner(context):
            return {"goal": "Gather evidence", "steps": [{"actor": "sre", "intent": intent,
                "text": "Request information or wait", "operation": "contain" if intent == "execute" else "",
                "source_ids": []}]}
        adapter = ReflectiveCognition(memory=MemoryCognition(), reflector=reflector, planner=planner,
                                      reflector_id="cold-reflect", planner_id="cold-plan")
        return await adapter({"actor": "sre", "memory_scope": "empty", "facts": {},
                              "observations": [], "operations": ["contain"], "cognition_state": {}})

    async def test_wait_ask_defer_decline_do_not_require_fabricated_evidence(self):
        for intent in ("wait", "ask", "defer", "decline"):
            state = await self.run_plan(intent)
            self.assertEqual(state["context"]["hypotheses"], [])
            self.assertEqual(state["context"]["plan"]["kind"], "intention")

    async def test_claim_or_execution_cannot_use_empty_sources(self):
        for intent in ("speak", "execute"):
            with self.assertRaises(ValueError):
                await self.run_plan(intent)


if __name__ == "__main__":
    unittest.main()
