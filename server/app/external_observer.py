"""System-independent measurements derived only from the public transcript."""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from typing import Any

from app.research_protocol import (
    HUMAN_REVIEW_PROTOCOL_VERSION,
    REALISM_RUBRIC,
    public_transcript_rows,
    transcript_provenance,
)


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().casefold())


def _duration_seconds(start: Any, end: Any) -> float | None:
    try:
        left = datetime.fromisoformat(str(start))
        right = datetime.fromisoformat(str(end))
        return max(0.0, (right - left).total_seconds())
    except (TypeError, ValueError):
        return None


def build_external_observation(bundle: dict[str, Any]) -> dict[str, Any]:
    """Calculate condition-neutral metrics without reading internal task state."""
    messages = [row for row in (bundle.get("messages") or []) if isinstance(row, dict)]
    public = [row for row in messages if row.get("speaker_type") in {"user", "npc"}]
    npc = [row for row in public if row.get("speaker_type") == "npc"]
    players = [row for row in public if row.get("speaker_type") == "user"]
    directory = bundle.get("speaker_directory") or {}
    expected_npcs = [speaker_id for speaker_id, row in directory.items() if row.get("role") == "npc"]
    speaker_counts = Counter(str(row.get("speaker_id") or "unknown") for row in public)
    npc_counts = Counter(str(row.get("speaker_id") or "unknown") for row in npc)

    active_npcs = sum(1 for speaker_id in expected_npcs if npc_counts.get(speaker_id, 0) > 0)
    participation_rate = active_npcs / len(expected_npcs) if expected_npcs else None
    if npc and len(expected_npcs) > 1:
        probabilities = [count / len(npc) for count in npc_counts.values() if count]
        entropy = -sum(value * math.log(value) for value in probabilities)
        normalized_entropy = entropy / math.log(len(expected_npcs))
    elif npc and len(expected_npcs) == 1:
        normalized_entropy = 1.0
    else:
        normalized_entropy = None

    seen: Counter[str] = Counter()
    duplicate_ids: list[int] = []
    for row in public:
        text = _normalized(str(row.get("content") or ""))
        if not text:
            continue
        seen[text] += 1
        if seen[text] > 1:
            duplicate_ids.append(int(row.get("sequence_no") or 0))

    session = bundle.get("session") or {}
    baseline_state = bundle.get("baseline_result") or {}
    system_claim = {
        "status": session.get("status"),
        "declared_complete": baseline_state.get("declared_complete")
        if baseline_state
        else session.get("status") == "completed",
        "declared_phase": baseline_state.get("declared_phase")
        if baseline_state
        else session.get("current_phase"),
    }
    return {
        "protocol": "public-transcript-observer-v1",
        "independence": (
            "Computed from public messages, speaker metadata, timestamps, and the system's "
            "own completion claim; internal task state, private memory, and reasoning are excluded."
        ),
        "descriptive_metrics": {
            "player_turns": len(players),
            "public_message_count": len(public),
            "npc_message_count": len(npc),
            "speaker_message_counts": dict(sorted(speaker_counts.items())),
            "npc_participation_rate": participation_rate,
            "npc_participation_entropy_normalized": normalized_entropy,
            "exact_repetition_count": len(duplicate_ids),
            "exact_repetition_rate": len(duplicate_ids) / len(public) if public else 0.0,
            "exact_repetition_sequence_nos": duplicate_ids,
            "duration_seconds": _duration_seconds(session.get("created_at"), session.get("updated_at")),
        },
        "system_claim": system_claim,
        "requires_blinded_semantic_evaluation": [
            "externally_validated_completion",
            "premature_completion",
            "authority_violation_rate",
            "responsible_confirmer_rate",
            "agreement_retention_rate",
            "cross_role_knowledge_contamination_rate",
            "protected_secret_leakage_rate",
            "responsibility_match_rate",
            "semantic_repetition_rate",
            "distinct_contribution_rate",
        ],
    }


def build_blinded_evaluation_packet(bundle: dict[str, Any]) -> dict[str, Any]:
    """Prepare a condition-hidden packet for an external human or AI judge."""
    scenario = bundle.get("scenario") or {}
    directory = bundle.get("speaker_directory") or {}
    transcript = public_transcript_rows(bundle)
    provenance = transcript_provenance(bundle)
    # The source session id remains server-side so reviewers cannot correlate
    # an anonymous packet with condition-bearing debug/session URLs.
    public_provenance = {
        key: value for key, value in provenance.items() if key != "session_uuid"
    }
    npc_ids = [speaker_id for speaker_id, row in directory.items() if row.get("role") == "npc"]
    aliases = {speaker_id: f"Participant {chr(65 + index)}" for index, speaker_id in enumerate(sorted(npc_ids))}
    for row in transcript:
        if row.get("speaker_type") == "user":
            aliases[str(row.get("speaker_id") or "user")] = "Player"
    visible = [
        {**row, "speaker_label": aliases.get(str(row.get("speaker_id")), "Participant")}
        for row in transcript
    ]
    return {
        "evaluation_protocol": HUMAN_REVIEW_PROTOCOL_VERSION,
        "run_label": "anonymous",
        "condition_hidden": True,
        "language_policy": {
            "interface": ["zh-CN", "en"],
            "transcript": "original_verbatim",
            "notice_en": "The dialogue below is the exact stored transcript; it is not translated or regenerated.",
            "notice_zh": "以下对话为系统当时保存的原始逐字记录，未翻译、未重写、未重新生成。",
        },
        "source_provenance": public_provenance,
        "gold_specification": {
            "scenario_id": scenario.get("id"),
            "scenario_slug": scenario.get("slug"),
            "title": scenario.get("title"),
            "task_config": scenario.get("task_config") or {},
            "role_authority": {
                speaker_id: {
                    "job_title": row.get("job_title"),
                    "interaction_role": row.get("interaction_role"),
                    "authority": row.get("authority") or {},
                }
                for speaker_id, row in directory.items()
                if row.get("role") == "npc"
            },
        },
        "speaker_aliases": aliases,
        "fixed_window_transcript": [row for row in visible if int(row.get("turn_id") or 0) <= 20],
        "public_transcript": visible,
        "system_claim": (bundle.get("external_observation") or {}).get("system_claim") or {},
        "rubric": REALISM_RUBRIC,
        "human_rating_form": {
            "scale": "1-7",
            "role_strategic_fidelity": None,
            "epistemic_fidelity": None,
            "temporal_coherence": None,
            "interaction_structure_fidelity": None,
            "multi_party_dynamics_fidelity": None,
            "procedural_fidelity": None,
            "overall_believability": None,
            "reviewer_id": "",
            "notes": "",
        },
    }
