"""Pure-Python checks for transcript authenticity and bilingual review schema."""

from copy import deepcopy

from app.external_observer import build_blinded_evaluation_packet
from app.research_protocol import (
    CURRENT_ARCHITECTURE_VERSION,
    CURRENT_GENERATION_ID,
    REALISM_RUBRIC,
    experiment_manifest,
    transcript_provenance,
)
from app.research_probes import run_integrity_probes


def main() -> None:
    assert CURRENT_GENERATION_ID == "G4.6"
    assert CURRENT_ARCHITECTURE_VERSION == (
        "g4.6-clause-grounded-recovery-governance"
    )
    manifest = experiment_manifest(study_phase="exploration", random_seed=20260902)
    assert manifest["generation_id"] == CURRENT_GENERATION_ID
    assert manifest["architecture_version"] == CURRENT_ARCHITECTURE_VERSION
    bundle = {
        "session": {"session_uuid": "real-session-1", "status": "completed"},
        "scenario": {"id": 1, "slug": "case", "title": "Case", "task_config": {}},
        "speaker_directory": {
            "user": {"role": "user", "job_title": "Player"},
            "ceo": {"role": "npc", "job_title": "CEO", "interaction_role": "decision_maker", "authority": {}},
        },
        "messages": [
            {"sequence_no": 2, "turn_id": 1, "speaker_id": "ceo", "speaker_type": "npc", "speaker_source": "ai", "content": "Exact reply", "created_at": "2026-01-01T00:00:02Z"},
            {"sequence_no": 1, "turn_id": 1, "speaker_id": "user", "speaker_type": "user", "speaker_source": "ai", "content": "Exact prompt", "created_at": "2026-01-01T00:00:01Z"},
            {"sequence_no": 3, "turn_id": 1, "speaker_id": "system", "speaker_type": "system", "speaker_source": "system", "content": "hidden"},
        ],
        "external_observation": {"system_claim": {"status": "completed"}},
    }
    provenance = transcript_provenance(bundle)
    packet = build_blinded_evaluation_packet(bundle)
    assert provenance["message_count"] == 2
    assert len(provenance["transcript_sha256"]) == 64
    assert [row["content"] for row in packet["public_transcript"]] == ["Exact prompt", "Exact reply"]
    assert packet["source_provenance"]["transcript_sha256"] == provenance["transcript_sha256"]
    assert "session_uuid" not in packet["source_provenance"]
    assert packet["condition_hidden"] is True
    assert packet["speaker_aliases"]["ceo"] == "Participant A"
    assert len(REALISM_RUBRIC) == 6
    assert all(len(row["indicators"]) == 3 for row in REALISM_RUBRIC.values())
    assert all(row["label_en"] and row["label_zh"] for row in REALISM_RUBRIC.values())
    probes = run_integrity_probes(bundle)
    assert probes["checks"]["sequence_numbers_strictly_increasing"] is False
    assert probes["checks"]["all_public_speakers_registered"] is True

    g2_bundle = deepcopy(bundle)
    g2_bundle["session"].update({
        "session_mode": "test",
        "run_config": {
            "comparison_protocol": "controlled",
            "comparison_lock_model": True,
            "research_manifest": {"architecture_version": "g2-coordinated-independent-agents"},
        },
    })
    g2_bundle["agent_memories"] = {"ceo": []}
    g2_bundle["task_result"] = {
        "coordination_history": [{
            "turn_id": 1,
            "focus": {"issue": "decision", "owner_ids": ["ceo"]},
        }]
    }
    g2_probes = run_integrity_probes(g2_bundle)
    assert g2_probes["checks"]["g2_coordination_history_present"] is True
    assert g2_probes["checks"]["g2_focus_owners_registered"] is True

    # G2 candidate metadata may be stored directly in run_config even if an
    # older archive omitted the nested manifest.  Player/user aliases are
    # normalized before checking registered focus owners.
    g21_bundle = deepcopy(g2_bundle)
    g21_bundle["session"]["run_config"] = {
        "comparison_protocol": "controlled",
        "comparison_lock_model": True,
        "architecture_version": "g2.1-grounded-coordinated-independent-agents",
    }
    g21_bundle["task_result"]["coordination_history"][0]["focus"]["owner_ids"] = ["player"]
    g21_probes = run_integrity_probes(g21_bundle)
    assert g21_probes["checks"]["g2_coordination_history_present"] is True
    assert g21_probes["checks"]["g2_focus_owners_registered"] is True

    g22_bundle = deepcopy(g2_bundle)
    g22_bundle["session"]["run_config"] = {
        "comparison_protocol": "controlled",
        "comparison_lock_model": True,
        "architecture_version": "g2.2-critical-grounded-coordinated-agents",
    }
    g22_probes = run_integrity_probes(g22_bundle)
    assert g22_probes["checks"]["g22_public_evidence_grounded"] is True
    g22_bundle["task_result"] = {
        "work_items": {
            "decision_evidence": {
                "required": True,
                "criticality_reason": "Public decision is blocked until evidence is provided.",
            }
        },
        "coordination_history": [{
            "turn_id": 1,
            "focus": {
                "issue": "work:decision_evidence", "kind": "work_item",
                "owner_ids": ["ceo"],
            },
        }],
    }
    critical_focus = run_integrity_probes(g22_bundle)
    assert critical_focus["checks"]["g22_work_focuses_task_critical"] is True
    g22_bundle["task_result"]["work_items"]["decision_evidence"]["required"] = False
    noncritical_focus = run_integrity_probes(g22_bundle)
    assert noncritical_focus["checks"]["g22_work_focuses_task_critical"] is False
    g22_bundle["messages"][1]["content"] = "I've attached a report that does not exist."
    failed_grounding = run_integrity_probes(g22_bundle)
    assert failed_grounding["checks"]["g22_public_evidence_grounded"] is False
    assert failed_grounding["all_applicable_passed"] is False

    g23_bundle = deepcopy(g2_bundle)
    g23_bundle["session"]["run_config"] = {
        "comparison_protocol": "controlled",
        "comparison_lock_model": True,
        "architecture_version": "g2.3-grounded-bounded-focus-agents",
    }
    g23_bundle["task_result"] = {
        "coordination_history": [
            {"turn_id": 1, "focus": {"issue": "decision", "kind": "state_variable", "focus_streak": 1, "owner_ids": ["ceo"]}},
            {"turn_id": 2, "focus": {"issue": "decision", "kind": "state_variable", "focus_streak": 2, "owner_ids": ["ceo"]}},
            {"turn_id": 3, "focus": {"issue": "outcome_resolution", "kind": "outcome_resolution", "focus_streak": 1, "origin_focus_issue": "decision", "owner_ids": ["ceo"]}},
        ],
    }
    g23_probes = run_integrity_probes(g23_bundle)
    assert g23_probes["checks"]["g23_focus_streak_bounded"] is True
    assert g23_probes["checks"]["g23_outcome_resolution_grounded"] is True
    g23_bundle["task_result"]["coordination_history"][2]["focus"] = {
        "issue": "decision", "kind": "state_variable", "focus_streak": 3,
        "owner_ids": ["ceo"],
    }
    bad_streak = run_integrity_probes(g23_bundle)
    assert bad_streak["checks"]["g23_focus_streak_bounded"] is False

    g3_bundle = deepcopy(g2_bundle)
    g3_bundle["session"]["run_config"] = {
        "comparison_protocol": "controlled",
        "comparison_lock_model": True,
        "architecture_version": "g3-ledger-grounded-multi-agent-simulation",
    }
    g3_bundle["task_result"] = {
        "completion_status": "in_progress",
        "work_items": {},
        "coordination_history": [{
            "turn_id": 1,
            "focus": {"issue": "decision", "kind": "state_variable", "focus_streak": 1, "owner_ids": ["ceo"]},
        }],
        "public_ledger": {
            "schema": "roommind-public-world-ledger-v1",
            "simulation_clock": {"turn": 1, "tick": 1},
            "entities": {
                "artifact:capacity_report": {
                    "kind": "artifact", "lifecycle": "submitted",
                }
            },
            "recent_events": [{
                "event_id": "ple-00001", "turn_id": 1, "tick": 1,
                "entity_kind": "artifact", "transition_to": "submitted",
                "inline_content": "Capacity is 5,200 units per month.",
                "public_evidence": {"quote": "Capacity is 5,200 units per month."},
                "provenance": "public_statement",
            }],
        },
    }
    g3_probes = run_integrity_probes(g3_bundle)
    assert g3_probes["checks"]["g3_authoritative_public_ledger_present"] is True
    assert g3_probes["checks"]["g3_ledger_events_have_public_provenance"] is True
    assert g3_probes["checks"]["g3_terminal_actions_have_inline_evidence"] is True
    assert g3_probes["checks"]["g3_simulation_clock_monotonic"] is True
    assert g3_probes["checks"]["g3_completion_reconciles_required_work"] is True

    invalid_g3 = deepcopy(g3_bundle)
    invalid_g3["task_result"]["public_ledger"]["recent_events"][0]["inline_content"] = ""
    invalid_g3["task_result"]["completion_status"] = "completed"
    invalid_g3["task_result"]["work_items"] = {
        "required_report": {"required": True, "status": "promised"}
    }
    invalid_g3_probes = run_integrity_probes(invalid_g3)
    assert invalid_g3_probes["checks"]["g3_terminal_actions_have_inline_evidence"] is False
    assert invalid_g3_probes["checks"]["g3_completion_reconciles_required_work"] is False

    g35_bundle = deepcopy(g3_bundle)
    g35_bundle["session"]["run_config"] = {
        "comparison_protocol": "controlled",
        "comparison_lock_model": True,
        "research_manifest": {
            "generation_id": "G3.5",
            "architecture_version": "g3.5-atomic-grounded-simulation",
        },
    }
    g35_bundle["task_result"]["public_ledger"]["entities"] = {
        "action:rollback": {"kind": "action", "lifecycle": "submitted"},
    }
    g35_bundle["task_result"]["public_ledger"]["recent_events"] = [{
        "event_id": "ple-00002", "turn_id": 1, "tick": 1,
        "entity_kind": "action", "transition_to": "submitted",
        "inline_content": "Rollback simulation completed with all checks green.",
        "public_evidence": {"quote": "The simulated rollback completed."},
        "provenance": "simulated_tool_result", "tool_result_id": "tool-rollback-1",
    }]
    g35_bundle["task_result"]["public_ledger"]["tool_results"] = {}
    missing_tool_result = run_integrity_probes(g35_bundle)
    assert missing_tool_result["checks"]["g35_completed_actions_require_tool_results"] is False
    assert missing_tool_result["all_applicable_passed"] is False
    g35_bundle["task_result"]["public_ledger"]["tool_results"] = {
        "tool-rollback-1": {
            "result_id": "tool-rollback-1", "actor_id": "ceo",
            "field": "rollback", "turn_id": 1,
            "inline_content": "Rollback simulation completed with all checks green.",
        }
    }
    grounded_tool_result = run_integrity_probes(g35_bundle)
    assert grounded_tool_result["checks"]["g35_completed_actions_require_tool_results"] is True

    g36_bundle = deepcopy(g35_bundle)
    g36_bundle["session"]["run_config"]["research_manifest"] = {
        "generation_id": "G3.6",
        "architecture_version": "g3.6-quote-grounded-capability-aware-simulation",
    }
    g36_bundle["messages"][0]["content"] = (
        "Containment is now active at the edge firewall."
    )
    visible_action = run_integrity_probes(g36_bundle)
    assert visible_action["checks"][
        "g36_visible_current_world_actions_require_tool_results"
    ] is False
    g36_bundle["messages"][0]["content"] = (
        "Containment will be activated after the evidence capture completes."
    )
    future_action = run_integrity_probes(g36_bundle)
    assert future_action["checks"][
        "g36_visible_current_world_actions_require_tool_results"
    ] is True

    g37_bundle = deepcopy(g36_bundle)
    g37_bundle["session"]["run_config"]["research_manifest"] = {
        "generation_id": "G3.7",
        "architecture_version": "g3.7-proposition-grounded-convergent-simulation",
    }
    g37_bundle["task_result"].update({
        "completion_status": "conditional",
        "capability_boundaries": {
            "containment_active": {"status": "unavailable"},
        },
        "outcome": {
            "type": "conditional",
            "status": "capability_boundary_reconciled",
            "unmet_conditions": ["containment_active"],
        },
        "coordination_history": [{
            "turn_id": 1,
            "focus": {
                "issue": "containment_active", "kind": "capability_boundary",
                "focus_streak": 1, "owner_ids": ["ceo"],
            },
        }],
    })
    g37_probes = run_integrity_probes(g37_bundle)
    assert g37_probes["checks"]["g37_capability_boundaries_not_repeated"] is True
    assert g37_probes["checks"]["g37_capability_boundary_closure_consistent"] is True
    g37_bundle["task_result"]["coordination_history"].append({
        "turn_id": 2,
        "focus": {
            "issue": "containment_active", "kind": "capability_boundary",
            "focus_streak": 2, "owner_ids": ["ceo"],
        },
    })
    repeated_boundary = run_integrity_probes(g37_bundle)
    assert repeated_boundary["checks"]["g37_capability_boundaries_not_repeated"] is False

    g38_bundle = deepcopy(g37_bundle)
    g38_bundle["session"]["run_config"]["research_manifest"] = {
        "generation_id": "G3.8",
        "architecture_version": "g3.8-authoritative-state-reducer-closure-lock",
    }
    g38_bundle["task_result"].update({
        "completion_status": "completed",
        "closure_lock": {"status": "locked", "resolved_fields": ["containment_active"]},
        "condition_results": [{
            "met": True,
            "condition": {"field": "containment_active", "operator": "==", "value": True},
        }],
        "work_items": {},
        "outcome": {"type": "completed", "status": "closed"},
        "coordination_history": [],
    })
    g38_probes = run_integrity_probes(g38_bundle)
    assert g38_probes["checks"]["g38_authoritative_closure_lock_consistent"] is True

    g39_bundle = deepcopy(g38_bundle)
    g39_bundle["session"]["run_config"]["research_manifest"] = {
        "generation_id": "G3.9",
        "architecture_version": "g3.9-natural-joint-confirmation-closure",
    }
    g39_bundle["scenario"]["task_config"] = {
        "state_schema": {"containment_active": {
            "type": "boolean",
            "confirmation_policy": "player_and_authorized_counterpart",
            "confirm_permissions": ["player", "ceo"],
        }},
        "completion_conditions": {"all": [{
            "field": "containment_active", "operator": "==", "value": True,
            "required_status": "confirmed",
        }]},
    }
    g39_bundle["speaker_directory"]["ceo"]["authority"] = {
        "can_confirm": ["containment_active"],
    }
    g39_bundle["task_result"]["variables"] = {
        "containment_active": {
            "value": True, "status": "confirmed",
            "confirmations": ["user", "ceo"],
        },
    }
    g39_bundle["task_result"]["public_ledger"]["entities"]["field:containment_active"] = {
        "entity_id": "field:containment_active", "kind": "decision",
        "field": "containment_active", "value": True, "lifecycle": "accepted",
        "actors_by_transition": {"accepted": ["user", "ceo"]},
    }
    g39_probes = run_integrity_probes(g39_bundle)
    assert g39_probes["checks"]["g39_task_does_not_end_stalled"] is True
    assert g39_probes["checks"]["g39_completed_task_has_closure_lock"] is True
    assert g39_probes["checks"]["g39_accepted_fields_project_atomically"] is True
    g39_bundle["task_result"]["completion_status"] = "stalled"
    g39_bundle["task_result"]["variables"]["containment_active"]["status"] = "proposed"
    failed_g39 = run_integrity_probes(g39_bundle)
    assert failed_g39["checks"]["g39_task_does_not_end_stalled"] is False
    assert failed_g39["checks"]["g39_accepted_fields_project_atomically"] is False

    g4_bundle = deepcopy(g39_bundle)
    g4_bundle["session"]["run_config"]["research_manifest"] = {
        "generation_id": "G4.0",
        "architecture_version": "g4.0-bounded-agenda-convergence",
    }
    g4_bundle["task_result"].update({
        "completion_status": "conditional",
        "open_issues": ["containment_active"],
        "outcome": {
            "type": "conditional",
            "status": "governor_bounded_close",
        },
    })
    g4_bundle["task_result"]["public_ledger"]["entities"] = {}
    g4_bundle["messages"].append({
        "sequence_no": 4,
        "turn_id": 2,
        "speaker_id": "ceo",
        "speaker_type": "npc",
        "speaker_source": "ai",
        "content": "We need verified containment evidence before final approval.",
        "created_at": "2026-01-01T00:00:04Z",
    })
    g4_probes = run_integrity_probes(g4_bundle)
    assert g4_probes["checks"]["g4_task_does_not_end_stalled"] is True
    assert g4_probes["checks"]["g4_no_progress_close_is_bounded"] is True
    assert g4_probes["checks"]["g4_same_speaker_near_duplicates_absent"] is True

    g41_bundle = deepcopy(g4_bundle)
    g41_bundle["session"]["run_config"]["research_manifest"] = {
        "generation_id": "G4.1",
        "architecture_version": "g4.1-floor-and-speech-act-ownership",
    }
    g41_bundle["speaker_directory"]["advisor"] = {
        "role": "npc", "display_name": "Advisor", "character_name": "Advisor",
        "job_title": "Advisor", "authority": {},
    }
    g41_bundle["agent_memories"]["advisor"] = []
    g41_bundle["messages"].extend([
        {
            "sequence_no": 5, "turn_id": 3, "speaker_id": "ceo",
            "speaker_type": "npc", "speaker_source": "ai",
            "content": "Could you describe the evidence behind your recommendation?",
            "created_at": "2026-01-01T00:00:05Z",
        },
        {
            "sequence_no": 6, "turn_id": 3, "speaker_id": "advisor",
            "speaker_type": "npc", "speaker_source": "ai",
            "content": "I led a similar decision by testing the recommendation first.",
            "created_at": "2026-01-01T00:00:06Z",
        },
    ])
    violated_floor = run_integrity_probes(g41_bundle)
    assert violated_floor["checks"]["g41_player_floor_handoff_respected"] is False
    g41_bundle["messages"].pop()
    respected_floor = run_integrity_probes(g41_bundle)
    assert respected_floor["checks"]["g41_player_floor_handoff_respected"] is True

    g42_bundle = deepcopy(g4_bundle)
    g42_bundle["session"]["run_config"]["research_manifest"] = {
        "generation_id": "G4.3",
        "architecture_version": "g4.3-cross-role-floor-and-evidence-boundary",
    }
    g42_bundle["speaker_directory"]["advisor"] = {
        "role": "npc", "display_name": "Avery Chen",
        "character_name": "Avery Chen", "job_title": "Advisor",
        "authority": {},
    }
    g42_bundle["agent_memories"]["advisor"] = []
    g42_bundle["messages"].extend([
        {
            "sequence_no": 5, "turn_id": 3, "speaker_id": "ceo",
            "speaker_type": "npc", "speaker_source": "ai",
            "content": "Avery, could you explain the operating constraint?",
            "meta": {"public_intent": {
                "kind": "statement", "target_id": "advisor",
            }},
            "created_at": "2026-01-01T00:00:05Z",
        },
        {
            "sequence_no": 6, "turn_id": 3, "speaker_id": "advisor",
            "speaker_type": "npc", "speaker_source": "ai",
            "content": "The constraint is the limited review window.",
            "created_at": "2026-01-01T00:00:06Z",
        },
    ])
    grounded_target = run_integrity_probes(g42_bundle)
    assert grounded_target["checks"]["g41_player_floor_handoff_respected"] is True
    assert grounded_target["checks"]["g42_structured_question_targets_match_public_speech"] is True
    g42_bundle["messages"][-2]["meta"]["public_intent"]["target_id"] = "user"
    mismatched_target = run_integrity_probes(g42_bundle)
    assert mismatched_target["checks"]["g42_structured_question_targets_match_public_speech"] is False

    g43_bundle = deepcopy(g42_bundle)
    g43_bundle["messages"][-2]["meta"]["public_intent"]["target_id"] = "advisor"
    g43_bundle["messages"].insert(-1, {
        "sequence_no": 6, "turn_id": 4, "speaker_id": "user",
        "speaker_type": "user", "speaker_source": "ai",
        "content": (
            "I confirm the operating constraint is the limited review window. "
            "Avery, could you add the details?"
        ),
        "meta": {"public_intent": {"kind": "handoff", "target_id": "advisor"}},
        "created_at": "2026-01-01T00:00:06Z",
    })
    g43_bundle["messages"][-1]["sequence_no"] = 7
    g43_bundle["messages"][-1]["turn_id"] = 4
    substituted_role = run_integrity_probes(g43_bundle)
    assert substituted_role["checks"]["g43_cross_role_question_ownership_preserved"] is False
    g43_bundle["messages"][-2]["content"] = "Avery, could you answer that question directly?"
    preserved_role = run_integrity_probes(g43_bundle)
    assert preserved_role["checks"]["g43_cross_role_question_ownership_preserved"] is True

    g44_bundle = deepcopy(g43_bundle)
    g44_bundle["session"]["run_config"]["research_manifest"] = {
        "generation_id": "G4.4",
        "architecture_version": "g4.4-deterministic-floor-owner-and-timebox-closure",
    }
    g44_bundle["messages"].append({
        "sequence_no": 8, "turn_id": 5, "speaker_id": "ceo",
        "speaker_type": "npc", "speaker_source": "ai",
        "content": "I'm assigning Alex Patel as the evidence owner.",
        "meta": {"public_intent": {"simulation_scope": "discussion"}},
        "created_at": "2026-01-01T00:00:08Z",
    })
    unregistered_owner = run_integrity_probes(g44_bundle)
    assert unregistered_owner["checks"]["g44_in_session_owners_are_registered"] is False
    g44_bundle["messages"][-1] = {
        **g44_bundle["messages"][-1],
        "content": "Avery Chen will be the evidence owner.",
    }
    registered_owner = run_integrity_probes(g44_bundle)
    assert registered_owner["checks"]["g44_in_session_owners_are_registered"] is True
    g44_bundle["messages"][-1] = {
        **g44_bundle["messages"][-1],
        "content": "Alex Patel will be the post-meeting evidence owner.",
        "meta": {"public_intent": {
            "simulation_scope": "external",
            "evidence_source": "external_followup",
        }},
    }
    external_owner = run_integrity_probes(g44_bundle)
    assert external_owner["checks"]["g44_in_session_owners_are_registered"] is True

    g45_bundle = deepcopy(g44_bundle)
    g45_bundle["session"]["run_config"]["research_manifest"] = {
        "generation_id": "G4.5",
        "architecture_version": CURRENT_ARCHITECTURE_VERSION,
    }
    g45_bundle["scenario"]["task_config"] = {
        "state_schema": {
            "decision": {
                "type": "boolean", "confirm_permissions": ["player", "ceo"],
                "confirmation_policy": "player_and_responsible_participant",
            }
        },
        "completion_conditions": {"all": [{
            "field": "decision", "operator": "==", "value": True,
            "required_status": "confirmed",
        }]},
    }
    g45_bundle["task_result"].update({
        "completion_status": "in_progress",
        "obligation_graph": {
            "schema": "roommind-meeting-obligation-graph-v1",
            "all_required_satisfied": False,
            "open_obligation_ids": ["all:0:decision"],
            "obligations": {
                "all:0:decision": {
                    "obligation_id": "all:0:decision", "field": "decision",
                    "status": "pending", "required_now": True,
                    "authorized_confirmer_ids": ["user", "ceo"],
                    "missing_confirmer_ids": ["user", "ceo"],
                }
            },
        },
    })
    g45_bundle["task_result"]["public_ledger"]["recent_events"] = []
    g45 = run_integrity_probes(g45_bundle)
    assert g45["checks"]["g45_obligation_graph_present"] is True
    assert g45["checks"]["g45_open_obligations_reconcile"] is True
    assert g45["checks"]["g45_obligation_targets_authorized"] is True
    g45_bundle["task_result"]["obligation_graph"]["open_obligation_ids"] = []
    bad_open_graph = run_integrity_probes(g45_bundle)
    assert bad_open_graph["checks"]["g45_open_obligations_reconcile"] is False

    g4_bundle["messages"].append({
        "sequence_no": 5,
        "turn_id": 3,
        "speaker_id": "ceo",
        "speaker_type": "npc",
        "speaker_source": "ai",
        "content": "We need the verified containment evidence before we give final approval.",
        "created_at": "2026-01-01T00:00:05Z",
    })
    repeated_g4 = run_integrity_probes(g4_bundle)
    assert repeated_g4["checks"]["g4_same_speaker_near_duplicates_absent"] is False


if __name__ == "__main__":
    main()
