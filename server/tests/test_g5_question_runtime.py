import unittest

from app.factorial_study import ARMS, freeze_design
from app.g5.runtime import Runtime, Review
from app.g5.world import World, Decision
from test_g5_runtime import manifest, spec


class Annotator:
    specification = {"adapter": "offline-questions-v1"}
    def __init__(self):
        self.calls = []
    async def __call__(self, context, decision):
        self.calls.append((context, decision))
        if decision.content == "Ready?":
            return [{"kind": "question", "start": 0, "end": 6, "targets": ["sre"]}]
        return [{"kind": "response", "start": 0, "end": len(decision.content),
                 "question_id": context["questions"]["questions"][0]["id"], "status": "deferred"}]


class QuestionRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.world = World(":memory:")
        self.addCleanup(self.world.close)

    def runtime(self, annotator, arm="A", policy=None, governance=None):
        design = manifest()["design"]
        design["question_annotation"] = {"adapter": "offline-questions-v1"}
        frozen = freeze_design(design)
        async def default_policy(view, feedback):
            self.assertNotIn("questions", view)
            return Decision("speak", "Ready?" if view["actor"] == "security" else "Later.")
        async def cognition(view):
            return {}
        async def allow(view, decision):
            return Review(True)
        return Runtime(world=self.world, world_id=arm, spec=spec(), manifest=frozen,
            ordinal=next(a["ordinal"] for a in frozen["assignments"] if a["arm"] == arm),
            max_steps=4, policy=policy or default_policy, question_annotator=annotator,
            cognition=cognition if ARMS[arm]["cognition"] else None,
            governance=(governance or allow) if ARMS[arm]["governance"] else None)

    async def test_four_arms_same_queue_and_turn_order(self):
        for arm in ARMS:
            annotator = Annotator()
            runtime = self.runtime(annotator, arm)
            await runtime.step()
            await runtime.step()
            self.assertEqual([c[0]["actor"] for c in annotator.calls], ["security", "sre"])
            self.assertNotIn("facts", annotator.calls[0][0])
            state = await runtime.question_journal.project()
            self.assertEqual(state["questions"][0]["responses"]["sre"]["status"], "deferred")
            self.assertEqual(sum(r["stage"] == "annotation" for r in self.world.attempts(arm)), 4)

    async def test_only_final_candidate_annotated(self):
        async def policy(view, feedback):
            return Decision("speak", "Ready?" if feedback else "Bad draft")
        async def review(view, decision):
            return Review(decision.content == "Ready?", "Revise")
        annotator = Annotator()
        runtime = self.runtime(annotator, "C", policy, review)
        await runtime.step()
        self.assertEqual([c[1].content for c in annotator.calls], ["Ready?"])

    async def test_failed_annotation_no_event_then_retry(self):
        annotator = Annotator()
        async def fail(context, decision):
            raise TimeoutError("offline failure")
        class Broken(Annotator):
            __call__ = staticmethod(fail)
        runtime = self.runtime(Broken())
        with self.assertRaises(TimeoutError):
            await runtime.step()
        self.assertEqual(self.world.events("A"), [])
        self.assertEqual(self.world.attempts("A")[-1]["status"], "failed")
        runtime = self.runtime(annotator)
        await runtime.step()
        self.assertEqual(len(self.world.events("A")), 1)

    async def test_missing_or_drifted_annotator_rejected(self):
        with self.assertRaises(ValueError):
            self.runtime(None)
        annotator = Annotator()
        runtime = self.runtime(annotator)
        annotator.specification = {"adapter": "changed"}
        with self.assertRaises(ValueError):
            await runtime.step()
        self.assertEqual(self.world.events("A"), [])
