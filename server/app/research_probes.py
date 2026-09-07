"""Deterministic integrity probes for archived simulation sessions.

These checks are objective implementation invariants, not human realism scores.
They are included in forensic exports so failures remain visible during
architecture exploration.
"""

from __future__ import annotations

import re
from typing import Any

from app.agent.speech_safety import (
    focus_question_target_mismatch_reason,
    near_duplicate_obligation_utterance,
    near_duplicate_public_utterance,
    npc_directed_question_handoff_reason,
    resolve_direct_question_target,
    resolve_direct_question_targets,
    retrospective_role_substitution_reason,
    speech_rejection_reason,
    terminal_current_world_action_reason,
    unregistered_participant_assignment_reason,
    unsupported_evidence_reason,
)
from app.research_protocol import transcript_provenance
from app.player_agent import is_minimal_player_floor_handoff


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
    generation_id = str(manifest.get("generation_id") or run_config.get("generation_id") or "")
    architecture_version = str(
        manifest.get("architecture_version")
        or run_config.get("architecture_version")
        or ""
    )
    is_g2_roommind = (
        session_mode == "test"
        and architecture_version.startswith(("g2-", "g2.", "g3", "g4"))
    )
    is_g22_roommind = session_mode == "test" and architecture_version.startswith(("g2.2", "g2.3", "g3", "g4"))
    is_g23_roommind = session_mode == "test" and architecture_version.startswith(("g2.3", "g3", "g4"))
    is_g3_roommind = session_mode == "test" and architecture_version.startswith(("g3", "g4"))
    is_g37_roommind = session_mode == "test" and architecture_version.startswith(("g3.7", "g3.8", "g3.9", "g4"))
    is_g38_roommind = session_mode == "test" and architecture_version.startswith(("g3.8", "g3.9", "g4"))
    is_g39_roommind = session_mode == "test" and architecture_version.startswith(("g3.9", "g4"))
    is_g4_roommind = session_mode == "test" and architecture_version.startswith("g4")
    is_g41_roommind = session_mode == "test" and architecture_version.startswith(("g4.1", "g4.2", "g4.3", "g4.4", "g4.5", "g4.6", "g4.7", "g4.8", "g4.9", "g4.10", "g4.11"))
    is_g42_roommind = session_mode == "test" and architecture_version.startswith(("g4.2", "g4.3", "g4.4", "g4.5", "g4.6", "g4.7", "g4.8", "g4.9", "g4.10", "g4.11", "g4.12"))
    is_g43_roommind = session_mode == "test" and architecture_version.startswith(("g4.3", "g4.4", "g4.5", "g4.6", "g4.7", "g4.8", "g4.9", "g4.10", "g4.11", "g4.12"))
    is_g44_roommind = session_mode == "test" and architecture_version.startswith(("g4.4", "g4.5", "g4.6", "g4.7", "g4.8", "g4.9", "g4.10", "g4.11", "g4.12"))
    is_g45_roommind = session_mode == "test" and architecture_version.startswith(("g4.5", "g4.6", "g4.7", "g4.8", "g4.9", "g4.10", "g4.11", "g4.12"))
    is_g47_roommind = session_mode == "test" and architecture_version.startswith(("g4.7", "g4.8", "g4.9", "g4.10", "g4.11", "g4.12"))
    is_g48_roommind = session_mode == "test" and architecture_version.startswith(("g4.8", "g4.9", "g4.10", "g4.11", "g4.12"))
    is_g49_roommind = session_mode == "test" and architecture_version.startswith(("g4.9", "g4.10", "g4.11", "g4.12"))
    is_g410_roommind = session_mode == "test" and architecture_version.startswith(("g4.10", "g4.11", "g4.12"))
    is_g411_roommind = session_mode == "test" and architecture_version.startswith(("g4.11", "g4.12"))
    is_g412_roommind = session_mode == "test" and architecture_version.startswith("g4.12")
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
    excessive_focus_streaks = [
        {
            "turn_id": int(row.get("turn_id") or 0),
            "issue": str((row.get("focus") or {}).get("issue") or ""),
            "focus_streak": int((row.get("focus") or {}).get("focus_streak") or 0),
        }
        for row in coordination_history if isinstance(row, dict)
        and isinstance(row.get("focus"), dict)
        and (row.get("focus") or {}).get("kind") != "outcome_resolution"
        and int((row.get("focus") or {}).get("focus_streak") or 0) > 2
    ]
    invalid_outcome_resolution = [
        int(row.get("turn_id") or 0)
        for row in coordination_history if isinstance(row, dict)
        and isinstance(row.get("focus"), dict)
        and (row.get("focus") or {}).get("kind") == "outcome_resolution"
        and not str((row.get("focus") or {}).get("origin_focus_issue") or "")
    ]
    unsupported_public_evidence: list[dict[str, Any]] = []
    task_config = ((full_bundle.get("scenario") or {}).get("task_config") or {})
    task_type = str(task_config.get("task_type") or "")
    evidence_mode = str(task_config.get("evidence_mode") or (
        "retrospective_claim" if task_type == "structured_interview" else "live_operation"
    ))
    retrospective_scenario = evidence_mode == "retrospective_claim"
    prior_public_context = ""
    for row in sorted(messages, key=lambda item: int(item.get("sequence_no") or 0)):
        reason = unsupported_evidence_reason(
            str(row.get("content") or ""), public_context=prior_public_context,
            allow_retrospective_artifact_claims=retrospective_scenario,
        )
        if reason:
            unsupported_public_evidence.append({
                "sequence_no": int(row.get("sequence_no") or 0),
                "speaker_id": str(row.get("speaker_id") or ""),
                "reason": reason,
            })
        prior_public_context = f"{prior_public_context}\n{row.get('content') or ''}"[-12000:]
    task_result = full_bundle.get("task_result") or {}
    public_ledger = task_result.get("public_ledger") or {}
    ledger_events = public_ledger.get("recent_events") or []
    ledger_entities = public_ledger.get("entities") or {}
    ledger_tool_results = public_ledger.get("tool_results") or {}
    invalid_ledger_events = [
        str(row.get("event_id") or "") for row in ledger_events
        if not isinstance(row, dict)
        or not row.get("event_id")
        or row.get("provenance") not in {
            "scenario_seed", "public_statement", "simulated_tool_result", "external_followup",
        }
        or not str((row.get("public_evidence") or {}).get("quote") or "").strip()
    ]
    unsupported_terminal_ledger_events = [
        str(row.get("event_id") or "") for row in ledger_events
        if isinstance(row, dict)
        and row.get("entity_kind") in {"artifact", "action", "verification"}
        and row.get("transition_to") in {"submitted", "verified", "accepted"}
        and not str(row.get("inline_content") or "").strip()
    ]
    unsupported_completed_action_sources = [
        str(row.get("event_id") or "") for row in ledger_events
        if isinstance(row, dict)
        and row.get("entity_kind") == "action"
        and row.get("transition_to") in {"submitted", "verified", "accepted"}
        and (
            row.get("provenance") != "simulated_tool_result"
            or not str(row.get("tool_result_id") or "").strip()
            or str(row.get("tool_result_id") or "") not in ledger_tool_results
        )
    ]
    tool_grounded_quotes = {
        " ".join(str((row.get("public_evidence") or {}).get("quote") or "").split())
        for row in ledger_events
        if isinstance(row, dict)
        and row.get("provenance") == "simulated_tool_result"
        and str(row.get("tool_result_id") or "") in ledger_tool_results
    }
    public_content_by_sequence = {
        int(row.get("sequence_no") or 0):
        " ".join(str(row.get("content") or "").split())
        for row in messages
    }
    ungrounded_live_artifact_receipts = [
        row for row in unsupported_public_evidence
        if public_content_by_sequence.get(int(row.get("sequence_no") or 0), "")
        not in tool_grounded_quotes
    ]
    unsupported_visible_current_world_actions = []
    for row in messages:
        content = " ".join(str(row.get("content") or "").split())
        grounded = content in tool_grounded_quotes
        reason = terminal_current_world_action_reason(
            content,
            validated_intent=(
                {
                    "simulation_scope": "in_session",
                    "evidence_source": "simulated_tool_result",
                    "tool_result_id": "registered",
                    "validation": "accepted",
                    "transition": "verified",
                }
                if grounded else
                {
                    "simulation_scope": "discussion",
                    "evidence_source": "public_statement",
                    "validation": "accepted",
                    "transition": "proposed",
                }
            ),
        )
        if reason:
            unsupported_visible_current_world_actions.append({
                "sequence_no": int(row.get("sequence_no") or 0),
                "speaker_id": str(row.get("speaker_id") or ""),
                "reason": reason,
            })
    clock = public_ledger.get("simulation_clock") or {}
    clock_turn = int(clock.get("turn") or 0)
    future_ledger_events = [
        str(row.get("event_id") or "") for row in ledger_events
        if isinstance(row, dict) and (
            int(row.get("turn_id") or 0) > clock_turn
            or row.get("clock_valid") is False
        )
    ]
    ledger_clock_sequence = [
        (int(row.get("turn_id") or 0), int(row.get("tick") or 0))
        for row in ledger_events if isinstance(row, dict)
    ]
    duplicate_ledger_event_ids = sorted({
        str(row.get("event_id") or "") for row in ledger_events
        if sum(1 for candidate in ledger_events if isinstance(candidate, dict)
               and candidate.get("event_id") == row.get("event_id")) > 1
    })
    invalid_entity_lifecycle = sorted(
        str(entity_id) for entity_id, entity in ledger_entities.items()
        if not isinstance(entity, dict) or entity.get("lifecycle") not in {
            "proposed", "committed", "in_progress", "submitted", "verified",
            "accepted", "rejected", "blocked",
        }
    )
    completion_status = str(task_result.get("completion_status") or "")
    same_speaker_near_duplicates: list[dict[str, Any]] = []
    prior_by_speaker: dict[str, list[str]] = {}
    for row in sorted(messages, key=lambda item: int(item.get("sequence_no") or 0)):
        speaker_id = str(row.get("speaker_id") or "")
        content = str(row.get("content") or "")
        prior = prior_by_speaker.setdefault(speaker_id, [])
        if near_duplicate_public_utterance(content, prior):
            same_speaker_near_duplicates.append({
                "sequence_no": int(row.get("sequence_no") or 0),
                "speaker_id": speaker_id,
            })
        prior.append(content)
    focus_by_turn = {
        int(row.get("turn_id") or 0): (row.get("focus") or {})
        for row in coordination_history if isinstance(row, dict)
    }
    cross_role_obligation_duplicates: list[dict[str, Any]] = []
    prior_public_rows: list[dict[str, str]] = []
    for row in sorted(messages, key=lambda item: int(item.get("sequence_no") or 0)):
        if str(row.get("speaker_type") or "") not in {"npc", "user"}:
            continue
        speaker_id = str(row.get("speaker_id") or "")
        content = str(row.get("content") or "")
        focus = focus_by_turn.get(int(row.get("turn_id") or 0)) or {}
        if row.get("speaker_type") == "npc" and near_duplicate_obligation_utterance(
            content, prior_public_rows, speaker_id=speaker_id, focus=focus,
            public_intent=((row.get("meta") or {}).get("public_intent") or {}),
        ):
            cross_role_obligation_duplicates.append({
                "sequence_no": int(row.get("sequence_no") or 0),
                "speaker_id": speaker_id,
                "obligation_id": str(focus.get("obligation_id") or ""),
            })
        prior_public_rows.append({
            "speaker_id": speaker_id, "content": content,
            "obligation_id": str(focus.get("obligation_id") or ""),
        })
    npc_labels = [
        label
        for speaker_id, speaker in directory.items()
        if speaker_id != "user" and isinstance(speaker, dict)
        for label in (
            speaker.get("display_name"), speaker.get("character_name"),
            speaker.get("job_title"), *((speaker.get("aliases") or [])),
        )
        if label
    ]
    player_row = directory.get("user") or {}
    player_labels = [
        label for label in (
            player_row.get("display_name"), player_row.get("character_name"),
            player_row.get("job_title"), *((player_row.get("aliases") or [])),
        ) if label
    ]
    participant_aliases = {
        str(speaker_id): [
            str(label) for label in (
                speaker.get("display_name"), speaker.get("character_name"),
                speaker.get("job_title"), *((speaker.get("aliases") or [])),
            ) if label
        ]
        for speaker_id, speaker in directory.items()
        if isinstance(speaker, dict)
    }
    ordered_messages = sorted(messages, key=lambda item: int(item.get("sequence_no") or 0))
    player_response_lock_violations: list[dict[str, Any]] = []
    for index, row in enumerate(ordered_messages):
        if row.get("speaker_type") != "user":
            continue
        targets = [
            target for target in resolve_direct_question_targets(
                str(row.get("content") or ""),
                public_intent=((row.get("meta") or {}).get("public_intent") or {}),
                participant_aliases=participant_aliases,
            )
            if target not in {"", "user"}
        ]
        if not targets:
            continue
        following_npcs: list[str] = []
        remaining_targets = list(targets)
        unexpected: list[str] = []
        for candidate in ordered_messages[index + 1:]:
            if candidate.get("speaker_type") == "user":
                break
            if candidate.get("speaker_type") == "npc":
                speaker_id = str(candidate.get("speaker_id") or "")
                following_npcs.append(speaker_id)
                if remaining_targets and speaker_id == remaining_targets[0]:
                    remaining_targets.pop(0)
                    if not remaining_targets:
                        break
                elif remaining_targets:
                    unexpected.append(speaker_id)
        if remaining_targets or unexpected:
            player_response_lock_violations.append({
                "sequence_no": int(row.get("sequence_no") or 0),
                "target_ids": targets,
                "following_npc_ids": following_npcs,
                "missing_target_ids": remaining_targets,
                "unexpected_speaker_ids": unexpected,
            })
    multi_addressee_response_violations: list[dict[str, Any]] = []
    for index, row in enumerate(ordered_messages):
        if row.get("speaker_type") != "user":
            continue
        targets = [
            target for target in resolve_direct_question_targets(
                str(row.get("content") or ""),
                public_intent=((row.get("meta") or {}).get("public_intent") or {}),
                participant_aliases=participant_aliases,
            )
            if target not in {"", "user"}
        ]
        if len(targets) < 2:
            continue
        following: list[dict[str, Any]] = []
        for candidate in ordered_messages[index + 1:]:
            if (
                candidate.get("speaker_type") == "user"
                and not is_minimal_player_floor_handoff(
                    str(candidate.get("content") or "")
                )
            ):
                break
            following.append(candidate)
        answered = {str(candidate.get("speaker_id") or "") for candidate in following}
        missing = [target for target in targets if target not in answered]
        if missing:
            multi_addressee_response_violations.append({
                "sequence_no": int(row.get("sequence_no") or 0),
                "target_ids": targets,
                "missing_target_ids": missing,
            })
    routing_prompt_violations = [
        {
            "sequence_no": int(row.get("sequence_no") or 0),
            "content": str(row.get("content") or ""),
        }
        for row in ordered_messages
        if row.get("speaker_type") == "user"
        and "please answer the question directly from your area" in str(
            row.get("content") or ""
        ).casefold()
    ]
    retrospective_authorship_violations = [
        {
            "sequence_no": int(row.get("sequence_no") or 0),
            "speaker_id": str(row.get("speaker_id") or ""),
            "reason": reason,
        }
        for row in ordered_messages
        if row.get("speaker_type") == "npc"
        for reason in [retrospective_role_substitution_reason(
            str(row.get("content") or ""),
            speaker_id=str(row.get("speaker_id") or ""),
            participant_aliases=participant_aliases,
            validated_intent=((row.get("meta") or {}).get("public_intent") or {}),
            interview_mode=retrospective_scenario,
        )]
        if reason
    ]
    conditional_acceptance_events = [
        {
            "event_id": str(event.get("event_id") or ""),
            "field": str(event.get("field") or ""),
            "turn_id": int(event.get("turn_id") or 0),
        }
        for event in ledger_events
        if isinstance(event, dict)
        and str(event.get("transition_to") or "") in {"accepted", "verified"}
        and re.search(
            r"\b(?:conditionally|subject\s+to|provided(?:\s+that)?|assuming|pending|"
            r"awaiting|unless|until|before\s+(?:i|we)\s+(?:can|will)|cannot|can't|"
            r"not\s+(?:yet\s+)?(?:confirm|accept|approve|agree|ready))\b",
            str((event.get("public_evidence") or {}).get("quote") or ""),
            flags=re.IGNORECASE,
        )
    ]
    post_terminal_confirmation_speech: list[dict[str, Any]] = []
    completion_fields = {
        str(condition.get("field") or "")
        for condition in [
            *(((full_bundle.get("scenario") or {}).get("task_config") or {}).get(
                "completion_conditions", {}
            ).get("all", [])),
            *(((full_bundle.get("scenario") or {}).get("task_config") or {}).get(
                "completion_conditions", {}
            ).get("any", [])),
        ]
        if isinstance(condition, dict) and condition.get("field")
    }
    accepted_completion_events = [
        event for event in ledger_events
        if isinstance(event, dict)
        and str(event.get("transition_to") or "") == "accepted"
        and str(event.get("field") or "") in completion_fields
    ]
    if completion_status == "completed" and accepted_completion_events:
        final_event = max(
            accepted_completion_events,
            key=lambda event: (int(event.get("turn_id") or 0), int(event.get("tick") or 0)),
        )
        final_turn = int(final_event.get("turn_id") or 0)
        actor_id = str(final_event.get("actor_id") or "")
        actor_rows = [
            (index, row) for index, row in enumerate(ordered_messages)
            if int(row.get("turn_id") or 0) == final_turn
            and str(row.get("speaker_id") or "") == actor_id
        ]
        if actor_rows:
            final_index = actor_rows[-1][0]
            post_terminal_confirmation_speech = [
                {
                    "sequence_no": int(row.get("sequence_no") or 0),
                    "speaker_id": str(row.get("speaker_id") or ""),
                    "terminal_event_id": str(final_event.get("event_id") or ""),
                }
                for row in ordered_messages[final_index + 1:]
                if int(row.get("turn_id") or 0) == final_turn
                and row.get("speaker_type") == "npc"
            ]
    unregistered_public_assignments = [
        {
            "sequence_no": int(row.get("sequence_no") or 0),
            "speaker_id": str(row.get("speaker_id") or ""),
            "reason": reason,
        }
        for row in messages
        for reason in [unregistered_participant_assignment_reason(
            str(row.get("content") or ""),
            participant_aliases=participant_aliases,
            validated_intent=((row.get("meta") or {}).get("public_intent") or {}),
        )]
        if reason
    ]
    player_floor_violations: list[dict[str, Any]] = []
    question_target_mismatches: list[dict[str, Any]] = []
    cross_role_question_violations: list[dict[str, Any]] = []
    direct_response_violations: list[dict[str, Any]] = []
    rows_by_turn: dict[int, list[dict[str, Any]]] = {}
    for row in sorted(messages, key=lambda item: int(item.get("sequence_no") or 0)):
        rows_by_turn.setdefault(int(row.get("turn_id") or 0), []).append(row)
    for turn_id, rows in rows_by_turn.items():
        handoff_sequence = 0
        for row in rows:
            if row.get("speaker_type") != "npc":
                continue
            if handoff_sequence:
                player_floor_violations.append({
                    "turn_id": turn_id,
                    "question_sequence_no": handoff_sequence,
                    "following_sequence_no": int(row.get("sequence_no") or 0),
                    "following_speaker_id": str(row.get("speaker_id") or ""),
                })
                continue
            intent = ((row.get("meta") or {}).get("public_intent") or {})
            resolved_target = resolve_direct_question_target(
                str(row.get("content") or ""),
                public_intent=intent,
                npc_labels=[str(label) for label in npc_labels],
                player_labels=[str(label) for label in player_labels],
                participant_aliases=participant_aliases,
            )
            structured_target = str(intent.get("target_id") or "")
            if (
                structured_target
                and resolved_target
                and structured_target not in {resolved_target, "player" if resolved_target == "user" else resolved_target}
            ):
                question_target_mismatches.append({
                    "turn_id": turn_id,
                    "sequence_no": int(row.get("sequence_no") or 0),
                    "structured_target_id": structured_target,
                    "resolved_target_id": resolved_target,
                })
            if resolved_target == "user":
                handoff_sequence = int(row.get("sequence_no") or 0)
    for index, row in enumerate(ordered_messages):
        if row.get("speaker_type") != "npc":
            continue
        source_id = str(row.get("speaker_id") or "")
        intent = ((row.get("meta") or {}).get("public_intent") or {})
        target_id = resolve_direct_question_target(
            str(row.get("content") or ""),
            public_intent=intent,
            npc_labels=[str(label) for label in npc_labels],
            player_labels=[str(label) for label in player_labels],
            participant_aliases=participant_aliases,
        )
        if not target_id or target_id in {"user", source_id}:
            continue
        for following in ordered_messages[index + 1:]:
            following_id = str(following.get("speaker_id") or "")
            if following_id == target_id:
                break
            if following.get("speaker_type") != "user":
                continue
            following_intent = ((following.get("meta") or {}).get("public_intent") or {})
            reason = npc_directed_question_handoff_reason(
                str(following.get("content") or ""),
                target_id=target_id,
                public_intent=following_intent,
                participant_aliases=participant_aliases,
            )
            if reason:
                cross_role_question_violations.append({
                    "question_sequence_no": int(row.get("sequence_no") or 0),
                    "question_speaker_id": source_id,
                    "target_id": target_id,
                    "player_sequence_no": int(following.get("sequence_no") or 0),
                    "reason": reason,
                })
            break
        following = ordered_messages[index + 1] if index + 1 < len(ordered_messages) else None
        if (
            following is None
            or int(following.get("turn_id") or 0) != int(row.get("turn_id") or 0)
            or str(following.get("speaker_id") or "") != target_id
        ):
            direct_response_violations.append({
                "question_sequence_no": int(row.get("sequence_no") or 0),
                "question_speaker_id": source_id,
                "target_id": target_id,
                "following_sequence_no": (
                    int(following.get("sequence_no") or 0) if following else None
                ),
                "following_speaker_id": (
                    str(following.get("speaker_id") or "") if following else ""
                ),
            })
    rejected_transition_surface_violations = [
        {
            "sequence_no": int(row.get("sequence_no") or 0),
            "speaker_id": str(row.get("speaker_id") or ""),
            "validation_reason": str(intent.get("validation_reason") or ""),
        }
        for row in ordered_messages
        if row.get("speaker_type") == "npc"
        for intent in [((row.get("meta") or {}).get("public_intent") or {})]
        if intent.get("commit_allowed") is False
        and speech_rejection_reason(
            str(row.get("content") or ""), validated_intent=intent,
            participant_aliases=participant_aliases,
        ) == "speech_exceeds_validated_lifecycle"
    ]
    focus_target_authority_violations: list[dict[str, Any]] = []
    bounded_handoff_violations: list[dict[str, Any]] = []
    bounded_handoffs_by_target: dict[str, int] = {}
    for row in ordered_messages:
        meta = row.get("meta") or {}
        public_intent = meta.get("public_intent") or {}
        if row.get("speaker_type") == "npc":
            focus = focus_by_turn.get(int(row.get("turn_id") or 0)) or {}
            reason = focus_question_target_mismatch_reason(
                str(row.get("content") or ""),
                speaker_id=str(row.get("speaker_id") or ""),
                focus=focus,
                public_intent=public_intent,
                participant_aliases=participant_aliases,
            )
            if reason:
                focus_target_authority_violations.append({
                    "sequence_no": int(row.get("sequence_no") or 0),
                    "speaker_id": str(row.get("speaker_id") or ""),
                    "target_id": str(public_intent.get("target_id") or ""),
                    "reason": reason,
                })
        if (
            row.get("speaker_type") == "user"
            and str(meta.get("intent") or "") == "bounded_cross_role_handoff"
        ):
            target_id = str(public_intent.get("target_id") or "")
            bounded_handoffs_by_target[target_id] = (
                bounded_handoffs_by_target.get(target_id, 0) + 1
            )
            if not target_id or meta.get("requested_end") is not True:
                bounded_handoff_violations.append({
                    "sequence_no": int(row.get("sequence_no") or 0),
                    "target_id": target_id,
                    "reason": "bounded_handoff_missing_target_or_stop_request",
                })
    bounded_handoff_violations.extend({
        "sequence_no": 0,
        "target_id": target_id,
        "reason": "bounded_handoff_repeated",
    } for target_id, count in bounded_handoffs_by_target.items() if count > 1)
    malformed_public_fragments = [
        {
            "sequence_no": int(row.get("sequence_no") or 0),
            "speaker_id": str(row.get("speaker_id") or ""),
        }
        for row in ordered_messages
        if speech_rejection_reason(str(row.get("content") or ""))
        == "malformed_fragment"
    ]
    post_closure_speech: list[dict[str, Any]] = []
    closure_sequence = 0
    for row in ordered_messages:
        meta = row.get("meta") or {}
        if closure_sequence:
            post_closure_speech.append({
                "closure_sequence_no": closure_sequence,
                "sequence_no": int(row.get("sequence_no") or 0),
                "speaker_id": str(row.get("speaker_id") or ""),
            })
        if row.get("speaker_type") == "user" and meta.get("requested_end") is True:
            closure_sequence = int(row.get("sequence_no") or 0)
    capability_boundaries = task_result.get("capability_boundaries") or {}
    capability_focus_issues = [
        str((row.get("focus") or {}).get("issue") or "")
        for row in coordination_history if isinstance(row, dict)
        and (row.get("focus") or {}).get("kind") == "capability_boundary"
    ]
    repeated_capability_focus_issues = sorted({
        issue for issue in capability_focus_issues
        if issue and capability_focus_issues.count(issue) > 1
    })
    outcome = task_result.get("outcome") or {}
    boundary_closure_unmet = {
        str(field) for field in (outcome.get("unmet_conditions") or []) if field
    }
    unavailable_boundary_fields = {
        str(field) for field, row in capability_boundaries.items()
        if isinstance(row, dict) and row.get("status") == "unavailable"
    }
    open_required_work = [
        str(key) for key, item in (task_result.get("work_items") or {}).items()
        if isinstance(item, dict) and item.get("required") is True
        and item.get("status") not in {"submitted", "completed", "rejected"}
    ]
    condition_results = [
        row for row in (task_result.get("condition_results") or [])
        if isinstance(row, dict)
    ]
    field_projection_mismatches: list[str] = []
    task_variables = task_result.get("variables") or {}
    state_schema = task_config.get("state_schema") or {}
    for field, spec in state_schema.items():
        entity = ledger_entities.get(f"field:{field}") or {}
        if not isinstance(entity, dict) or entity.get("lifecycle") != "accepted":
            continue
        accepted_by = {
            "user" if str(actor) == "player" else str(actor)
            for actor in ((entity.get("actors_by_transition") or {}).get("accepted") or [])
        }
        configured = {
            "user" if str(actor) == "player" else str(actor)
            for actor in (spec.get("confirm_permissions") or [])
        }
        authorized_counterparts = {
            str(speaker_id) for speaker_id, speaker in directory.items()
            if str(speaker_id) != "user"
            and field in (((speaker or {}).get("authority") or {}).get("can_confirm") or [])
        } | (configured - {"user"})
        policy = str(spec.get("confirmation_policy") or "responsible_participant")
        policy_satisfied = {
            "player": "user" in accepted_by,
            "responsible_participant": bool(accepted_by & authorized_counterparts),
            "player_and_authorized_counterpart": (
                "user" in accepted_by and bool(accepted_by & authorized_counterparts)
            ),
            "player_and_responsible_participant": (
                "user" in accepted_by and bool(accepted_by & authorized_counterparts)
            ),
            "player_and_assignee": (
                "user" in accepted_by and bool(accepted_by & authorized_counterparts)
            ),
        }.get(policy, False)
        if not policy_satisfied:
            continue
        variable = task_variables.get(field) or {}
        projected_confirmations = {
            "user" if str(actor) == "player" else str(actor)
            for actor in (variable.get("confirmations") or [])
        }
        if (
            variable.get("status") != "confirmed"
            or variable.get("value") != entity.get("value")
            or not accepted_by.issubset(projected_confirmations)
        ):
            field_projection_mismatches.append(str(field))
    obligation_graph = task_result.get("obligation_graph") or {}
    obligations = obligation_graph.get("obligations") or {}
    expected_open_obligations = sorted(
        str(row.get("obligation_id") or key)
        for key, row in obligations.items()
        if isinstance(row, dict) and row.get("required_now") is True
        and row.get("status") != "satisfied"
    )
    recorded_open_obligations = sorted(
        str(value) for value in (obligation_graph.get("open_obligation_ids") or [])
    )
    incapable_obligation_targets: list[dict[str, Any]] = []
    for event in ledger_events:
        if not isinstance(event, dict):
            continue
        if str(event.get("entity_kind") or "") != "handoff":
            continue
        field = str(event.get("field") or "")
        target_id = "user" if str(event.get("target_id") or "") == "player" else str(event.get("target_id") or "")
        if not field or not target_id:
            continue
        matching = [
            row for row in obligations.values()
            if isinstance(row, dict) and str(row.get("field") or "") == field
        ]
        capable = {
            "user" if str(value) == "player" else str(value)
            for obligation in matching
            for value in (obligation.get("authorized_confirmer_ids") or [])
        }
        if capable and target_id not in capable:
            incapable_obligation_targets.append({
                "event_id": str(event.get("event_id") or ""),
                "field": field, "target_id": target_id,
            })
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
        "g23_focus_streak_bounded": (
            not excessive_focus_streaks if is_g23_roommind else None
        ),
        "g23_outcome_resolution_grounded": (
            not invalid_outcome_resolution if is_g23_roommind else None
        ),
        "g3_authoritative_public_ledger_present": (
            public_ledger.get("schema") == "roommind-public-world-ledger-v1"
            if is_g3_roommind else None
        ),
        "g3_ledger_events_have_public_provenance": (
            not invalid_ledger_events if is_g3_roommind else None
        ),
        "g3_terminal_actions_have_inline_evidence": (
            not unsupported_terminal_ledger_events if is_g3_roommind else None
        ),
        "g35_completed_actions_require_tool_results": (
            not unsupported_completed_action_sources
            if is_g3_roommind and generation_id.startswith(("G3.5", "G3.6", "G3.7", "G3.8", "G3.9", "G4")) else None
        ),
        "g36_visible_current_world_actions_require_tool_results": (
            not unsupported_visible_current_world_actions
            if is_g3_roommind and generation_id.startswith(("G3.6", "G3.7", "G3.8", "G3.9", "G4")) else None
        ),
        "g37_capability_boundaries_not_repeated": (
            not repeated_capability_focus_issues if is_g37_roommind else None
        ),
        "g37_capability_boundary_closure_consistent": (
            (
                completion_status == "conditional"
                and bool(boundary_closure_unmet)
                and boundary_closure_unmet.issubset(unavailable_boundary_fields)
            )
            if is_g37_roommind
            and outcome.get("status") == "capability_boundary_reconciled"
            else (True if is_g37_roommind else None)
        ),
        "g38_authoritative_closure_lock_consistent": (
            (
                str(((full_bundle.get("task_result") or {}).get("closure_lock") or {}).get("status") or "")
                == "locked"
                and bool(condition_results)
                and all(
                    bool(row.get("met"))
                    for row in condition_results
                )
                and not open_required_work
            )
            if is_g38_roommind and completion_status == "completed"
            else (True if is_g38_roommind else None)
        ),
        "g39_task_does_not_end_stalled": (
            completion_status != "stalled" if is_g39_roommind else None
        ),
        "g39_completed_task_has_closure_lock": (
            str((task_result.get("closure_lock") or {}).get("status") or "") == "locked"
            if is_g39_roommind and completion_status == "completed"
            else (True if is_g39_roommind else None)
        ),
        "g39_accepted_fields_project_atomically": (
            not field_projection_mismatches if is_g39_roommind else None
        ),
        "g4_same_speaker_near_duplicates_absent": (
            not same_speaker_near_duplicates if is_g4_roommind else None
        ),
        "g4_no_progress_close_is_bounded": (
            (
                completion_status in {"conditional", "deferred"}
                and bool(task_result.get("open_issues") or [])
                and outcome.get("type") == completion_status
            )
            if is_g4_roommind and outcome.get("status") == "governor_bounded_close"
            else (True if is_g4_roommind else None)
        ),
        "g4_task_does_not_end_stalled": (
            completion_status != "stalled" if is_g4_roommind else None
        ),
        "g41_player_floor_handoff_respected": (
            not player_floor_violations if is_g41_roommind else None
        ),
        "g42_structured_question_targets_match_public_speech": (
            not question_target_mismatches if is_g42_roommind else None
        ),
        "g43_cross_role_question_ownership_preserved": (
            not cross_role_question_violations if is_g43_roommind else None
        ),
        "g44_in_session_owners_are_registered": (
            not unregistered_public_assignments if is_g44_roommind else None
        ),
        "g45_obligation_graph_present": (
            obligation_graph.get("schema") == "roommind-meeting-obligation-graph-v1"
            and bool(obligations) if is_g45_roommind else None
        ),
        "g45_open_obligations_reconcile": (
            expected_open_obligations == recorded_open_obligations
            if is_g45_roommind else None
        ),
        "g45_completed_requires_satisfied_obligations": (
            bool(obligation_graph.get("all_required_satisfied"))
            if is_g45_roommind and completion_status == "completed"
            else (True if is_g45_roommind else None)
        ),
        "g45_obligation_targets_authorized": (
            not incapable_obligation_targets if is_g45_roommind else None
        ),
        "g45_cross_role_obligation_repetition_absent": (
            not cross_role_obligation_duplicates if is_g45_roommind else None
        ),
        "g47_focus_question_targets_authorized": (
            not focus_target_authority_violations if is_g47_roommind else None
        ),
        "g47_repeated_player_handoff_is_bounded": (
            not bounded_handoff_violations if is_g47_roommind else None
        ),
        "g48_cross_speaker_issue_repetition_absent": (
            not cross_role_obligation_duplicates if is_g48_roommind else None
        ),
        "g48_public_utterances_well_formed": (
            not malformed_public_fragments if is_g48_roommind else None
        ),
        "g48_no_speech_after_player_closure": (
            not post_closure_speech if is_g48_roommind else None
        ),
        "g48_live_artifact_receipts_grounded": (
            not ungrounded_live_artifact_receipts if is_g48_roommind else None
        ),
        "g49_multi_addressee_responses_preserved": (
            not multi_addressee_response_violations if is_g49_roommind else None
        ),
        "g49_generated_routing_prompts_absent": (
            not routing_prompt_violations if is_g49_roommind else None
        ),
        "g49_retrospective_authorship_preserved": (
            not retrospective_authorship_violations if is_g49_roommind else None
        ),
        "g410_conditional_confirmations_not_committed": (
            not conditional_acceptance_events if is_g410_roommind else None
        ),
        "g410_terminal_confirmation_locks_floor": (
            not post_terminal_confirmation_speech if is_g410_roommind else None
        ),
        "g411_npc_questions_receive_direct_same_turn_response": (
            not direct_response_violations if is_g411_roommind else None
        ),
        "g411_rejected_transitions_not_reintroduced_in_speech": (
            not rejected_transition_surface_violations if is_g411_roommind else None
        ),
        "g412_player_addressed_response_lock_respected": (
            not player_response_lock_violations if is_g412_roommind else None
        ),
        "g3_simulation_clock_monotonic": (
            not future_ledger_events
            and ledger_clock_sequence == sorted(ledger_clock_sequence)
            and not duplicate_ledger_event_ids
            if is_g3_roommind else None
        ),
        "g3_entity_lifecycle_valid": (
            not invalid_entity_lifecycle if is_g3_roommind else None
        ),
        "g3_completion_reconciles_required_work": (
            not (completion_status == "completed" and open_required_work)
            if is_g3_roommind else None
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
            "excessive_focus_streaks": excessive_focus_streaks,
            "invalid_outcome_resolution_turns": invalid_outcome_resolution,
            "invalid_g3_ledger_event_ids": invalid_ledger_events,
            "unsupported_terminal_g3_event_ids": unsupported_terminal_ledger_events,
            "unsupported_completed_action_source_event_ids": unsupported_completed_action_sources,
            "unsupported_visible_current_world_actions": unsupported_visible_current_world_actions,
            "repeated_capability_focus_issues": repeated_capability_focus_issues,
            "unavailable_capability_boundary_fields": sorted(unavailable_boundary_fields),
            "future_g3_ledger_event_ids": future_ledger_events,
            "duplicate_g3_ledger_event_ids": duplicate_ledger_event_ids,
            "invalid_g3_entity_lifecycle": invalid_entity_lifecycle,
            "open_required_work_at_completion": open_required_work,
            "g39_field_projection_mismatches": field_projection_mismatches,
            "g4_same_speaker_near_duplicates": same_speaker_near_duplicates,
            "g41_player_floor_violations": player_floor_violations,
            "g42_question_target_mismatches": question_target_mismatches,
            "g43_cross_role_question_violations": cross_role_question_violations,
            "g44_unregistered_public_assignments": unregistered_public_assignments,
            "g45_cross_role_obligation_duplicates": cross_role_obligation_duplicates,
            "g45_incapable_obligation_targets": incapable_obligation_targets,
            "g45_expected_open_obligations": expected_open_obligations,
            "g45_recorded_open_obligations": recorded_open_obligations,
            "g47_focus_target_authority_violations": focus_target_authority_violations,
            "g47_bounded_handoff_violations": bounded_handoff_violations,
            "g48_malformed_public_fragments": malformed_public_fragments,
            "g48_post_closure_speech": post_closure_speech,
            "g48_ungrounded_live_artifact_receipts": ungrounded_live_artifact_receipts,
            "g49_multi_addressee_response_violations": multi_addressee_response_violations,
            "g49_generated_routing_prompt_violations": routing_prompt_violations,
            "g49_retrospective_authorship_violations": retrospective_authorship_violations,
            "g410_conditional_acceptance_events": conditional_acceptance_events,
            "g410_post_terminal_confirmation_speech": post_terminal_confirmation_speech,
            "g411_direct_response_violations": direct_response_violations,
            "g411_rejected_transition_surface_violations": rejected_transition_surface_violations,
            "g412_player_response_lock_violations": player_response_lock_violations,
        },
        "transcript_provenance": transcript_provenance(full_bundle),
    }
