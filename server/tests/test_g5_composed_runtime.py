"""Offline composed-adapter acceptance; scripted responses are not quality evidence."""
import json
import tempfile
import unittest
from pathlib import Path

from app.factorial_study import ARMS, digest, freeze_design
from app.g5.components import specification
from app.g5.governance import CandidateGovernance
from app.g5.memory import MemoryCognition
from app.g5.model_auditor import ModelAuditor
from app.g5.model_cognition import ModelCognitionGenerator
from app.g5.model_policy import Completion, ModelBinding, ModelPolicy
from app.g5.model_questions import ModelQuestionAnnotator
from app.g5.reflection import ReflectiveCognition
from app.g5.runtime import Runtime
from app.g5.semantic import EmbeddingBinding, EmbeddingCompletion, EmbeddingScorer
from app.g5.world import World
from test_g5_inputs_attempts import cards
from test_g5_runtime import manifest, spec


class Harness:
    def __init__(self, revision_mode=None, closing=False):
        self.calls = []
        self.fail_annotation = False
        self.fail_revision = revision_mode == "fail_once"
        binding = ModelBinding("offline", "fixed", "mock", 0.2, 512)
        embedding = EmbeddingBinding("offline", "vector", "mock-vector", 2)

        async def vectors(request):
            self.calls.append(("embedding", request))
            return EmbeddingCompletion(embedding, digest(request), [[1., 1.] for _ in request["input"]])

        def transport(kind):
            async def complete(request):
                data = json.loads(request["messages"][1]["content"])
                self.calls.append((kind, data))
                if kind == "policy":
                    view = data["role_view"]
                    content = "Ready?" if not view["observations"] else "Later."
                    if closing and view["observations"]:
                        content = "Let's end this session."
                    if closing and view.get("session_reopening"):
                        content = "Let's reopen this session."
                    if revision_mode and not view["observations"]:
                        if data["revision_feedback"] and self.fail_revision:
                            self.fail_revision = False
                            raise TimeoutError("injected offline revision outage")
                        if not data["revision_feedback"] or revision_mode == "exhaust":
                            content = "Bad draft"
                    body = {"action": "speak", "content": content, "operation": ""}
                elif kind in ("reflection", "planning"):
                    ids = [n["id"] for n in data["memory"]["retrieved"]][:1]
                    body = ({"hypotheses": [{"text": "Clarification may help", "source_ids": ids}]}
                            if kind == "reflection" else {"goal": "Clarify", "steps": [{
                                "actor": data["actor"], "intent": "ask", "text": "Ask for context",
                                "operation": "", "source_ids": ids}]})
                elif kind == "audit":
                    body = {"findings": []}
                    if data["candidate"]["content"] == "Bad draft":
                        body["findings"] = [{"code": "unsupported_fact", "severity": "hard",
                            "certainty": "supported", "start": 0, "end": 9,
                            "source_ids": ["fact:contained"], "reason": "Clarify instead of asserting completion"}]
                else:
                    if self.fail_annotation:
                        self.fail_annotation = False
                        raise TimeoutError("injected offline annotation outage")
                    context = data["context"]
                    annotations = []
                    if not context["observations"]:
                        annotations = [{"kind": "question", "start": 0, "end": 6, "targets": ["sre"]}]
                    elif context["actor"] == "sre" and not closing:
                        annotations = [{"kind": "response", "start": 0, "end": 6,
                            "question_id": context["questions"]["questions"][0]["id"], "status": "deferred"}]
                    body = {"annotations": annotations}
                return Completion(json.dumps(body), binding.provider, binding.model,
                                  binding.endpoint_id, digest(request), "stop")
            return complete

        self.policy = ModelPolicy(binding, transport("policy"))
        self.cognition = ReflectiveCognition(
            memory=MemoryCognition(semantic_scorer=EmbeddingScorer(embedding, vectors), semantic_id="offline"),
            reflector=ModelCognitionGenerator("reflection", binding, transport("reflection")),
            planner=ModelCognitionGenerator("planning", binding, transport("planning")),
            reflector_id="fixed-reflect", planner_id="fixed-plan")
        self.governance = CandidateGovernance(ModelAuditor(binding, transport("audit")), auditor_id="fixed")
        self.annotator = ModelQuestionAnnotator(binding, transport("annotation"))
        design = manifest()["design"]
        design["components"] = {name: specification(getattr(self, name))
                                for name in ("policy", "cognition", "governance")}
        design["question_annotation"] = specification(self.annotator)
        for arm in design["arms"].values():
            arm["shared"]["model_bindings_sha256"] = digest(design["components"])
            arm["shared"]["role_inputs_sha256"] = digest(cards())
        self.frozen = freeze_design(design)

    def runtime_options(self, world, arm):
        return dict(world=world, world_id=arm, spec=spec(), manifest=self.frozen,
            ordinal=next(a["ordinal"] for a in self.frozen["assignments"] if a["arm"] == arm),
            policy=self.policy, cognition=self.cognition if ARMS[arm]["cognition"] else None,
            governance=self.governance if ARMS[arm]["governance"] else None,
            question_annotator=self.annotator, role_inputs=cards(), max_steps=4)

    def runtime(self, world, arm):
        return Runtime(**self.runtime_options(world, arm))


class ComposedRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejected_draft_revised_by_same_role_only_final_is_annotated(self):
        for arm in ("C", "D"):
            with self.subTest(arm=arm):
                harness = Harness("revise")
                world = World(":memory:")
                self.addCleanup(world.close)
                runtime = harness.runtime(world, arm)
                result = await runtime.step()
                payload = result["event"]["payload"]
                self.assertEqual(payload["decision"]["content"], "Ready?")
                attempts = payload["audit"]["attempts"]
                self.assertEqual([a["review"]["allowed"] for a in attempts], [False, True])
                policies = [data for kind, data in harness.calls if kind == "policy"]
                self.assertEqual([p["role_view"]["actor"] for p in policies], ["security"] * 2)
                self.assertEqual(policies[0]["role_view"], policies[1]["role_view"])
                self.assertTrue(policies[1]["revision_feedback"])
                annotated = [data["speech"]["content"] for kind, data in harness.calls if kind == "annotation"]
                self.assertEqual(annotated, ["Ready?"])
                self.assertNotIn("Bad draft", json.dumps(world.observe(arm, "sre")[1]))
                self.assertEqual(len((await runtime.question_journal.project())["questions"]), 1)

    async def test_revision_exhaustion_is_silent_unresolved_not_question_or_success(self):
        harness = Harness("exhaust")
        world = World(":memory:")
        self.addCleanup(world.close)
        runtime = harness.runtime(world, "D")
        result = await runtime.step()
        payload = result["event"]["payload"]
        self.assertEqual(payload["decision"], {"action": "wait", "content": "", "operation": ""})
        self.assertEqual(payload["audit"]["outcome"], "unresolved_after_revisions")
        self.assertEqual(len(payload["audit"]["attempts"]), 2)
        self.assertNotIn("annotation", [kind for kind, _ in harness.calls])
        self.assertEqual((await runtime.question_journal.project())["questions"], [])
        self.assertEqual(world.observe("D", "sre")[1]["observations"], [])
        self.assertFalse(world.facts("D")["contained"]["value"])

    async def test_revision_transport_failure_no_commit_then_same_result_as_reference(self):
        harness = Harness("fail_once")
        world = World(":memory:")
        self.addCleanup(world.close)
        runtime = harness.runtime(world, "D")
        with self.assertRaises(TimeoutError):
            await runtime.step()
        self.assertEqual(world.events("D"), [])
        self.assertEqual(world.attempts("D")[-1]["stage"], "policy")
        self.assertEqual(world.attempts("D")[-1]["status"], "failed")
        self.assertNotIn("annotation", [kind for kind, _ in harness.calls])
        await runtime.step()
        reference = World(":memory:")
        self.addCleanup(reference.close)
        await Harness("revise").runtime(reference, "D").step()
        self.assertEqual(world.events("D"), reference.events("D"))
        self.assertGreater(len(world.attempts("D")), len(reference.attempts("D")))

    async def test_four_arms_composed_trace_isolation_and_cutoff(self):
        for arm, flags in ARMS.items():
            with self.subTest(arm=arm):
                harness = Harness()
                world = World(":memory:")
                self.addCleanup(world.close)
                runtime = harness.runtime(world, arm)
                for _ in range(4):
                    await runtime.step()
                before = len(harness.calls)
                self.assertEqual((await runtime.step())["status"], "cutoff")
                self.assertEqual(len(harness.calls), before)
                kinds = [kind for kind, _ in harness.calls]
                for kind in ("embedding", "reflection", "planning"):
                    self.assertEqual(kind in kinds, flags["cognition"])
                self.assertEqual("audit" in kinds, flags["governance"])
                events = world.events(arm)
                self.assertEqual([e["payload"]["actor"] for e in events], ["security", "sre"] * 2)
                for kind, data in harness.calls:
                    if kind == "policy":
                        view = data["role_view"]
                        self.assertEqual("cognition" in view, flags["cognition"])
                        other = "sre" if view["actor"] == "security" else "security"
                        self.assertNotIn(other + "-only-goal", json.dumps(data))
                        self.assertNotIn("questions", view)
                    if kind == "annotation":
                        self.assertNotIn("protected-source", json.dumps(data))
                public = world.observe(arm, "sre")[1]
                self.assertNotIn("model_evidence", json.dumps(public))
                self.assertNotIn("protected-source", json.dumps(public))
                self.assertFalse(public["facts"]["contained"]["value"])
                queue = await runtime.question_journal.project()
                self.assertEqual(queue["questions"][0]["responses"]["sre"]["status"], "deferred")

    async def test_failed_final_annotation_then_reopen_matches_uninterrupted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "world.sqlite")
            harness = Harness()
            world = World(path)
            runtime = harness.runtime(world, "D")
            await runtime.step()
            original = world.events("D")
            harness.fail_annotation = True
            with self.assertRaises(TimeoutError):
                await runtime.step()
            self.assertEqual(world.events("D"), original)
            self.assertEqual(world.attempts("D")[-1]["status"], "failed")
            world.close()
            world = World(path)
            self.addCleanup(world.close)
            resumed = Harness().runtime(world, "D")
            for _ in range(3):
                await resumed.step()
            reference = World(":memory:")
            self.addCleanup(reference.close)
            uninterrupted = Harness().runtime(reference, "D")
            for _ in range(4):
                await uninterrupted.step()
            self.assertEqual(world.events("D"), reference.events("D"))
            self.assertEqual(await resumed.question_journal.project(), await uninterrupted.question_journal.project())
            self.assertGreater(len(world.attempts("D")), len(reference.attempts("D")))
