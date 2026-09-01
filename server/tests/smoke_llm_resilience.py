"""Offline regression checks for empty LLM output and bounded test history."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from app.llm.client import LLMClient, LLMEmptyContentError, llm_provider_failover_enabled
from app.player_agent import bounded_dialogue
from app.external_evaluator import _dispatch_metrics, _normalize_evaluation, _public_transcript
from app.batch_experiments import _dialogue_retry_result
from app.baseline_chat import (
    BASELINE_MEMORY_KEY,
    _agent_memory,
    _character_prompt,
    generate_baseline_turn,
    _remember_public_turn,
)


class FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, payload: dict):
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class FakeAsyncClient:
    responses: list[FakeResponse | Exception] = []
    requested_budgets: list[int] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, *, json, headers):
        self.requested_budgets.append(json["max_tokens"])
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def completion(content: str | None, finish_reason: str) -> FakeResponse:
    return FakeResponse(
        {
            "choices": [
                {"message": {"content": content}, "finish_reason": finish_reason}
            ]
        }
    )


async def call_client(responses: list[FakeResponse | Exception], max_tokens: int = 200) -> str:
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
    compact_source = [
        {"role": "system", "content": "S" * 20000},
        *({"role": "user", "content": f"old-{i}-" + "x" * 4000} for i in range(20)),
        {"role": "user", "content": "LATEST-" + "y" * 10000},
    ]
    compacted = LLMClient._compact_messages(compact_source)
    assert len(compacted) == 13
    assert compacted[0]["role"] == "system"
    assert "older context compacted" in compacted[0]["content"]
    assert "LATEST-" not in compacted[-1]["content"]  # bounded from the right
    assert compacted[-1]["content"].endswith("y" * 100)

    failover_client = LLMClient()
    token = llm_provider_failover_enabled.set(True)
    try:
        with patch("app.llm.client.resolve_siliconflow_api_key", return_value="configured"), patch(
            "app.llm.client.resolve_siliconflow_model_id", return_value="fallback-model"
        ):
            assert failover_client._fallback_target("ollama") == (
                "siliconflow", "fallback-model"
            )
    finally:
        llm_provider_failover_enabled.reset(token)
    assert failover_client._fallback_target("ollama") is None

    characters = [
        SimpleNamespace(character_id="agent_a"),
        SimpleNamespace(character_id="agent_b"),
    ]
    baseline_session = SimpleNamespace(shared_state={})
    assert _agent_memory(baseline_session, "agent_a") == []
    _remember_public_turn(
        baseline_session, characters,
        [{"speaker_id": "user", "content": "Public opening"}], message_limit=5,
    )
    assert set(baseline_session.shared_state[BASELINE_MEMORY_KEY]) == {"agent_a", "agent_b"}
    assert _agent_memory(baseline_session, "agent_a") == [
        {"speaker_id": "user", "content": "Public opening"}
    ]
    baseline_session.shared_state[BASELINE_MEMORY_KEY]["agent_a"].append({
        "speaker_id": "agent_a", "content": "Private copy mutation",
    })
    assert len(_agent_memory(baseline_session, "agent_a")) == 2
    assert len(_agent_memory(baseline_session, "agent_b")) == 1

    profile = SimpleNamespace(
        character_id="agent_a", display_name="Agent A", job_title="Director",
        sort_order=1,
        side="opponent", team_id="team_a", relationship_to_player="counterpart",
        interaction_role="decision_maker", persona="Firm", responsibility="Decide",
        tendency={}, private_state={"secret": "A-only"}, authority={}, system_prompt="",
    )
    assert _character_prompt(profile)["private_state"] == {"secret": "A-only"}

    full_profiles = [
        profile,
        SimpleNamespace(
            character_id="agent_b", display_name="Agent B", job_title="Manager",
            sort_order=2,
            side="opponent", team_id="team_b", relationship_to_player="counterpart",
            interaction_role="advisor", persona="Careful", responsibility="Advise",
            tendency={}, private_state={"secret": "B-only"}, authority={}, system_prompt="",
        ),
    ]
    scenario = SimpleNamespace(
        title="Independent baseline fixture", description="A public case",
        player_side_goal="Reach a decision", business_goal="Reach a decision",
        opponent_side_goal="Protect interests", task_config={}, phases=["opening"],
        win_conditions=[], orchestration_config={}, characters=full_profiles,
    )
    generation_session = SimpleNamespace(
        shared_state={},
        run_config={"working_message_limit": 5, "comparison_lock_model": True},
        current_phase="opening",
    )
    resolved = SimpleNamespace(
        provider="ollama", model="fixture", temperature=0.2, max_tokens=600,
        label=lambda: "ollama/fixture",
    )
    prompts: list[str] = []

    async def independent_reply(messages, **kwargs):
        assert [row["role"] for row in messages] == ["system", "user"]
        prompt_text = "\n".join(row["content"] for row in messages)
        prompts.append(prompt_text)
        own_id = "agent_a" if "A-only" in prompt_text else "agent_b"
        return (
            '{"action":"speak","content":"Reply from ' + own_id
            + '","declared_phase":"opening","declared_complete":false}'
        )

    with (
        patch("app.baseline_chat.orch_support.get_llm_config", AsyncMock(return_value={})),
        patch("app.baseline_chat.resolve_llm", return_value=resolved),
        patch("app.baseline_chat.llm_client.chat_completion", side_effect=independent_reply),
    ):
        baseline_turn = await generate_baseline_turn(
            None, generation_session, scenario,
            [{"speaker_id": "user", "content": "Please respond."}],
        )
    assert len(prompts) == 2
    assert sum("A-only" in prompt_text for prompt_text in prompts) == 1
    assert sum("B-only" in prompt_text for prompt_text in prompts) == 1
    assert {row["speaker_id"] for row in baseline_turn.replies} == {"agent_a", "agent_b"}

    failed_at = datetime(2026, 8, 3, tzinfo=timezone.utc)
    failed_run = SimpleNamespace(
        result={
            "dialogue_status": "failed", "failure_stage": "autonomous_turn_7",
            "exception_type": "RuntimeError",
        },
        status="dialogue_failed", session_uuid="old-session", error="model timeout",
        started_at=failed_at, finished_at=failed_at,
    )
    retried = _dialogue_retry_result(failed_run)
    assert retried["dialogue_attempt_count"] == 2
    assert retried["dialogue_retry_history"][0]["session_uuid"] == "old-session"
    assert retried["dialogue_retry_history"][0]["failure_stage"] == "autonomous_turn_7"
    assert retried["evaluation_status"] == "not_started"
    assert retried["dialogue_status"] == "queued"

    assert await call_client([completion("visible", "stop")]) == "visible"

    result = await call_client(
        [completion("", "length"), completion("recovered", "stop")]
    )
    assert result == "recovered"
    assert FakeAsyncClient.requested_budgets == [200, 1024]

    result = await call_client(
        [completion("", "stop"), completion("recovered after empty stop", "stop")]
    )
    assert result == "recovered after empty stop"
    assert FakeAsyncClient.requested_budgets == [200, 200]

    result = await call_client([
        httpx.ReadTimeout("simulated timeout"),
        completion("recovered after timeout", "stop"),
    ])
    assert result == "recovered after timeout"
    assert FakeAsyncClient.requested_budgets == [200, 200]

    try:
        await call_client(
            [
                completion(None, "length"),
                completion("", "length"),
                completion("  ", "length"),
            ]
        )
    except LLMEmptyContentError as exc:
        assert "finish_reason='length'" in str(exc)
    else:
        raise AssertionError("permanently empty output must fail safely")
    assert FakeAsyncClient.requested_budgets == [200, 1024, 2048]

    try:
        await call_client([
            completion(None, "stop"), completion("", "stop"), completion("  ", "stop"),
        ])
    except LLMEmptyContentError as exc:
        assert "finish_reason='stop'" in str(exc)
    else:
        raise AssertionError("permanently empty stop output must fail safely")
    assert FakeAsyncClient.requested_budgets == [200, 200, 200]

    messages = [
        {"speaker_id": f"speaker-{i}", "content": f"turn-{i}-" + ("x" * 100)}
        for i in range(80)
    ]
    dialogue = bounded_dialogue(messages, message_limit=6, character_limit=500)
    assert len(dialogue) <= 500
    assert "turn-79" in dialogue
    assert "turn-1-" not in dialogue

    assert _normalize_evaluation('{"externally_validated_completion": true}') == {
        "externally_validated_completion": True
    }
    assert _normalize_evaluation(
        '```json\n{"evaluation":{"externally_validated_completion":false}}\n```'
    ) == {"externally_validated_completion": False}
    assert _normalize_evaluation('{"notes":"missing required decision"}') is None
    wrapped_dimension = _normalize_evaluation(
        '{"role_strategic_fidelity":{"dimension_score":6,"metrics":{}}}',
        "role_strategic_fidelity",
    )
    assert wrapped_dimension and wrapped_dimension["dimension_score"] == 6
    canonical_dimension = _normalize_evaluation(
        '{"dimension_score":5,"metrics":{"role_consistency":{"score":6}}}',
        "role_strategic_fidelity",
    )
    assert canonical_dimension and canonical_dimension["dimension_score"] == 5
    assert canonical_dimension["metrics"]["role_consistency"]["score"] == 6

    transcript = _public_transcript([
        {"speaker_type": "npc", "sequence_no": i, "turn_id": i, "speaker_id": "npc", "content": "x" * 1200}
        for i in range(100)
    ])
    assert len(transcript) == 100
    assert transcript[0]["sequence_no"] == 0
    assert len(transcript[0]["content"]) == 900

    class Rule:
        trigger_keywords = ["quality"]
        priority_character_ids = ["quality_director"]
        max_speakers = 1

    dispatch = _dispatch_metrics([
        {"turn_id": 1, "speaker_id": "user", "content": "Discuss quality"},
        {"turn_id": 1, "speaker_id": "quality_director", "content": "Ready"},
    ], [Rule()])
    assert dispatch["dispatch_precision"] == 1.0
    assert dispatch["dispatch_recall"] == 1.0

    print("LLM resilience smoke test: ok")


if __name__ == "__main__":
    asyncio.run(main())
