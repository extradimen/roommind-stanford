"""Current adapters together; synthetic responses are not behavioral evidence."""
import unittest
import json

from app.factorial_study import ARMS, digest, freeze_design
from app.g5.model_policy import ModelBinding, Completion
from app.g5.model_session import ModelSessionAnnotator
from app.g5.runtime import Runtime
from app.g5.session_journal import SESSION_PROTOCOL
from app.g5.world import World
from test_g5_scheduled_runtime import options


def session_options(world, arm, closing=False, reopening=False):
    harness, args = options(world, arm, closing=closing)
    state = {"fail": False, "requests": []}
    async def transport(request):
        state["requests"].append(request)
        if state["fail"]:
            state["fail"] = False
            raise TimeoutError("offline session annotation failure")
        speech = json.loads(request["messages"][1]["content"])["speech"]["content"]
        annotation = ({"kind": "end_intent", "start": 0, "end": len(speech)}
                      if closing and speech == "Let's end this session." else None)
        if reopening and speech == "Let's reopen this session.":
            annotation = {"kind": "reopen", "start": 0, "end": len(speech)}
        return Completion(json.dumps({"annotation": annotation}), "offline", "fixed", "mock", digest(request), "stop")
    annotator = ModelSessionAnnotator(ModelBinding("offline", "fixed", "mock", 0.2, 512), transport)
    design = harness.frozen["design"]
    design["session_annotation"] = annotator.runtime_specification()
    for profile in design["arms"].values():
        stop = {"max_steps": 8 if reopening else 4, "max_revisions": 1, "session": SESSION_PROTOCOL}
        if reopening:
            stop["reopening"] = "explicit-request-next-scheduled-role-v1"
        profile["shared"]["stopping_policy_sha256"] = digest(stop)
    frozen = freeze_design(design)
    return harness, state, {**args, "manifest": frozen,
        "ordinal": next(a["ordinal"] for a in frozen["assignments"] if a["arm"] == arm),
        "session_annotator": annotator, "allow_reopening": reopening, "max_steps": 8 if reopening else 4}


class SessionComposedTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_reopening_four_arms_keeps_pending_history_and_next_actor(self):
        for arm in ARMS:
            world = World(":memory:")
            self.addCleanup(world.close)
            _, _, args = session_options(world, arm, closing=True, reopening=True)
            runtime = Runtime(**args)
            for _ in range(4):
                await runtime.step()
            before = world.events(arm)
            questions = await runtime.question_journal.project()
            harness, state, args = session_options(world, arm, closing=True, reopening=True)
            runtime = Runtime(**args)
            self.assertEqual((await runtime.step())["status"], "session_closed")
            self.assertEqual(harness.calls, [])
            result = await runtime.step(reopen=True)
            self.assertEqual(result["event"]["payload"]["actor"], "sre")
            self.assertEqual(result["event"]["payload"]["decision"]["content"], "Let's reopen this session.")
            self.assertEqual(world.events(arm)[:4], before)
            self.assertEqual((await runtime.session_journal.project())["episode"], 2)
            self.assertEqual((await runtime.question_journal.project())["questions"], questions["questions"])
            policies = [data for kind, data in harness.calls if kind == "policy"]
            self.assertTrue(policies[0]["role_view"]["session_reopening"]["requested"])
            self.assertEqual(len(state["requests"]), 1)
            self.assertNotIn("reopening_requested", str(world.observe(arm, "security")))
            await runtime.step()
            await runtime.step()
            self.assertEqual((await runtime.step())["status"], "session_closed")
            self.assertEqual(len(world.events(arm)), 7)

    async def test_all_current_adapters_close_with_pending_question_and_reconstruct(self):
        for arm in ARMS:
            world = World(":memory:")
            self.addCleanup(world.close)
            _, _, args = session_options(world, arm, closing=True)
            runtime = Runtime(**args)
            for _ in range(3):
                await runtime.step()
            self.assertEqual((await runtime.session_journal.project())["status"], "open")
            await runtime.step()
            before = world.events(arm)
            self.assertEqual([e["payload"]["decision"]["content"] for e in before],
                             ["Ready?"] + ["Let's end this session."] * 3)
            questions = await runtime.question_journal.project()
            self.assertEqual(questions["questions"][0]["responses"]["sre"]["status"], "unanswered")
            harness, state, args = session_options(world, arm, closing=True)
            runtime = Runtime(**args)
            stopped = await runtime.step()
            self.assertEqual(stopped["status"], "session_closed")
            self.assertIsNone(stopped["task_completed"])
            self.assertEqual(harness.calls, [])
            self.assertEqual(state["requests"], [])
            self.assertEqual(world.events(arm), before)
            self.assertEqual(await runtime.question_journal.project(), questions)

    async def test_four_arms_all_current_adapters_keep_null_distinct_from_closure(self):
        for arm, flags in ARMS.items():
            world = World(":memory:")
            self.addCleanup(world.close)
            harness, state, args = session_options(world, arm)
            runtime = Runtime(**args)
            for _ in range(4):
                await runtime.step()
            events = world.events(arm)
            self.assertEqual([e["payload"]["actor"] for e in events], ["security", "sre", "sre", "security"])
            kinds = [kind for kind, _ in harness.calls]
            self.assertEqual("reflection" in kinds, flags["cognition"])
            self.assertEqual("audit" in kinds, flags["governance"])
            self.assertEqual(len(state["requests"]), 4)
            for event, request in zip(events, state["requests"]):
                audit = event["payload"]["audit"]
                self.assertIsNone(audit["session_annotation"])
                self.assertEqual(audit["session_annotation_evidence"]["request_sha256"], digest(request))
                self.assertIn("question_annotation_evidence", audit)
            self.assertEqual((await runtime.session_journal.project())["status"], "open")
            self.assertEqual((await runtime.question_journal.project())["questions"][0]["responses"]["sre"]["status"], "deferred")
            count = len(harness.calls)
            self.assertEqual((await runtime.step())["status"], "cutoff")
            self.assertEqual(len(harness.calls), count)
            self.assertNotIn("session_annotation_evidence", str(world.observe(arm, "sre")))

    async def test_session_failure_then_rebuild_preserves_priority_and_reference_events(self):
        world, reference = World(":memory:"), World(":memory:")
        self.addCleanup(world.close)
        self.addCleanup(reference.close)
        _, state, args = session_options(world, "D")
        runtime = Runtime(**args)
        await runtime.step()
        state["fail"] = True
        with self.assertRaises(TimeoutError):
            await runtime.step()
        self.assertEqual(len(world.events("D")), 1)
        failed = world.attempts("D")[-1]
        self.assertEqual((failed["stage"], failed["status"]), ("session_annotation", "failed"))
        _, _, args = session_options(world, "D")
        runtime = Runtime(**args)
        for _ in range(3):
            await runtime.step()
        _, _, args = session_options(reference, "D")
        uninterrupted = Runtime(**args)
        for _ in range(4):
            await uninterrupted.step()
        self.assertEqual(world.events("D"), reference.events("D"))
        self.assertEqual(await runtime.session_journal.project(), await uninterrupted.session_journal.project())
        self.assertEqual(await runtime.question_journal.project(), await uninterrupted.question_journal.project())
        self.assertIn(failed, world.attempts("D"))
