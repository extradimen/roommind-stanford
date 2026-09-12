import unittest
from dataclasses import replace

from app.factorial_study import digest
from app.g5.model_policy import ModelBinding, Completion
from app.g5.model_session import ModelSessionAnnotator
from app.g5.world import Decision


class ModelSessionTests(unittest.IsolatedAsyncioTestCase):
    def adapter(self, body, transform=lambda r: r):
        self.calls = []
        async def transport(request):
            self.calls.append(request)
            return transform(Completion(body, "ollama", "fixed", "offline", digest(request), "stop"))
        return ModelSessionAnnotator(ModelBinding("ollama", "fixed", "offline", 0.2, 512), transport)

    def context(self):
        return {"actor": "a", "participants": ["a", "b"], "observations": [],
                "session": {"status": "open"}, "private_secret": "never-send"}

    async def test_null_and_span_keep_receipt_and_filter_input(self):
        for body in ('{"annotation":null}', '{"annotation":{"kind":"end_intent","start":0,"end":4}}'):
            output = await self.adapter(body)(self.context(), Decision("speak", "End."))
            self.assertNotIn("never-send", str(self.calls))
            self.assertEqual(output.model_evidence["request_sha256"], digest(self.calls[0]))
            self.assertEqual(output.model_evidence["response_sha256"], digest(body))

    async def test_bad_receipts_envelopes_and_spans(self):
        for transform in (lambda r: replace(r, model="other"), lambda r: replace(r, finish_reason="length"),
                          lambda r: replace(r, request_sha256="wrong")):
            with self.assertRaises(ValueError):
                await self.adapter('{"annotation":null}', transform)(self.context(), Decision("speak", "End."))
        for body in ('', '[]', '{"annotation":null,"annotation":null}', '{"annotation":null,"rewrite":"x"}',
                     '{"annotation":{"kind":"end_intent","start":0,"end":99}}',
                     '{"annotation":{"kind":"end_intent","start":false,"end":4}}'):
            with self.assertRaises(ValueError):
                await self.adapter(body)(self.context(), Decision("speak", "End."))

    async def test_invalid_input_never_calls_transport(self):
        adapter = self.adapter('{"annotation":null}')
        for context, decision in (({}, Decision("speak", "End.")), (self.context(), Decision("wait"))):
            with self.assertRaises(ValueError):
                await adapter(context, decision)
        self.assertEqual(self.calls, [])
