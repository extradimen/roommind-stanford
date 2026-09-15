"""Scripted three-role queue integration; no semantic-quality claims."""
import unittest

from app.factorial_study import ARMS, digest, freeze_design
from app.g5.runtime import Runtime, Review
from app.g5.scheduling import QuestionScheduler
from app.g5.world import World, Decision
from test_g5_runtime import manifest


def build(world, arm, respond):
    scenario = {"roles": ["a", "b", "c"], "facts": {}, "actions": {}}
    scheduler = QuestionScheduler(priority_enabled=True)
    design = manifest(max_steps=10)["design"]
    design["scenarios"][0]["snapshot_sha256"] = digest(scenario)
    design["scheduling"] = scheduler.runtime_specification()
    design["question_annotation"] = {"adapter": "script-multi-target-v1"}
    for item in design["arms"].values():
        item["shared"]["base_scheduler_sha256"] = digest(design["scheduling"])
    frozen = freeze_design(design)

    async def policy(view, feedback):
        if not view["observations"]:
            return Decision("speak", "C then B, ready?")
        if respond and view["actor"] != "a" and not any(
                e["actor"] == view["actor"] for e in view["observations"]):
            return Decision("speak", "Later." if view["actor"] == "c" else "Decline.")
        return Decision("wait")

    class Annotator:
        specification = design["question_annotation"]
        async def __call__(self, context, decision):
            if not context["questions"]["questions"]:
                return [{"kind": "question", "start": 0, "end": len(decision.content), "targets": ["c", "b"]}]
            return [{"kind": "response", "start": 0, "end": len(decision.content),
                     "question_id": context["questions"]["questions"][0]["id"],
                     "status": "deferred" if context["actor"] == "c" else "declined"}]

    async def cognition(view):
        return {}

    async def governance(view, decision):
        return Review(True)

    return Runtime(world=world, world_id=arm, spec=scenario, manifest=frozen,
        ordinal=next(a["ordinal"] for a in frozen["assignments"] if a["arm"] == arm),
        max_steps=10, policy=policy, scheduler=scheduler, question_annotator=Annotator(),
        cognition=cognition if ARMS[arm]["cognition"] else None,
        governance=governance if ARMS[arm]["governance"] else None)


class MultiTargetRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_waiting_targets_get_one_priority_each_and_no_role_starves(self):
        for arm in ARMS:
            with self.subTest(arm=arm):
                world = World(":memory:")
                self.addCleanup(world.close)
                runtime = build(world, arm, False)
                for _ in range(10):
                    await runtime.step()
                selections = [e["payload"]["audit"]["scheduling"] for e in world.events(arm)]
                self.assertEqual([s["actor"] for s in selections if s["mode"] == "priority"], ["c", "b"])
                self.assertEqual([s["actor"] for s in selections if s["mode"] == "base"],
                                 ["a", "b", "c", "a", "b", "c", "a", "b"])
                q = (await runtime.question_journal.project())["questions"][0]
                self.assertEqual(q["pending_targets"], ["c", "b"])
                self.assertFalse(q["all_targets_responded"])
                self.assertFalse((await runtime.step())["task_completed"])

    async def test_defer_and_decline_preserved_across_runtime_reconstruction(self):
        for arm in ARMS:
            with self.subTest(arm=arm):
                world = World(":memory:")
                self.addCleanup(world.close)
                runtime = build(world, arm, True)
                for _ in range(3):
                    await runtime.step()
                before = await runtime.question_journal.project()
                runtime = build(world, arm, True)
                for _ in range(7):
                    await runtime.step()
                self.assertEqual(await runtime.question_journal.project(), before)
                q = before["questions"][0]
                self.assertEqual(q["responses"]["c"]["status"], "deferred")
                self.assertEqual(q["responses"]["b"]["status"], "declined")
                self.assertEqual(q["pending_targets"], ["c"])
                priority = [e for e in world.events(arm) if e["payload"]["audit"]["scheduling"]["mode"] == "priority"]
                self.assertEqual([e["payload"]["actor"] for e in priority], ["c"])
