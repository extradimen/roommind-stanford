import unittest
from dataclasses import replace

from app.factorial_study import digest
from app.g5.model_policy import ModelBinding, Completion
from app.g5.model_questions import ModelQuestionAnnotator
from app.g5.world import Decision


class ModelQuestionTests(unittest.IsolatedAsyncioTestCase):
    binding = ModelBinding("ollama", "fixed", "offline", 0.2, 512)

    def adapter(self, body, transform=lambda r: r):
        self.calls = []
        async def transport(request):
            self.calls.append(request)
            return transform(Completion(body, "ollama", "fixed", "offline", digest(request), "stop"))
        return ModelQuestionAnnotator(self.binding, transport)

    def context(self):
        return {"actor": "a", "participants": ["a", "b"], "observations": [],
                "questions": {"questions": []}, "private_secret": "never-send"}

    async def test_input_filter_and_empty_result_receipt(self):
        output = await self.adapter('{"annotations":[]}')(self.context(), Decision("speak", "Hello"))
        self.assertEqual(output, [])
        self.assertNotIn("never-send", str(self.calls))
        self.assertEqual(output.model_evidence["request_sha256"], digest(self.calls[0]))

    async def test_bad_binding_truncation_and_json(self):
        for transform in (lambda r: replace(r, model="other"), lambda r: replace(r, finish_reason="length")):
            with self.assertRaises(ValueError):
                await self.adapter('{"annotations":[]}', transform)(self.context(), Decision("speak", "Hello"))
        for body in ('', '[]', '{"annotations":[],"annotations":[]}', '{"annotations":[],"rewrite":"x"}'):
            with self.assertRaises(ValueError):
                await self.adapter(body)(self.context(), Decision("speak", "Hello"))

    async def test_missing_context_and_non_speech_never_call(self):
        adapter = self.adapter('{"annotations":[]}')
        with self.assertRaises(ValueError):
            await adapter({}, Decision("speak", "Hello"))
        with self.assertRaises(ValueError):
            await adapter(self.context(), Decision("wait"))
        self.assertEqual(self.calls, [])

    async def test_invalid_targets_receive_bounded_feedback_and_retain_hashes(self):
        bodies = iter([
            '{"annotations":[{"kind":"question","start":0,"end":6,"targets":["a"]}]}',
            '{"annotations":[{"kind":"question","start":0,"end":6,"targets":["b"]}]}',
        ])
        calls = []
        async def transport(request):
            calls.append(request)
            return Completion(next(bodies), "ollama", "fixed", "offline", digest(request), "stop")
        adapter = ModelQuestionAnnotator(self.binding, transport, max_revisions=2)
        output = await adapter(self.context(), Decision("speak", "Ready?"))
        self.assertEqual(output[0]["targets"], ["b"])
        self.assertEqual(len(calls), 2)
        feedback = __import__("json").loads(calls[1]["messages"][1]["content"])["context"]["validation_feedback"]
        self.assertEqual(feedback["error"]["message"], "Invalid question targets")
        self.assertEqual(feedback["error"]["error_code"], "reference")
        self.assertEqual(feedback["allowed_values"]["participants"], ["a", "b"])
        self.assertEqual(feedback["allowed_values"]["question_target_ids"], ["b"])
        self.assertEqual(len(output.model_evidence["rejected"]), 1)
        self.assertEqual(output.model_evidence["rejected"][0]["response_sha256"],
                         digest('{"annotations":[{"kind":"question","start":0,"end":6,"targets":["a"]}]}'))

    async def test_question_repair_is_bounded_and_hash_bound(self):
        adapter = self.adapter(
            '{"annotations":[{"kind":"question","start":0,"end":6,"targets":[]}]}')
        adapter.max_revisions = 2
        with self.assertRaisesRegex(ValueError, "Invalid question targets"):
            await adapter(self.context(), Decision("speak", "Ready?"))
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(adapter.runtime_specification()["question_repair"], {
            "schema": "g5-question-validation-feedback-v1", "max_revisions": 2})

    async def test_response_must_belong_to_pending_target(self):
        context = self.context()
        context["questions"] = {"questions": [{
            "id": "q1", "responses": {"b": {"status": "unanswered"}}}]}
        body = ('{"annotations":[{"kind":"response","start":0,"end":6,'
                '"question_id":"q1","status":"answered"}]}')
        with self.assertRaisesRegex(ValueError, "pending target"):
            await self.adapter(body)(context, Decision("speak", "Answer"))
