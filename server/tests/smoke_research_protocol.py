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
    assert CURRENT_GENERATION_ID == "G3.4"
    assert CURRENT_ARCHITECTURE_VERSION == (
        "g3.4-natural-recovery-bounded-evidence-ledger-simulation"
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
                "provenance": "prevalidated_agent_intent",
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


if __name__ == "__main__":
    main()
