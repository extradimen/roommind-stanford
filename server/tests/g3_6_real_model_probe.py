"""Small configured-model probe for G3.6 public speech behavior.

This is engineering evidence only. It uses the configured provider credentials
and does not create sessions, touch the database, or replace a frozen matched
qualification batch.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from app.agent.act import render_npc_speech
from app.agent.speech_safety import speech_rejection_reason
from app.orchestrator.llm_binding import ResolvedLlm


CASES = (
    {
        "name": "negotiation",
        "character_id": "supplier_ceo",
        "display_name": "Mr. Wang",
        "job_title": "Supplier CEO",
        "persona": "Commercially firm, concise, and relationship-aware.",
        "responsibility": "Own price, volume, and commercial commitments.",
        "context": "Alex: We can accept 84 RMB if the 30-day delivery commitment is firm.",
        "input": "What terms can you confirm today?",
        "draft": "Respond with the terms you can accept and one condition that remains unresolved.",
        "intent": {"kind": "proposal", "subject": "commercial terms", "transition": "proposed", "simulation_scope": "discussion", "evidence_source": "public_statement", "validation": "accepted"},
    },
    {
        "name": "launch",
        "character_id": "cfo",
        "display_name": "Nora Chen",
        "job_title": "CFO",
        "persona": "Evidence-led, cautious, and direct about financial uncertainty.",
        "responsibility": "Evaluate budget exposure and approve financial commitments.",
        "context": "Sales: Demand looks promising. Operations: A limited launch is feasible.",
        "input": "Can finance support the launch decision?",
        "draft": "State what finance can assess from the evidence and what remains conditional without inventing a budget approval.",
        "intent": {"kind": "issue", "subject": "budget readiness", "transition": "proposed", "field": "budget_approved", "value": None, "simulation_scope": "discussion", "evidence_source": "public_statement", "validation": "accepted"},
    },
    {
        "name": "interview",
        "character_id": "engineering_director",
        "display_name": "Daniel Wu",
        "job_title": "Engineering Director",
        "persona": "Specific, analytical, and interested in trade-offs.",
        "responsibility": "Assess engineering collaboration evidence.",
        "context": "Candidate: In my previous role, I used a limited rollout to resolve a product-engineering disagreement.",
        "input": "Continue the interview without repeating the same question.",
        "draft": "Ask one concise follow-up about the candidate's personal action and measurable result.",
        "intent": {"kind": "statement", "subject": "engineering collaboration evidence", "transition": "proposed", "simulation_scope": "discussion", "evidence_source": "public_statement", "validation": "accepted"},
    },
    {
        "name": "incident",
        "character_id": "sre_lead",
        "display_name": "Priya Shah",
        "job_title": "SRE Lead",
        "persona": "Calm, technical, and precise about observed versus pending work.",
        "responsibility": "Diagnose impact and execute containment and recovery.",
        "context": "Security: Capture and verify volatile evidence before changing traffic controls.",
        "input": "Is containment active yet?",
        "draft": "Explain that evidence capture is still in progress and state the next proposed action; do not claim containment, verification, or deployment completed.",
        "intent": {"kind": "action", "subject": "activate containment", "transition": "committed", "field": "containment_active", "value": True, "simulation_scope": "external", "evidence_source": "external_followup", "validation": "accepted"},
    },
)


async def run(model: str, output: Path) -> dict:
    resolved = ResolvedLlm(
        provider="ollama", model=model, temperature=0.2, max_tokens=768,
    )
    rows = []
    for case in CASES:
        character = SimpleNamespace(
            character_id=case["character_id"],
            display_name=case["display_name"],
            job_title=case["job_title"],
            persona=case["persona"],
            responsibility=case["responsibility"],
            relationship_to_player="counterpart",
            authority={}, private_state={}, fallback_actions={}, system_prompt="",
        )
        content, _, _, rendered = await render_npc_speech(
            character=character,
            conversation_context=case["context"],
            user_input=case["input"],
            reasoning=case["draft"],
            draft=case["draft"],
            npc_llm=resolved,
            active_plan_text=case["responsibility"],
            validated_intent=case["intent"],
        )
        rows.append({
            "case": case["name"],
            "content": content,
            "rendered": rendered,
            "rejection_reason": speech_rejection_reason(
                content,
                public_context=f"{case['context']}\n{case['input']}",
                validated_intent=case["intent"],
            ) if content else "silent_recovery",
        })
    result = {
        "protocol": "roommind-g3.6-configured-model-probe-v1",
        "evidence_use": "engineering_prequalification_only",
        "provider": "ollama",
        "model": model,
        "cases": rows,
        "all_public_outputs_safe": all(
            row["content"] and row["rejection_reason"] is None for row in rows
        ),
    }
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt-oss:120b")
    parser.add_argument(
        "--output", type=Path,
        default=Path("/tmp/roommind-g3.6-real-model-probe.json"),
    )
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.model, args.output)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
