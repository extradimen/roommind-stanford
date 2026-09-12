import json
import unittest
from dataclasses import asdict

import httpx

from app.g5.model_policy import ModelBinding, ModelPolicy
from app.g5.ollama_transport import OllamaTransport
from test_g5_model_policy import view


class HTTPTests(unittest.IsolatedAsyncioTestCase):
    binding = ModelBinding("ollama", "gpt-oss:120b", "test-route", 0.2, 512)

    def response(self, **changes):
        return {"model": self.binding.model, "done": True, "done_reason": "stop",
                "message": {"role": "assistant", "content":
                            '{"action":"wait","content":"","operation":""}'}, **changes}

    def adapter(self, handler, **kwargs):
        return OllamaTransport(self.binding, "https://provider.invalid",
                               http_transport=httpx.MockTransport(handler), **kwargs)

    def request(self):
        return {"binding": asdict(self.binding), "messages": [{"role": "user", "content": "test"}]}

    async def test_policy_roundtrip_filtered_input_fixed_request(self):
        captured = []
        def handler(request):
            captured.append(request)
            return httpx.Response(200, json=self.response())
        decision = await ModelPolicy(self.binding, self.adapter(handler, api_key="test-secret"))(view(), ())
        self.assertEqual(decision.action, "wait")
        request = captured[0]
        self.assertEqual(str(request.url), "https://provider.invalid/api/chat")
        self.assertEqual(request.headers["authorization"], "Bearer test-secret")
        payload = json.loads(request.content)
        self.assertEqual(payload["options"], {"temperature": 0.2, "num_predict": 512})
        self.assertIs(payload["stream"], False)
        self.assertEqual(payload["model"], self.binding.model)
        for secret in ("never-send", "not-for-policy", "test-secret"):
            self.assertNotIn(secret, request.content.decode())
            self.assertNotIn(secret, decision.model_evidence_json)

    async def test_reasoning_effort_is_explicitly_bound_and_sent(self):
        captured = []
        def handler(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200, json=self.response())
        adapter = self.adapter(handler, reasoning_effort="low")
        await adapter(self.request())
        self.assertEqual(captured[0]["think"], "low")
        self.assertEqual(adapter.runtime_specification()["adapter"], "g5-ollama-http-v2")
        self.assertEqual(adapter.runtime_specification()["reasoning_effort"], "low")

    async def test_invalid_request_never_sent(self):
        def handler(request):
            self.fail("Unexpected HTTP request")
        for request in ({}, {**self.request(), "binding": {}},
                        {**self.request(), "messages": [{"role": "tool", "content": "x"}]}):
            with self.assertRaises(ValueError):
                await self.adapter(handler)(request)

    async def test_status_no_redirect_retry_or_body_disclosure(self):
        for status in (302, 401, 429, 500):
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(status, text="secret-prompt", headers={"location": "https://other.invalid"})
            with self.assertRaises(ConnectionError) as caught:
                await self.adapter(handler)(self.request())
            self.assertNotIn("secret-prompt", str(caught.exception))
            self.assertEqual(len(calls), 1)

    async def test_timeout_and_connection_redacted(self):
        for error, expected in ((httpx.ReadTimeout("secret"), TimeoutError),
                                (httpx.ConnectError("secret"), ConnectionError)):
            def handler(request):
                raise error
            with self.assertRaises(expected) as caught:
                await self.adapter(handler)(self.request())
            self.assertNotIn("secret", str(caught.exception))

    async def test_invalid_completion_rejected(self):
        bodies = [self.response(model="other"), self.response(done=1),
                  self.response(done_reason="length"), self.response(message={}),
                  self.response(message={"role": "assistant", "content": "", "thinking": "hidden"}),
                  self.response(message={"role": "assistant", "content": "ok", "tool_calls": [{}]})]
        for body in bodies:
            with self.assertRaises(ValueError):
                await self.adapter(lambda r: httpx.Response(200, json=body))(self.request())
        for body in (b'bad', b'{"model":"x","model":"y"}', b'[]'):
            with self.assertRaises(ValueError):
                await self.adapter(lambda r: httpx.Response(200, content=body))(self.request())

    def test_route_and_timeout_validation(self):
        for url in ("http://remote.invalid", "https://user:secret@host", "https://host?key=x",
                    "https://host/api", "https://host#fragment"):
            with self.assertRaises(ValueError):
                OllamaTransport(self.binding, url)
        for timeout in (0, float("nan"), True):
            with self.assertRaises(ValueError):
                OllamaTransport(self.binding, "https://host", timeout=timeout)
        for effort in (False, "minimal", "LOW"):
            with self.assertRaises(ValueError):
                OllamaTransport(self.binding, "https://host", reasoning_effort=effort)

    def test_transport_configuration_is_bound_without_credentials(self):
        adapter = self.adapter(lambda r: httpx.Response(200), api_key="test-secret")
        policy = ModelPolicy(self.binding, adapter)
        frozen = policy.runtime_specification()
        self.assertNotIn("test-secret", json.dumps(frozen))
        self.assertIn("transport", frozen)
        adapter._timeout = 60
        self.assertNotEqual(frozen, policy.runtime_specification())
