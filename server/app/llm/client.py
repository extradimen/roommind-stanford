from collections.abc import AsyncIterator
import asyncio
from contextvars import ContextVar
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
    resolve_ollama_model_id,
    resolve_siliconflow_api_key,
    resolve_siliconflow_base_url,
    resolve_siliconflow_model_id,
)
from app.telemetry import emit, monotonic_ms


# Provider failover is a user-experience policy, not an experimental policy.
# Participation sessions enable it explicitly; controlled test/baseline runs
# leave it disabled so both conditions remain bound to the configured model.
llm_provider_failover_enabled: ContextVar[bool] = ContextVar(
    "llm_provider_failover_enabled", default=False
)


class LLMEmptyContentError(RuntimeError):
    """The provider returned HTTP success but no usable visible response."""


class LLMClient:
    """Unified LLM client — OpenClaw-aligned Ollama Cloud + SiliconFlow."""

    PROVIDERS = ("ollama", "siliconflow")
    RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
    MAX_RETRIES = 3
    LENGTH_RETRY_MIN_TOKENS = 1024
    LENGTH_RETRY_MAX_TOKENS = 4096
    FAILOVER_STATUS = frozenset({402, 403, 404, 410})

    @staticmethod
    def _compact_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Bound generic long prompts while preserving instructions and recency."""
        if not messages:
            return []
        compacted: list[dict[str, str]] = []
        last_index = len(messages) - 1
        for index, row in enumerate(messages):
            content = str(row.get("content") or "")
            role = str(row.get("role") or "user")
            if role == "system":
                # Keep both the beginning and final output contract.
                if len(content) > 12000:
                    content = content[:8000] + "\n...[older context compacted]...\n" + content[-4000:]
            elif index == last_index:
                content = content[-8000:]
            else:
                content = content[-2500:]
            compacted.append({**row, "role": role, "content": content})
        # Very long histories keep the system message(s) and recent dialogue.
        systems = [row for row in compacted if row.get("role") == "system"]
        dialogue = [row for row in compacted if row.get("role") != "system"][-12:]
        return [*systems, *dialogue]

    def _fallback_target(self, provider: LlmProvider) -> tuple[LlmProvider, str] | None:
        if not llm_provider_failover_enabled.get():
            return None
        if provider == "ollama" and resolve_siliconflow_api_key():
            return "siliconflow", resolve_siliconflow_model_id()
        if provider == "siliconflow" and resolve_ollama_api_key():
            return "ollama", resolve_ollama_model_id()
        return None

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
        _failover_attempted: bool = False,
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
        request_messages = list(messages)
        payload: dict[str, Any] = {
            "model": resolved_model,
            "messages": request_messages,
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
                    input_characters=sum(len(str(row.get("content") or "")) for row in request_messages),
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
                    fallback = None if _failover_attempted else self._fallback_target(resolved_provider)
                    if fallback:
                        emit("llm.request.provider_failover", from_provider=resolved_provider,
                             from_model=resolved_model, to_provider=fallback[0], to_model=fallback[1],
                             reason="transport_error")
                        return await self.chat_completion(
                            messages, provider=fallback[0], model=fallback[1], temperature=temperature,
                            max_tokens=max_tokens, response_format=response_format,
                            _failover_attempted=True,
                        )
                    raise RuntimeError(
                        f"LLM provider {resolved_provider}/{resolved_model} is unreachable after "
                        f"{self.MAX_RETRIES} attempts: {type(exc).__name__}: {exc!r}"
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
                    if attempt < self.MAX_RETRIES - 1:
                        if finish_reason == "length":
                            # Reasoning models may consume the entire small output
                            # budget before emitting visible content.
                            payload["max_tokens"] = min(
                                max(
                                    int(payload["max_tokens"]) * 2,
                                    self.LENGTH_RETRY_MIN_TOKENS,
                                ),
                                self.LENGTH_RETRY_MAX_TOKENS,
                            )
                            if attempt >= 1:
                                request_messages = self._compact_messages(messages)
                                payload["messages"] = request_messages
                        emit(
                            "llm.request.length_retry"
                            if finish_reason == "length"
                            else "llm.request.empty_retry",
                            provider=resolved_provider,
                            model=resolved_model,
                            attempt=attempt + 1,
                            finish_reason=finish_reason,
                            duration_ms=monotonic_ms(started),
                            next_max_tokens=payload["max_tokens"],
                        )
                        # A provider can occasionally return HTTP 200 and
                        # finish_reason=stop with an empty message. Treat that as
                        # a transient unusable response, just like a retryable
                        # transport failure, instead of aborting the whole run.
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                    emit(
                        "llm.request.empty",
                        provider=resolved_provider,
                        model=resolved_model,
                        attempt=attempt + 1,
                        finish_reason=finish_reason,
                        duration_ms=monotonic_ms(started),
                    )
                    fallback = None if _failover_attempted else self._fallback_target(resolved_provider)
                    if fallback:
                        emit("llm.request.provider_failover", from_provider=resolved_provider,
                             from_model=resolved_model, to_provider=fallback[0], to_model=fallback[1],
                             reason=f"empty_{finish_reason}")
                        return await self.chat_completion(
                            self._compact_messages(messages), provider=fallback[0], model=fallback[1],
                            temperature=temperature, max_tokens=max_tokens,
                            response_format=response_format, _failover_attempted=True,
                        )
                    raise LLMEmptyContentError(
                        f"LLM provider {resolved_provider}/{resolved_model} returned no visible "
                        f"content after retries (finish_reason={finish_reason!r})"
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
                fallback = (
                    None if _failover_attempted or resp.status_code not in (
                        self.FAILOVER_STATUS | self.RETRYABLE_STATUS
                    )
                    else self._fallback_target(resolved_provider)
                )
                if fallback:
                    emit("llm.request.provider_failover", from_provider=resolved_provider,
                         from_model=resolved_model, to_provider=fallback[0], to_model=fallback[1],
                         reason=f"http_{resp.status_code}")
                    return await self.chat_completion(
                        messages, provider=fallback[0], model=fallback[1], temperature=temperature,
                        max_tokens=max_tokens, response_format=response_format,
                        _failover_attempted=True,
                    )
                hint = {
                    402: "billing or quota problem",
                    403: "authorization, billing, or quota problem",
                    404: "model or endpoint not found",
                    410: "model has been retired",
                }.get(resp.status_code, "provider request failed")
                raise RuntimeError(
                    f"LLM provider {resolved_provider}/{resolved_model}: {hint} "
                    f"(HTTP {resp.status_code}). Check the provider settings. {resp.text[:300]}"
                )
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
