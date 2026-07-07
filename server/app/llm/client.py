from collections.abc import AsyncIterator
import asyncio
import json
from typing import Any

import httpx

from app.platform_config import ENV_PATH
from app.platform_llm import (
    LlmProvider,
    available_models,
    resolve_active_model,
    resolve_llm_provider,
    resolve_ollama_api_key,
    resolve_ollama_base_url,
    resolve_siliconflow_api_key,
    resolve_siliconflow_base_url,
)


class LLMClient:
    """Unified LLM client — OpenClaw-aligned Ollama Cloud + SiliconFlow."""

    PROVIDERS = ("ollama", "siliconflow")
    RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
    MAX_RETRIES = 3

    @property
    def AVAILABLE_MODELS(self) -> dict[str, list[str]]:
        return available_models()

    def _chat_url(self, provider: LlmProvider, base_url: str | None) -> str:
        if provider == "ollama":
            base = (base_url or resolve_ollama_base_url()).rstrip("/")
            if base.endswith("/v1"):
                return f"{base}/chat/completions"
            return f"{base}/v1/chat/completions"
        base = (base_url or resolve_siliconflow_base_url()).rstrip("/")
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    def _resolve_key(self, provider: LlmProvider) -> str:
        if provider == "ollama":
            return resolve_ollama_api_key()
        return resolve_siliconflow_api_key()

    def _normalize_provider(self, provider: str) -> LlmProvider:
        p = provider.strip().lower()
        if p in ("ollama", "ollama_cloud"):
            return "ollama"
        return "siliconflow"

    def _siliconflow_extras(self, model: str) -> dict[str, Any]:
        """SiliconFlow Qwen3 等模型默认关闭 thinking，避免额外延迟。"""
        model_lower = model.lower()
        if model_lower.startswith("qwen/qwen3") or "/qwen3-" in model_lower:
            return {"enable_thinking": False}
        return {}

    def _apply_provider_payload(
        self,
        payload: dict[str, Any],
        provider: LlmProvider,
        model: str,
    ) -> None:
        if provider == "siliconflow":
            payload.update(self._siliconflow_extras(model))

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        response_format: dict[str, Any] | None = None,
        db_provider: str | None = None,
        db_model: str | None = None,
    ) -> str:
        resolved_provider, resolved_model = resolve_active_model(db_provider, db_model)
        if provider:
            resolved_provider = self._normalize_provider(provider)
        if model:
            resolved_model = model

        key = api_key if api_key is not None else self._resolve_key(resolved_provider)
        if not key:
            env_name = "OLLAMA_API_KEY" if resolved_provider == "ollama" else "SILICONFLOW_API_KEY"
            raise RuntimeError(
                f"API key not configured for provider '{resolved_provider}'. "
                f"Set {env_name} in {ENV_PATH} and restart API."
            )

        url = self._chat_url(resolved_provider, base_url)
        payload: dict[str, Any] = {
            "model": resolved_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if response_format:
            payload["response_format"] = response_format
        self._apply_provider_payload(payload, resolved_provider, resolved_model)

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            for attempt in range(self.MAX_RETRIES):
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code < 400:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                if resp.status_code in self.RETRYABLE_STATUS and attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                raise RuntimeError(f"LLM API error {resp.status_code}: {resp.text[:500]}")
            raise RuntimeError("LLM API request failed after retries")

    async def chat_completion_stream(
        self,
        messages: list[dict[str, str]],
        *,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        db_provider: str | None = None,
        db_model: str | None = None,
    ) -> AsyncIterator[str]:
        resolved_provider, resolved_model = resolve_active_model(db_provider, db_model)
        if provider:
            resolved_provider = self._normalize_provider(provider)
        if model:
            resolved_model = model

        key = api_key if api_key is not None else self._resolve_key(resolved_provider)
        if not key:
            env_name = "OLLAMA_API_KEY" if resolved_provider == "ollama" else "SILICONFLOW_API_KEY"
            raise RuntimeError(
                f"API key not configured for provider '{resolved_provider}'. "
                f"Set {env_name} in {ENV_PATH} and restart API."
            )

        url = self._chat_url(resolved_provider, base_url)
        payload: dict[str, Any] = {
            "model": resolved_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        self._apply_provider_payload(payload, resolved_provider, resolved_model)
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            for attempt in range(self.MAX_RETRIES):
                async with client.stream("POST", url, json=payload, headers=headers) as resp:
                    if resp.status_code >= 400:
                        body = await resp.aread()
                        if resp.status_code in self.RETRYABLE_STATUS and attempt < self.MAX_RETRIES - 1:
                            await asyncio.sleep(1.0 * (attempt + 1))
                            break
                        raise RuntimeError(f"LLM API error {resp.status_code}: {body.decode()[:500]}")
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            return
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                        if delta:
                            yield delta
                    return
            raise RuntimeError("LLM API stream failed after retries")


llm_client = LLMClient()
