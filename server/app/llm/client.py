from collections.abc import AsyncIterator
import asyncio
import json
import time
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
from app.telemetry import emit, monotonic_ms


class LLMClient:
    """Unified LLM client — OpenClaw-aligned Ollama Cloud + SiliconFlow."""

    PROVIDERS = ("ollama", "siliconflow")
    RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
    MAX_RETRIES = 3
    LENGTH_RETRY_MIN_TOKENS = 1024
    LENGTH_RETRY_MAX_TOKENS = 4096

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
                started = time.monotonic()
                emit(
                    "llm.request.started",
                    provider=resolved_provider,
                    model=resolved_model,
                    attempt=attempt + 1,
                    max_attempts=self.MAX_RETRIES,
                    max_tokens=payload.get("max_tokens"),
                    message_count=len(messages),
                    input_characters=sum(len(str(row.get("content") or "")) for row in messages),
                    response_format=(response_format or {}).get("type"),
                )
                try:
                    resp = await client.post(url, json=payload, headers=headers)
                except httpx.TransportError as exc:
                    emit(
                        "llm.request.transport_error",
                        provider=resolved_provider,
                        model=resolved_model,
                        attempt=attempt + 1,
                        exception_type=type(exc).__name__,
                        error=repr(exc)[:1000],
                        duration_ms=monotonic_ms(started),
                        retrying=attempt < self.MAX_RETRIES - 1,
                    )
                    if attempt < self.MAX_RETRIES - 1:
                        await asyncio.sleep(1.0 * (attempt + 1))
                        continue
                    raise RuntimeError(
                        f"LLM transport failed after {self.MAX_RETRIES} attempts: "
                        f"{type(exc).__name__}: {exc!r}"
                    ) from exc
                if resp.status_code < 400:
                    data = resp.json()
                    content = data["choices"][0]["message"].get("content")
                    if isinstance(content, str) and content.strip():
                        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
                        emit(
                            "llm.request.succeeded",
                            provider=resolved_provider,
                            model=resolved_model,
                            attempt=attempt + 1,
                            duration_ms=monotonic_ms(started),
                            output_characters=len(content),
                            prompt_tokens=usage.get("prompt_tokens"),
                            completion_tokens=usage.get("completion_tokens"),
                            total_tokens=usage.get("total_tokens"),
                            finish_reason=data.get("choices", [{}])[0].get("finish_reason"),
                        )
                        return content
                    finish_reason = data.get("choices", [{}])[0].get("finish_reason")
                    if finish_reason == "length" and attempt < self.MAX_RETRIES - 1:
                        # Reasoning models may consume the entire small output budget
                        # before emitting visible content. Jump to a useful floor on
                        # the first retry, then grow normally while remaining bounded.
                        payload["max_tokens"] = min(
                            max(
                                int(payload["max_tokens"]) * 2,
                                self.LENGTH_RETRY_MIN_TOKENS,
                            ),
                            self.LENGTH_RETRY_MAX_TOKENS,
                        )
                        emit(
                            "llm.request.length_retry",
                            provider=resolved_provider,
                            model=resolved_model,
                            attempt=attempt + 1,
                            duration_ms=monotonic_ms(started),
                            next_max_tokens=payload["max_tokens"],
                        )
                        continue
                    emit(
                        "llm.request.empty",
                        provider=resolved_provider,
                        model=resolved_model,
                        attempt=attempt + 1,
                        finish_reason=finish_reason,
                        duration_ms=monotonic_ms(started),
                    )
                    raise RuntimeError(
                        f"LLM API returned no visible content (finish_reason={finish_reason!r})"
                    )
                if resp.status_code in self.RETRYABLE_STATUS and attempt < self.MAX_RETRIES - 1:
                    emit(
                        "llm.request.http_retry",
                        provider=resolved_provider,
                        model=resolved_model,
                        attempt=attempt + 1,
                        status_code=resp.status_code,
                        duration_ms=monotonic_ms(started),
                    )
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                emit(
                    "llm.request.http_error",
                    provider=resolved_provider,
                    model=resolved_model,
                    attempt=attempt + 1,
                    status_code=resp.status_code,
                    duration_ms=monotonic_ms(started),
                    response_preview=resp.text[:500],
                )
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
