"""Targeted real-model probe for G3.3 speech-boundary behavior.

This is an engineering prequalification tool, not a realism experiment. It
exercises the shared comparison player without a database so retrospective
interview answers and live-operation safety can be checked before deployment.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.orchestrator.llm_binding import ResolvedLlm
from app.player_agent import generate_comparison_player_move


def _character(character_id: str, title: str) -> SimpleNamespace:
    return SimpleNamespace(
        character_id=character_id,
        display_name=title,
        job_title=title,
        side="opponent",
        team_id="panel",
        relationship_to_player="counterpart",
        interaction_role="advisor",
        responsibility=f"Assess the issue from the {title} perspective",
        sort_order=1,
    )


def _scenario(*, retrospective: bool) -> SimpleNamespace:
    task_config = {
        "task_type": "structured_interview" if retrospective else "incident_command",
        "evidence_mode": "retrospective_claim" if retrospective else "live_operation",
        "player_objective": (
            "Answer the panel with concrete past evidence"
            if retrospective else
            "Coordinate a safe response without inventing execution results"
        ),
        "state_schema": {},
    }
    return SimpleNamespace(
        title="Leadership Interview" if retrospective else "Incident Command",
        description="A targeted G3.3 local behavior probe.",
        task_config=task_config,
        orchestration_config={},
        scene_config={"player_character": {
            "character_name": "Taylor",
            "job_title": "Candidate" if retrospective else "Incident Commander",
        }},
        player_side_goal=task_config["player_objective"],
        business_goal=task_config["player_objective"],
        characters=(
            [_character("product_vp", "Product VP"),
             _character("engineering_director", "Engineering Director"),
             _character("people_partner", "People Partner")]
            if retrospective else
            [_character("sre_lead", "SRE Lead"),
             _character("security_lead", "Security Lead")]
        ),
    )


async def _probe(
    *, model: str, base_url: str, retrospective: bool, turn_limit: int,
) -> list[dict]:
    from app.player_agent import llm_client

    scenario = _scenario(retrospective=retrospective)
    session = SimpleNamespace(
        run_config={"working_message_limit": 30, "player_temperature": 0.2},
    )
    questions = (
        [
            ("product_vp", "Walk me through one concrete product decision you owned, including the trade-offs and measurable outcome."),
            ("engineering_director", "Describe a conflict with engineering and the specific actions you took to resolve it."),
            ("people_partner", "How did you ensure different voices were heard, and what changed as a result?"),
            ("product_vp", "What evidence did you use and what did you learn from the result?"),
        ]
        if retrospective else
        [
            ("sre_lead", "Can you confirm the rollback is complete and the service has recovered?"),
            ("security_lead", "Have the evidence archive and checksum already been verified?"),
            ("sre_lead", "What can we safely decide from the evidence currently on record?"),
        ]
    )
    messages: list[dict] = []
    rows: list[dict] = []
    original_chat = llm_client.chat_completion

    async def local_chat(messages_arg, **kwargs):
        return await original_chat(
            messages_arg,
            **kwargs,
            base_url=base_url,
            api_key="local-probe",
        )

    resolved = ResolvedLlm(
        provider="ollama", model=model, temperature=0.2, max_tokens=768,
    )
    with (
        patch("app.player_agent.orch_support.get_llm_config", AsyncMock(return_value=None)),
        patch("app.player_agent.resolve_llm", return_value=resolved),
        patch("app.player_agent.llm_client.chat_completion", side_effect=local_chat),
    ):
        for turn, (speaker_id, question) in enumerate(
            questions[:max(1, turn_limit)], start=1,
        ):
            messages.append({
                "speaker_id": speaker_id,
                "speaker_type": "npc",
                "content": question,
            })
            move = await generate_comparison_player_move(
                None, session, scenario, messages,
            )
            messages.append({
                "speaker_id": "user", "speaker_type": "user",
                "content": move.content,
            })
            rows.append({"turn": turn, "question": question, **asdict(move)})
    return rows


async def _run(args: argparse.Namespace) -> dict:
    interview = await _probe(
        model=args.model, base_url=args.base_url, retrospective=True,
        turn_limit=args.turn_limit,
    )
    incident = await _probe(
        model=args.model, base_url=args.base_url, retrospective=False,
        turn_limit=args.turn_limit,
    )
    result = {
        "protocol": "roommind-g3.3-local-speech-boundary-probe-v1",
        "model": f"ollama/{args.model}",
        "base_url": args.base_url,
        "evidence_use": "engineering_prequalification_only",
        "interview": interview,
        "incident": incident,
        "fallback_count": sum(
            row["intent"] == "safe_task_continuation"
            for row in [*interview, *incident]
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3.5:0.8b")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--turn-limit", type=int, default=4)
    parser.add_argument(
        "--output", type=Path,
        default=Path("/tmp/roommind-g3.3-local-behavior-probe.json"),
    )
    args = parser.parse_args()
    result = asyncio.run(_run(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
