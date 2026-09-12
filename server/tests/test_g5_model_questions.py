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
