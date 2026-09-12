import json
import unittest
from dataclasses import replace

from app.factorial_study import digest
from app.g5.model_policy import ModelBinding, Completion
from app.g5.model_auditor import ModelAuditor
from app.g5.governance import CandidateGovernance
from app.g5.world import Decision
from test_g5_governance import finding, view


class AuditorTests(unittest.IsolatedAsyncioTestCase):
    binding = ModelBinding("ollama", "fixed", "offline", 0.2, 512)

    def build(self, body, transform=lambda r: r):
        calls = []
        async def transport(request):
            calls.append(request)
            return transform(Completion(body, "ollama", "fixed", "offline", digest(request), "stop"))
        auditor = ModelAuditor(self.binding, transport)
        return CandidateGovernance(auditor, auditor_id="model-v1"), calls

    async def test_findings_evidence_and_input_filter(self):
        adapter, calls = self.build(json.dumps({"findings": [finding()]}))
        result = await adapter(view(), Decision("speak", "All contained"))
        self.assertFalse(result.allowed)
        self.assertNotIn("never-send", json.dumps(calls))
        evidence = json.loads(result.model_evidence_json)
        self.assertEqual(evidence["request_sha256"], digest(calls[0]))
        self.assertIn("auditor", adapter.specification)

    async def test_empty_findings_allow_without_rewrite(self):
        adapter, _ = self.build('{"findings":[]}')
        result = await adapter(view(), Decision("speak", "I decline."))
        self.assertTrue(result.allowed)
        self.assertEqual(result.reason, "")
        self.assertNotEqual(result.model_evidence_json, "null")

    async def test_bad_receipt_and_json_fail(self):
        for transform in (lambda r: replace(r, model="other"), lambda r: replace(r, finish_reason="length"),
                          lambda r: replace(r, request_sha256="wrong")):
            adapter, _ = self.build('{"findings":[]}', transform)
            with self.assertRaises(ValueError):
                await adapter(view(), Decision("speak", "abc"))
        for body in ('', '[]', '{"findings":[],"findings":[]}', '{"findings":[],"replacement":"yes"}'):
            adapter, _ = self.build(body)
            with self.assertRaises(ValueError):
                await adapter(view(), Decision("speak", "abc"))

    async def test_forged_source_fails_composition(self):
        adapter, _ = self.build(json.dumps({"findings": [finding(source_ids=["hidden"])]}))
        with self.assertRaises(ValueError):
            await adapter(view(), Decision("speak", "All contained"))

    async def test_drift_prevents_call_and_wait_skips_model(self):
        adapter, calls = self.build('{"findings":[]}')
        self.assertTrue((await adapter(view(), Decision("wait"))).allowed)
        self.assertEqual(calls, [])
        adapter.auditor.binding = replace(self.binding, model="other")
        with self.assertRaises(ValueError):
            await adapter(view(), Decision("speak", "abc"))
        self.assertEqual(calls, [])
