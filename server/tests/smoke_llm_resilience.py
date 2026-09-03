"""Offline regression checks for empty LLM output and bounded test history."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from app.llm.client import LLMClient, LLMEmptyContentError, llm_provider_failover_enabled
from app.agent.act import contextual_public_fallback, render_npc_speech
from app.player_agent import bounded_dialogue, safe_comparison_player_fallback
from app.external_evaluator import (
    REALISM_DIMENSIONS as EVALUATOR_DIMENSIONS,
    _dispatch_metrics,
    _evaluate_dimension,
    _normalize_evaluation,
    _public_transcript,
    evaluate_public_transcript,
    missing_evaluation_dimensions,
)
from app.batch_experiments import _dialogue_retry_result, _performance_summary
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
    performance = _performance_summary([{"llm_events": [
        {"event": "dialogue.safe_fallback.used"},
        {"event": "llm.degraded_fallback"},
    ]}])
    assert performance["dialogue_safe_fallback_count"] == 1
    assert performance["llm_degraded_fallback_count"] == 1
    historical_fallbacks = [
        safe_comparison_player_fallback(
            evidence_mode="retrospective_claim", pending_questions=[], turn_id=turn,
        )[0]
        for turn in range(1, 4)
    ]
    assert len(set(historical_fallbacks)) >= 2
    assert all("clarify the most important unresolved" not in row.casefold()
               for row in historical_fallbacks)
    inclusive_fallback, _ = safe_comparison_player_fallback(
        evidence_mode="retrospective_claim",
        pending_questions=[{
            "speaker_id": "people_partner",
            "question": "How did you ensure different voices were heard, and what changed as a result?",
        }],
        turn_id=3,
    )
    assert "least-heard" in inclusive_fallback or "each function" in inclusive_fallback
    live_content, live_intent = safe_comparison_player_fallback(
        evidence_mode="live_operation",
        pending_questions=[{"speaker_id": "finance_lead", "question": "Evidence?"}],
        turn_id=1,
    )
    assert "Finance Lead" in live_content
    assert "responsible participant" not in live_content.casefold()
    assert live_intent["target_id"] == "finance_lead"
    npc_fallback = contextual_public_fallback(
        SimpleNamespace(
            job_title="Operations Director", responsibility="Validate capacity",
            relationship_to_player="counterpart",
        ),
        {"subject": "pilot readiness", "transition": "proposed"},
    )
    assert "pilot readiness" in npc_fallback
    assert "remains open" not in npc_fallback.casefold()
    assert "responsible owner" not in npc_fallback.casefold()
    assert "highest-priority open issue" not in npc_fallback
    direct_character = SimpleNamespace(
        character_id="operations_lead", display_name="Operations Lead",
        persona="Concise and evidence-led", authority={}, private_state={},
        system_prompt="",
    )
    direct_reply, _, _, direct_used = await render_npc_speech(
        character=direct_character,
        conversation_context="The team is discussing pilot readiness.",
        user_input="What can we decide?",
        reasoning="Offer a bounded proposal.",
        draft="I propose a limited pilot while the remaining evidence is reviewed.",
        npc_llm=SimpleNamespace(
            provider="ollama", model="unused", temperature=0.0, max_tokens=512,
        ),
        validated_intent={
            "kind": "proposal", "subject": "limited pilot",
            "transition": "proposed", "simulation_scope": "discussion",
            "evidence_source": "public_statement",
        },
    )
    assert direct_used is True
    assert direct_reply == "I propose a limited pilot while the remaining evidence is reviewed."
    outcome_fallback = contextual_public_fallback(
        direct_character,
        {"kind": "outcome", "subject": "the launch decision", "transition": "blocked"},
    )
    assert "defer the final decision" in outcome_fallback

    artifact_content, artifact_intent = safe_comparison_player_fallback(
        evidence_mode="live_operation",
        pending_questions=[{
            "speaker_id": "security_lead",
            "question": "Can you upload the signed validation report?",
        }],
        turn_id=2,
    )
    assert "post-meeting deliverable" in artifact_content
    assert artifact_intent["kind"] == "handoff"

    partial_evaluation = {
        "dimensions": {
            name: {
                "dimension_score": 6,
                "metrics": {
                    metric: {"score": 6, "evidence_sequence_nos": [1], "reason": "frozen"}
                    for metric in EVALUATOR_DIMENSIONS[name]
                },
            }
            for name in EVALUATOR_DIMENSIONS if name != "role_strategic_fidelity"
        },
        "evaluation_errors": {"role_strategic_fidelity": "truncated JSON"},
    }
    assert missing_evaluation_dimensions(partial_evaluation) == ["role_strategic_fidelity"]
    partial_evaluation["dimensions"]["role_strategic_fidelity"] = {
        "dimension_score": 5,
        "metrics": {
            metric: {"score": 5, "evidence_sequence_nos": [1], "reason": "retried"}
            for metric in EVALUATOR_DIMENSIONS["role_strategic_fidelity"]
        },
    }
    assert missing_evaluation_dimensions(partial_evaluation) == []
    partial_evaluation["dimensions"]["temporal_coherence"]["metrics"]["fact_retention"] = {
        "score": 1, "evidence_sequence_nos": [], "reason": "",
    }
    assert missing_evaluation_dimensions(partial_evaluation) == ["temporal_coherence"]
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
        id=1, title="Independent baseline fixture", description="A public case",
        player_side_goal="Reach a decision", business_goal="Reach a decision",
        opponent_side_goal="Protect interests", task_config={}, phases=["opening"],
        win_conditions=[], orchestration_config={}, characters=full_profiles,
    )
    frozen_dimensions = {
        name: {
            "dimension_score": 6,
            "metrics": {
                metric: {"score": 6, "evidence_sequence_nos": [1], "reason": "frozen"}
                for metric in metrics
            },
            "strengths": [], "issues": [], "notes": "frozen",
        }
        for name, metrics in EVALUATOR_DIMENSIONS.items()
        if name != "role_strategic_fidelity"
    }
    incremental_existing = {
        "dimensions": frozen_dimensions,
        "evaluation_errors": {"role_strategic_fidelity": "previous truncation"},
    }
    evaluated_names: list[str] = []

    async def one_missing_dimension(**kwargs):
        evaluated_names.append(kwargs["dimension"])
        return {
            "dimension_score": 5,
            "metrics": {
                metric: {"score": 5, "evidence_sequence_nos": [1], "reason": "retry"}
                for metric in kwargs["metrics"]
            },
            "strengths": [], "issues": [], "notes": "retried",
        }

    evaluator_resolved = SimpleNamespace(
        provider="ollama", model="fixture", max_tokens=600,
        label=lambda: "ollama/fixture",
    )
    with (
        patch("app.external_evaluator.orch_support.get_llm_config", AsyncMock(return_value={})),
        patch("app.external_evaluator.orch_support.load_dispatch_rules", AsyncMock(return_value=[])),
        patch("app.external_evaluator.resolve_llm", return_value=evaluator_resolved),
        patch("app.external_evaluator._evaluate_dimension", side_effect=one_missing_dimension),
    ):
        incremental_result = await evaluate_public_transcript(
            None, scenario=scenario, messages=[], system_claim={},
            existing_evaluation=incremental_existing,
        )
    assert evaluated_names == ["role_strategic_fidelity"]
    assert incremental_result["dimensions"]["epistemic_fidelity"] == frozen_dimensions["epistemic_fidelity"]
    assert incremental_result["dimension_scores"]["role_strategic_fidelity"] == 5
    assert incremental_result["evaluation_errors"] == {}

    malformed_then_valid = [
        '{"dimension_score":6,"metrics":{}}',
        json.dumps({
            "dimension_score": 5,
            "metrics": {
                metric: {
                    "score": 5, "evidence_sequence_nos": [1], "reason": "Grounded reason",
                }
                for metric in EVALUATOR_DIMENSIONS["role_strategic_fidelity"]
            },
            "strengths": [], "issues": [], "notes": "valid",
        }),
    ]
    with patch(
        "app.external_evaluator.llm_client.chat_completion",
        AsyncMock(side_effect=malformed_then_valid),
    ):
        strict_dimension = await _evaluate_dimension(
            dimension="role_strategic_fidelity",
            metrics=EVALUATOR_DIMENSIONS["role_strategic_fidelity"],
            gold={},
            transcript=[{
                "sequence_no": 1, "turn_id": 1, "speaker_id": "npc", "content": "Evidence",
            }],
            system_claim={}, provider="ollama", model="fixture", max_tokens=600,
        )
    assert strict_dimension["dimension_score"] == 5
    assert all(row["reason"] for row in strict_dimension["metrics"].values())
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
