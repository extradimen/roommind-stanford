import json
import unittest
from dataclasses import replace

from app.factorial_study import digest
from app.g5.model_policy import Completion, ModelBinding, ModelPolicy


def view():
    return {"actor": "sre", "participants": ["sre"], "own_role": {"private": {"goals": ["diagnose"]}},
            "public_roster": {"sre": {}}, "facts": {}, "observations": [], "operations": ["contain"],
            "cognition_state": {"unselected_memory": "not-for-policy"},
            "world_audit": {"another_role_secret": "never-send"}}


class PolicyTests(unittest.IsolatedAsyncioTestCase):
    binding = ModelBinding("test-provider", "fixed-model", "local-test-route", 0.2, 4096)

    def policy(self, body, transform=lambda response: response, capture=None):
        async def transport(request):
            if capture is not None:
                capture.append(request)
            return transform(Completion(body, self.binding.provider, self.binding.model,
                                        self.binding.endpoint_id, digest(request), "stop"))
        return ModelPolicy(self.binding, transport)

    async def test_fixed_binding_filtered_view_and_evidence(self):
        requests = []
        policy = self.policy('{"action":"speak","content":"I am uncertain.","operation":""}', capture=requests)
        decision = await policy(view(), ())
        self.assertEqual(decision.content, "I am uncertain.")
        self.assertNotIn("never-send", json.dumps(requests))
        self.assertNotIn("not-for-policy", json.dumps(requests))
        self.assertEqual(json.loads(decision.model_evidence_json)["request_sha256"], digest(requests[0]))

    async def test_binding_drift_and_wrong_request_fail(self):
        for transform in (lambda r: replace(r, model="other-model"),
                          lambda r: replace(r, provider="other-provider"),
                          lambda r: replace(r, endpoint_id="other-route"),
                          lambda r: replace(r, request_sha256="wrong"),
                          lambda r: replace(r, finish_reason="length")):
            with self.assertRaises(ValueError):
                await self.policy('{"action":"wait","content":"","operation":""}', transform)(view(), ())

    async def test_malformed_or_forged_decisions_do_not_become_fallback_speech(self):
        for body in ('', '[]', '```json\n{}\n```', '{"action":"wait","action":"speak"}',
                     '{"action":"wait","content":"hidden speech","operation":""}',
                     '{"action":"execute","content":"","operation":"not-registered"}',
                     '{"action":"wait","content":"","operation":"","model":"forged"}'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                await self.policy(body)(view(), ())

    async def test_revision_feedback_changes_bound_request(self):
        requests = []
        policy = self.policy('{"action":"wait","content":"","operation":""}', capture=requests)
        await policy(view(), ())
        await policy(view(), ("Use the available evidence.",))
        self.assertNotEqual(digest(requests[0]), digest(requests[1]))

    async def test_no_role_card_means_no_model_call(self):
        requests = []
        with self.assertRaises(ValueError):
            await self.policy('{}', capture=requests)({"actor": "sre"}, ())
        self.assertEqual(requests, [])

    async def test_transport_failure_is_not_replaced_with_success(self):
        async def unavailable(request):
            raise TimeoutError("simulated provider failure")
        with self.assertRaises(TimeoutError):
            await ModelPolicy(self.binding, unavailable)(view(), ())

    async def test_structured_failure_is_repaired_and_rejected_body_retained(self):
        bodies = iter([
            '{"action":"execute","content":"","operation":"invented"}',
            '{"action":"execute","content":"","operation":"contain"}',
        ])
        requests = []
        async def transport(request):
            requests.append(request)
            return Completion(next(bodies), self.binding.provider, self.binding.model,
                              self.binding.endpoint_id, digest(request), "stop")
        result = await ModelPolicy(self.binding, transport, max_revisions=2)(view(), ())
        repair = json.loads(requests[1]["messages"][1]["content"])["structured_validation_feedback"]
        self.assertEqual(repair["error"]["error_code"], "authority")
        evidence = json.loads(result.model_evidence_json)
        self.assertEqual(evidence["rejected"][0]["response_content"],
                         '{"action":"execute","content":"","operation":"invented"}')

    async def test_model_adapter_runs_through_journal_and_world_commit(self):
        from app.factorial_study import freeze_design
        from app.g5.runtime import Runtime
        from app.g5.world import World
        from test_g5_runtime import spec, manifest
        from test_g5_inputs_attempts import cards
        world = World(":memory:")
        self.addCleanup(world.close)
        inputs = cards()
        design = manifest()["design"]
        for arm in design["arms"].values():
            arm["shared"]["role_inputs_sha256"] = digest(inputs)
        frozen = freeze_design(design)
        ordinal = next(r["ordinal"] for r in frozen["assignments"] if r["arm"] == "A")
        policy = self.policy('{"action":"speak","content":"Evidence is uncertain.","operation":""}')
        runtime = Runtime(world=world, world_id="model-test", spec=spec(), manifest=frozen,
                          ordinal=ordinal, policy=policy, max_steps=4, role_inputs=inputs)
        result = await runtime.step()
        evidence = json.loads(result["event"]["payload"]["decision"]["model_evidence_json"])
        self.assertEqual(evidence["binding"]["model"], "fixed-model")
        observed = world.observe("model-test", "sre")[1]
        self.assertEqual(observed["observations"][0]["content"], "Evidence is uncertain.")
        self.assertNotIn("model_evidence_json", str(observed))
        self.assertEqual([r["status"] for r in world.attempts("model-test")],
                         ["started", "succeeded", "started", "succeeded"])


if __name__ == "__main__":
    unittest.main()
