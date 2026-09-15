import unittest

from app.factorial_study import ARMS, digest, freeze_design
from app.g5.runtime import Runtime
from app.g5.scheduling import QuestionScheduler
from app.g5.world import World
from test_g5_composed_runtime import Harness


def options(world, arm, enabled=True, closing=False):
    harness = Harness(closing=closing)
    scheduler = QuestionScheduler(priority_enabled=enabled)
    design = harness.frozen["design"]
    design["scheduling"] = scheduler.runtime_specification()
    for entry in design["arms"].values():
        entry["shared"]["base_scheduler_sha256"] = digest(design["scheduling"])
    harness.frozen = freeze_design(design)
    return harness, {**harness.runtime_options(world, arm), "scheduler": scheduler}


class ScheduledRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_four_arms_same_priority_policy_and_default_off_order(self):
        for enabled in (False, True):
            for arm in ARMS:
                with self.subTest(enabled=enabled, arm=arm):
                    world = World(":memory:")
                    self.addCleanup(world.close)
                    _, args = options(world, arm, enabled)
                    runtime = Runtime(**args)
                    for _ in range(4):
                        await runtime.step()
                    events = world.events(arm)
                    self.assertEqual([e["payload"]["actor"] for e in events],
                                     ["security", "sre", "sre", "security"] if enabled else ["security", "sre"] * 2)
                    self.assertEqual(events[1]["payload"]["audit"]["scheduling"]["mode"],
                                     "priority" if enabled else "base")
                    self.assertNotIn("scheduling", str(world.observe(arm, "sre")[1]))

    async def test_failure_does_not_consume_priority_and_reconstruction_resumes(self):
        world = World(":memory:")
        self.addCleanup(world.close)
        harness, args = options(world, "D")
        runtime = Runtime(**args)
        await runtime.step()
        harness.fail_annotation = True
        with self.assertRaises(TimeoutError):
            await runtime.step()
        self.assertEqual(len(world.events("D")), 1)
        _, args = options(world, "D")
        runtime = Runtime(**args)
        result = await runtime.step()
        self.assertEqual(result["event"]["payload"]["audit"]["scheduling"]["mode"], "priority")
        self.assertEqual((await runtime.step())["event"]["payload"]["actor"], "sre")

    async def test_missing_drift_and_unbound_scheduler_rejected(self):
        world = World(":memory:")
        self.addCleanup(world.close)
        _, args = options(world, "D")
        with self.assertRaises(ValueError):
            Runtime(**{**args, "scheduler": None})
        runtime = Runtime(**args)
        args["scheduler"].limit = 2
        with self.assertRaises(ValueError):
            await runtime.step()
        self.assertEqual(world.events("D"), [])
        with self.assertRaises(ValueError):
            Runtime(**{**Harness().runtime_options(world, "A"), "scheduler": QuestionScheduler()})

    def test_scheduler_hash_mismatch_rejected(self):
        design = Harness().frozen["design"]
        design["scheduling"] = QuestionScheduler().runtime_specification()
        with self.assertRaises(ValueError):
            freeze_design(design)
