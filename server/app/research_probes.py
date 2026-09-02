"""Deterministic integrity probes for archived simulation sessions.

These checks are objective implementation invariants, not human realism scores.
They are included in forensic exports so failures remain visible during
architecture exploration.
"""

from __future__ import annotations

from typing import Any

from app.agent.speech_safety import unsupported_evidence_reason
from app.research_protocol import transcript_provenance


def run_integrity_probes(full_bundle: dict[str, Any]) -> dict[str, Any]:
    messages = [
        row for row in (full_bundle.get("messages") or [])
        if row.get("speaker_type") in {"user", "npc"}
    ]
    sequence = [int(row.get("sequence_no") or 0) for row in messages]
    directory = full_bundle.get("speaker_directory") or {}
    unknown_speakers = sorted({
        str(row.get("speaker_id") or "") for row in messages
        if str(row.get("speaker_id") or "") not in directory
    })
    empty_messages = [
        int(row.get("sequence_no") or 0) for row in messages
        if not str(row.get("content") or "").strip()
    ]
    player_counts: dict[int, int] = {}
    for row in messages:
        if row.get("speaker_type") == "user":
            turn = int(row.get("turn_id") or 0)
            player_counts[turn] = player_counts.get(turn, 0) + 1
    duplicate_player_turns = sorted(turn for turn, count in player_counts.items() if count > 1)
    run_config = (full_bundle.get("session") or {}).get("run_config") or {}
    session_mode = (full_bundle.get("session") or {}).get("session_mode")
    memories = full_bundle.get("agent_memories") or {}
    npc_ids = sorted(
        speaker_id for speaker_id, row in directory.items() if row.get("role") == "npc"
    )
    missing_memory_partitions = [
        speaker_id for speaker_id in npc_ids
        if session_mode == "test" and speaker_id not in memories
    ]
    manifest = run_config.get("research_manifest") or {}
    architecture_version = str(
        manifest.get("architecture_version")
        or run_config.get("architecture_version")
        or ""
    )
    is_g2_roommind = (
        session_mode == "test"
        and architecture_version.startswith(("g2-", "g2."))
    )
    is_g22_roommind = session_mode == "test" and architecture_version.startswith("g2.2")
    coordination_history = (full_bundle.get("task_result") or {}).get("coordination_history") or []
    coordination_turns = [
        int(row.get("turn_id") or 0) for row in coordination_history if isinstance(row, dict)
    ]
    unknown_focus_owners = sorted({
        str(owner)
        for row in coordination_history if isinstance(row, dict)
        for owner in (((row.get("focus") or {}).get("owner_ids") or []))
        if ("user" if str(owner) == "player" else str(owner)) not in directory
    })
    work_items = (full_bundle.get("task_result") or {}).get("work_items") or {}
    noncritical_focus_issue_set: set[str] = set()
    for row in coordination_history:
        focus = row.get("focus") if isinstance(row, dict) else None
        if not isinstance(focus, dict) or focus.get("kind") != "work_item":
            continue
        issue = str(focus.get("issue") or "")
        item = work_items.get(issue.removeprefix("work:")) or {}
        if item.get("required") is not True or not item.get("criticality_reason"):
            noncritical_focus_issue_set.add(issue)
    noncritical_focus_issues = sorted(noncritical_focus_issue_set)
    unsupported_public_evidence: list[dict[str, Any]] = []
    prior_public_context = ""
    for row in sorted(messages, key=lambda item: int(item.get("sequence_no") or 0)):
        reason = unsupported_evidence_reason(
            str(row.get("content") or ""), public_context=prior_public_context
        )
        if reason:
            unsupported_public_evidence.append({
                "sequence_no": int(row.get("sequence_no") or 0),
                "speaker_id": str(row.get("speaker_id") or ""),
                "reason": reason,
            })
        prior_public_context = f"{prior_public_context}\n{row.get('content') or ''}"[-12000:]
    checks = {
        "public_transcript_nonempty": bool(messages),
        "sequence_numbers_unique": len(sequence) == len(set(sequence)),
        "sequence_numbers_strictly_increasing": sequence == sorted(sequence),
        "all_public_speakers_registered": not unknown_speakers,
        "all_public_messages_have_content": not empty_messages,
        "at_most_one_player_message_per_turn": not duplicate_player_turns,
        "comparison_model_lock_present": (
            bool(run_config.get("comparison_lock_model"))
            if session_mode in {"test", "baseline"} and run_config.get("comparison_protocol")
            else None
        ),
        "roommind_agent_memory_partitions_present": (
            not missing_memory_partitions if session_mode == "test" else None
        ),
        "g2_coordination_history_present": (
            bool(coordination_history) if is_g2_roommind else None
        ),
        "g2_coordination_turns_unique_and_increasing": (
            coordination_turns == sorted(set(coordination_turns)) if is_g2_roommind else None
        ),
        "g2_focus_owners_registered": (
            not unknown_focus_owners if is_g2_roommind else None
        ),
        "g22_public_evidence_grounded": (
            not unsupported_public_evidence if is_g22_roommind else None
        ),
        "g22_work_focuses_task_critical": (
            not noncritical_focus_issues if is_g22_roommind else None
        ),
    }
    applicable = [value for value in checks.values() if value is not None]
    return {
        "protocol": "roommind-deterministic-integrity-probes-v2",
        "scope": "implementation_integrity_not_realism",
        "all_applicable_passed": all(applicable),
        "checks": checks,
        "diagnostics": {
            "unknown_speakers": unknown_speakers,
            "empty_message_sequence_nos": empty_messages,
            "duplicate_player_turn_ids": duplicate_player_turns,
            "missing_roommind_memory_partitions": missing_memory_partitions,
            "unknown_g2_focus_owners": unknown_focus_owners,
            "unsupported_public_evidence": unsupported_public_evidence,
            "noncritical_focus_issues": noncritical_focus_issues,
        },
        "transcript_provenance": transcript_provenance(full_bundle),
    }
