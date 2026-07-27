"""Offline regression checks for empty LLM output and bounded test history."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from app.llm.client import LLMClient
from app.player_agent import bounded_dialogue


class FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, payload: dict):
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class FakeAsyncClient:
    responses: list[FakeResponse] = []
    requested_budgets: list[int] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, *, json, headers):
        self.requested_budgets.append(json["max_tokens"])
        return self.responses.pop(0)


def completion(content: str | None, finish_reason: str) -> FakeResponse:
    return FakeResponse(
        {
            "choices": [
                {"message": {"content": content}, "finish_reason": finish_reason}
            ]
        }
    )


async def call_client(responses: list[FakeResponse], max_tokens: int = 200) -> str:
    FakeAsyncClient.responses = list(responses)
    FakeAsyncClient.requested_budgets = []
    client = LLMClient()
    with patch("app.llm.client.httpx.AsyncClient", FakeAsyncClient):
        return await client.chat_completion(
            [{"role": "user", "content": "test"}],
            provider="ollama",
            model="test-model",
            api_key="test-key",
            max_tokens=max_tokens,
        )


async def main() -> None:
    assert await call_client([completion("visible", "stop")]) == "visible"

    result = await call_client(
        [completion("", "length"), completion("recovered", "stop")]
    )
    assert result == "recovered"
    assert FakeAsyncClient.requested_budgets == [200, 1024]

    try:
        await call_client(
            [
                completion(None, "length"),
                completion("", "length"),
                completion("  ", "length"),
            ]
        )
    except RuntimeError as exc:
        assert "finish_reason='length'" in str(exc)
    else:
        raise AssertionError("permanently empty output must fail safely")
    assert FakeAsyncClient.requested_budgets == [200, 1024, 2048]

    messages = [
        {"speaker_id": f"speaker-{i}", "content": f"turn-{i}-" + ("x" * 100)}
        for i in range(80)
    ]
    dialogue = bounded_dialogue(messages, message_limit=6, character_limit=500)
    assert len(dialogue) <= 500
    assert "turn-79" in dialogue
    assert "turn-1-" not in dialogue

    print("LLM resilience smoke test: ok")


if __name__ == "__main__":
    asyncio.run(main())
