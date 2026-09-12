"""Archived configuration assembly against the existing scripted reference."""
import copy
from pathlib import Path
import unittest

import httpx

import test_g5_local_batch as batch_tests
from test_g5_cognition_storage import storage_options
from app.g5.assembly import ExplicitRouteAssembler, OfflineAssembler
from app.g5.capacity import BudgetTransport, RequestBudget
from app.g5.model_policy import ModelBinding, ModelPolicy
from app.g5.model_questions import ModelQuestionAnnotator
from app.g5.ollama_transport import OllamaTransport
from app.g5.world import World


def assembler(world):
    # Only transport delegates cross this boundary: no reference components are
    # returned by the assembler. Each resolver makes a fresh scripted stack.
    def delegates():
        options = storage_options(world, "D")[2]
        found = {}
        def walk(adapter):
            if adapter is None: return
            for name in ("memory", "semantic_scorer", "reflector", "planner", "auditor"):
                walk(getattr(adapter, name, None))
            transport = getattr(adapter, "transport", None)
            if transport is not None: found[transport.delegate_id] = transport.delegate
        for name in ("policy", "cognition", "governance", "question_annotator", "session_annotator"):
            walk(options[name])
        return found
    return OfflineAssembler({key: lambda key=key: delegates()[key] for key in delegates()})


def inputs(options):
    return {options["manifest"]["assignments"][0]["scenario_id"]: {
        key: copy.deepcopy(options[key]) for key in ("spec", "role_inputs", "max_steps", "allow_reopening", "reliable_reopening")}}


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.world = World(":memory:"); self.addCleanup(self.world.close)
        self.options = storage_options(self.world, "D")[2]
        self.assembler = assembler(self.world)

    def test_roundtrip_all_arms_and_fresh_instances(self):
        factory = self.assembler.factory(world=self.world, manifest=self.options["manifest"], runtime_inputs=inputs(self.options))
        for assignment in self.options["manifest"]["assignments"]:
            one, two = factory(assignment), factory(assignment)
            self.assertIsNot(one["policy"], two["policy"])
            self.assertEqual(one["policy"].runtime_specification(), self.options["policy"].runtime_specification())
            self.assertEqual(one["cognition"] is not None, assignment["arm"] in ("B", "D"))
            self.assertEqual(one["governance"] is not None, assignment["arm"] in ("C", "D"))
        world_ids = {factory(assignment)["world_id"]
                     for assignment in self.options["manifest"]["assignments"]}
        self.assertEqual(len(world_ids), len(self.options["manifest"]["assignments"]))

    def test_unknown_fields_prompt_protocol_and_transport_drift_rejected(self):
        original = self.options["manifest"]["design"]["components"]["policy"]
        for change in (lambda s: s.update(extra=True), lambda s: s.update(system_prompt_sha256="wrong"),
                       lambda s: s["binding"].update(provider="ollama"),
                       lambda s: s["transport"].update(delegate_id="unregistered"),
                       lambda s: s["transport"].update(delegate_spec={"wrong": True}),
                       lambda s: s["transport"]["budget"].update(overflow="truncate")):
            value = copy.deepcopy(original); change(value)
            with self.assertRaises(ValueError): self.assembler.component(value)
        with self.assertRaises(ValueError): self.assembler.component({"adapter": "arbitrary.module"})

    def test_question_repair_limit_roundtrips_from_frozen_specification(self):
        original = self.options["manifest"]["design"]["question_annotation"]
        value = copy.deepcopy(original)
        value["question_repair"] = {
            "schema": "g5-question-validation-feedback-v1", "max_revisions": 2}
        rebuilt = self.assembler.component(value)
        self.assertIsInstance(rebuilt, ModelQuestionAnnotator)
        self.assertEqual(rebuilt.max_revisions, 2)
        self.assertEqual(rebuilt.runtime_specification(), value)

    def test_changed_runtime_inputs_rejected_without_creating_world(self):
        values = inputs(self.options)
        next(iter(values.values()))["max_steps"] += 1
        factory = self.assembler.factory(world=self.world, manifest=self.options["manifest"], runtime_inputs=values)
        with self.assertRaises(ValueError): factory(self.options["manifest"]["assignments"][0])
        self.assertEqual(self.world.db.execute("SELECT COUNT(*) FROM g5_worlds").fetchone()[0], 0)

    def test_explicit_route_assembler_reconstructs_without_network_or_credentials(self):
        calls = []
        binding = ModelBinding("ollama", "gpt-oss:120b", "validation-route", 0.2, 512)
        def handler(request):
            calls.append(request)
            return httpx.Response(500)
        route = OllamaTransport(binding, "https://provider.invalid", api_key="test-secret",
                                http_transport=httpx.MockTransport(handler))
        specification = ModelPolicy(binding, route).runtime_specification()
        built = ExplicitRouteAssembler({}, {"validation-route": lambda: route}).component(specification)
        self.assertEqual(built.runtime_specification(), specification)
        self.assertEqual(calls, [])
        self.assertNotIn("test-secret", str(specification))

        budgeted = BudgetTransport(route, RequestBudget(100_000, 100_000),
                                   delegate_id="validation-route")
        budgeted_spec = ModelPolicy(binding, budgeted).runtime_specification()
        rebuilt = ExplicitRouteAssembler(
            {"validation-route": lambda: route},
            {"validation-route": lambda: route}).component(budgeted_spec)
        self.assertEqual(rebuilt.runtime_specification(), budgeted_spec)
        self.assertEqual(calls, [])

    def test_offline_and_explicit_route_boundaries_reject_substitution(self):
        binding = ModelBinding("ollama", "gpt-oss:120b", "validation-route", 0.2, 512)
        route = OllamaTransport(binding, "https://provider.invalid",
                                http_transport=httpx.MockTransport(lambda r: httpx.Response(500)))
        specification = ModelPolicy(binding, route).runtime_specification()
        with self.assertRaises(ValueError):
            OfflineAssembler({}).component(specification)
        with self.assertRaises(ValueError):
            ExplicitRouteAssembler({}, {}).component(specification)
        other = OllamaTransport(binding, "https://other.invalid",
                                http_transport=httpx.MockTransport(lambda r: httpx.Response(500)))
        with self.assertRaises(ValueError):
            ExplicitRouteAssembler({}, {"validation-route": lambda: other}).component(specification)


