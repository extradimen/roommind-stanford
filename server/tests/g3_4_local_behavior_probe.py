"""Engineering probe for G3.4 natural recovery and bounded artifact handling.

This is development evidence only. It does not replace a frozen matched-pair
qualification batch or independent human review.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.agent.act import render_npc_speech
from app.llm.client import LLMEmptyContentError
from app.orchestrator.llm_binding import ResolvedLlm
from g3_3_local_behavior_probe import _probe


async def _npc_probe(model: str, base_url: str) -> dict:
    from app.agent.act import llm_client

    character = SimpleNamespace(
        character_id="security_lead",
        display_name="Marcus Reed",
        persona="Careful security lead who protects evidence integrity.",
        job_title="Security Lead",
        responsibility="Validate security evidence",
        relationship_to_player="counterpart",
        authority={"can_confirm": ["security_validation"]},
        private_state={},
        fallback_actions={},
        system_prompt="",
    )
    resolved = ResolvedLlm(
        provider="ollama", model=model, temperature=0.2, max_tokens=768,
    )
    original_chat = llm_client.chat_completion

    async def local_chat(messages, **kwargs):
        return await original_chat(
            messages, **kwargs, base_url=base_url, api_key="local-probe",
        )

    intent = {
        "kind": "artifact", "subject": "security validation report",
        "transition": "committed", "simulation_scope": "external",
        "field": "security_validation",
    }
    with patch("app.agent.act.llm_client.chat_completion", side_effect=local_chat):
        content, _, _, generated = await render_npc_speech(
            character=character,
            conversation_context=(
                "Jordan: We cannot attach files here. Summarize the findings and "
                "record the signed report as a follow-up."
            ),
            user_input="What can you establish now?",
            reasoning="Provide available findings without inventing an upload.",
            draft=(
                "State that the evidence review can be summarized now and the signed "
                "report remains a post-meeting deliverable."
            ),
            npc_llm=resolved,
            active_plan_text="Validate security evidence",
            validated_intent=intent,
        )

    async def empty(*args, **kwargs):
        raise LLMEmptyContentError("probe")

    with patch("app.agent.act.llm_client.chat_completion", side_effect=empty):
        fallback, _, _, fallback_generated = await render_npc_speech(
            character=character,
            conversation_context="Jordan: What remains to be decided?",
            user_input="Please respond.",
            reasoning="Explain the unresolved evidence boundary.",
            draft="Discuss the security validation report without completing it.",
            npc_llm=resolved,
            active_plan_text="Validate security evidence",
            validated_intent=intent,
        )
    return {
        "real_model_content": content,
        "real_model_generated": generated,
        "deterministic_fallback": fallback,
        "deterministic_fallback_generated": fallback_generated,
    }


async def _run(args: argparse.Namespace) -> dict:
    result = {
        "protocol": "roommind-g3.4-local-natural-recovery-probe-v1",
        "model": f"ollama/{args.model}",
        "evidence_use": "engineering_prequalification_only",
        "interview": await _probe(
            model=args.model, base_url=args.base_url,
            retrospective=True, turn_limit=4,
        ),
        "incident": await _probe(
            model=args.model, base_url=args.base_url,
            retrospective=False, turn_limit=3,
        ),
        "npc_recovery": await _npc_probe(args.model, args.base_url),
    }
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt-oss:120b-cloud")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument(
        "--output", type=Path,
        default=Path("/tmp/roommind-g3.4-local-behavior-probe.json"),
    )
    args = parser.parse_args()
    print(json.dumps(asyncio.run(_run(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
