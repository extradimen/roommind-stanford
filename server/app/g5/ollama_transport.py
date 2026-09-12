"""Explicit Ollama HTTP route; no environment discovery, retries or fallbacks.

Construction does not contact the network. Callers own authorization to invoke
the route. Inject an httpx transport for offline protocol tests.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import math
from urllib.parse import urlsplit

import httpx

from app.factorial_study import digest
from app.g5.model_policy import Completion, ModelBinding, _unique_object


class OllamaTransport:
    def __init__(self, binding: ModelBinding, base_url: str, *, api_key: str | None = None,
                 timeout: float = 120, http_transport=None):
        binding.validate()
        route = urlsplit(base_url)
        if (binding.provider != "ollama" or route.scheme not in ("https", "http")
                or not route.hostname or route.username or route.password
                or route.query or route.fragment or route.path not in ("", "/")
                or (route.scheme == "http" and route.hostname not in ("localhost", "127.0.0.1", "::1"))):
            raise ValueError("Invalid explicit Ollama route")
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Invalid HTTP timeout")
        if api_key is not None and (not isinstance(api_key, str) or not api_key.strip()
                                    or any(c.isspace() for c in api_key)):
            raise ValueError("Invalid explicit credential")
        self.binding = binding
        self._url = base_url.rstrip("/") + "/api/chat"
        self._api_key = api_key
        self._timeout = timeout
        self._http_transport = http_transport

    def runtime_specification(self):
        return {"adapter": "g5-ollama-http-v1", "binding": asdict(self.binding),
                "route_sha256": digest(self._url), "timeout": self._timeout,
                "stream": False, "format": "json", "redirects": False,
                "ambient_environment": False, "automatic_retries": 0}

    async def __call__(self, request: dict) -> Completion:
        if (not isinstance(request, dict) or set(request) != {"binding", "messages"}
                or digest(request["binding"]) != digest(asdict(self.binding))):
            raise ValueError("HTTP request binding mismatch")
        messages = request["messages"]
        if (not isinstance(messages, list) or not messages
                or any(not isinstance(m, dict) or set(m) != {"role", "content"}
                       or m["role"] not in ("system", "user", "assistant")
                       or not isinstance(m["content"], str) for m in messages)):
            raise ValueError("Invalid HTTP messages")
        request_hash = digest(request)
        payload = {"model": self.binding.model, "messages": messages, "stream": False,
                   "format": "json", "options": {"temperature": self.binding.temperature,
                                                   "num_predict": self.binding.max_tokens}}
        headers = {"Authorization": "Bearer " + self._api_key} if self._api_key else {}
        # No ambient proxies, cookies, credential sources or redirect following.
        try:
            async with httpx.AsyncClient(transport=self._http_transport, trust_env=False,
                                        follow_redirects=False, timeout=self._timeout) as client:
                response = await client.post(self._url, json=payload, headers=headers)
        except httpx.TimeoutException:
            raise TimeoutError("Ollama transport timeout") from None
        except httpx.HTTPError:
            raise ConnectionError("Ollama transport failure") from None
        if response.status_code != 200:
            raise ConnectionError("Ollama HTTP status " + str(response.status_code))
        try:
            data = json.loads(response.content, object_pairs_hook=_unique_object)
        except (ValueError, UnicodeError):
            raise ValueError("Invalid Ollama response JSON") from None
        if not isinstance(data, dict) or data.get("model") != self.binding.model:
            raise ValueError("Ollama response model mismatch")
        message = data.get("message")
        if (data.get("done") is not True or data.get("done_reason") != "stop"
                or not isinstance(message, dict) or message.get("role") != "assistant"
                or not isinstance(message.get("content"), str) or not message["content"].strip()
                or message.get("tool_calls") or message.get("images")):
            raise ValueError("Incomplete or unsupported Ollama response")
        return Completion(message["content"], self.binding.provider, data["model"],
                          self.binding.endpoint_id, request_hash, "stop")