class BatchAssemblyTests(unittest.IsolatedAsyncioTestCase):
    async def test_archived_factory_resume_and_sealed_reuse(self):
        fixture = batch_tests.BatchTests()
        await fixture.asyncSetUp()
        try:
            options = storage_options(fixture.world, "D")[2]
            factory = assembler(fixture.world).factory(world=fixture.world, manifest=fixture.contract["manifest"], runtime_inputs=inputs(options))
            batch = fixture.batch(factory=factory)
            stream = batch.run()
            try:
                for _ in range(3): await anext(stream)
            finally:
                await stream.aclose(); batch.close()
            batch = fixture.batch(factory=factory)
            try:
                rows = [row async for row in batch.run()]
                self.assertEqual(sum(r["status"] == "sealed" for r in rows), 4)
                packet = await batch.evaluation_inputs()
                self.assertEqual([len(s["events"]) for s in packet["sources"]], [7] * 4)
                self.assertEqual(len([r async for r in batch.run()]), 4)
                self.assertEqual(await batch.evaluation_inputs(), packet)
            finally: batch.close()
            reference = World(str(Path(fixture.directory.name) / "reference.sqlite"))
            old_control = fixture.control
            fixture.control = str(Path(fixture.directory.name) / "reference-control.sqlite")
            batch = fixture.batch(world=reference, factory=batch_tests.factory(reference, fixture.contract, []))
            try:
                _ = [row async for row in batch.run()]
                expected = await batch.evaluation_inputs()
                self.assertEqual([s["events"] for s in packet["sources"]], [s["events"] for s in expected["sources"]])
            finally:
                batch.close(); reference.close(); fixture.control = old_control
        finally: fixture.doCleanups()


if __name__ == "__main__": unittest.main()
