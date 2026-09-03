"""Regression checks for public NPC speech safety."""

from app.agent.speech_safety import (
    PUBLIC_RESPONSE_DRAFT,
    player_speech_rejection_reason,
    normalized_public_propositions,
    protected_information_reason,
    retain_safe_public_clauses,
    speech_rejection_reason,
    terminal_current_world_action_reason,
)
from types import SimpleNamespace

from app.agent.act import configured_public_fallback
from app.orchestrator.common import orch_support
from app.task_state import (
    advance_phase,
    apply_evaluator_updates,
    evaluate_conditions,
    finalize_stalled_task_state,
    initial_task_state,
    normalize_evaluator_payload,
    public_task_result,
    prepare_turn_governance,
    reconcile_capability_boundary_closure,
    set_progress_metadata,
    task_progress_signature,
)
from app.orchestrator.generative import generative_orchestrator
from app.player_agent import (
    normalize_player_content,
    pending_public_questions,
    retrospective_continuity_anchor,
)
from app.public_ledger import (
    commit_public_intent, record_simulated_tool_result, validate_public_intent,
)


def main() -> None:
    assert configured_public_fallback({
        "default": "Ask for the commercial conditions needed to make the proposal workable."
    }) == ""
    assert configured_public_fallback({
        "default": "Internal instruction.",
        "public_reply": "Could you clarify the commercial conditions you can offer?",
    }) == "Could you clarify the commercial conditions you can offer?"

    # A state evaluator may echo schema defaults that were never spoken.  Only
    # the explicitly quoted field/value survives deterministic grounding, and
    # "before we can finalize" cannot become a completed outcome.
    supplier = SimpleNamespace(
        character_id="supplier_ceo",
        authority={"can_propose": ["unit_price", "delivery_days"],
                   "can_confirm": ["unit_price", "delivery_days"]},
    )
    negotiation_config = {
        "state_schema": {
            "unit_price": {"type": "number", "propose_permissions": ["supplier_ceo"]},
            "delivery_days": {"type": "integer", "propose_permissions": ["supplier_ceo"]},
            "quality_protocol": {"type": "boolean", "propose_permissions": ["quality_director"]},
        },
        "phases": [{"phase_id": "opening"}],
        "completion_conditions": {"all": [
            {"field": "unit_price", "operator": "<=", "value": 85, "required_status": "confirmed"},
            {"field": "delivery_days", "operator": "<=", "value": 30, "required_status": "confirmed"},
            {"field": "quality_protocol", "operator": "==", "value": True, "required_status": "confirmed"},
        ]},
    }
    quote = (
        "The unit price target of 85 RMB is the highest-priority open issue. "
        "We must secure volume commitments before we can finalize the contract."
    )
    hallucinated = initial_task_state(negotiation_config)
    apply_evaluator_updates(
        task_config=negotiation_config, state=hallucinated,
        parsed={
            "updates": [
                {"field": "unit_price", "value": 85, "status": "proposed", "proposed_by": "supplier_ceo", "confirmed_by": [], "evidence": [{"speaker_id": "supplier_ceo", "quote": quote}]},
                {"field": "delivery_days", "value": 30, "status": "proposed", "proposed_by": "supplier_ceo", "confirmed_by": [], "evidence": [{"speaker_id": "supplier_ceo", "quote": quote}]},
                {"field": "quality_protocol", "value": True, "status": "proposed", "proposed_by": "supplier_ceo", "confirmed_by": [], "evidence": [{"speaker_id": "supplier_ceo", "quote": quote}]},
            ],
            "events": [{
                "event_type": "action_committed", "subject": "pricing data",
                "status": "completed", "actor_id": "user",
                "evidence": [{"speaker_id": "user", "quote": "Please provide the pricing data."}],
            }],
            "outcome": {"type": "completed", "reason": "finalized", "evidence": [{"speaker_id": "supplier_ceo", "quote": quote}]},
        },
        characters=[supplier], player_text="Please provide the pricing data.",
        npc_turns=[{"speaker_id": "supplier_ceo", "content": quote}], turn_id=1,
    )
    assert hallucinated["variables"]["unit_price"]["status"] == "proposed"
    assert hallucinated["variables"]["delivery_days"]["status"] == "unknown"
    assert hallucinated["variables"]["quality_protocol"]["status"] == "unknown"
    assert hallucinated["work_items"] == {}
    assert hallucinated["completion_status"] == "in_progress"

    clarification_state = initial_task_state({
        "state_schema": {}, "phases": [{"phase_id": "opening"}],
        "completion_conditions": {"all": []},
    })
    clarification = "Please clarify the highest-priority open issue before I commit."
    apply_evaluator_updates(
        task_config={"state_schema": {}, "phases": [{"phase_id": "opening"}], "completion_conditions": {"all": []}},
        state=clarification_state,
        parsed={"updates": [], "events": [{
            "event_type": "information_provided", "subject": "unit price target",
            "status": "completed", "actor_id": "supplier_ceo",
            "evidence": [{"speaker_id": "supplier_ceo", "quote": clarification}],
        }]},
        characters=[supplier], player_text="",
        npc_turns=[{"speaker_id": "supplier_ceo", "content": clarification}], turn_id=1,
    )
    assert clarification_state["work_items"] == {}

    # Two authorized public acceptances of the same explicit field value are
    # deterministically projected into the task read model without relying on
    # the LLM evaluator to rediscover them.
    accepted_config = {
        "state_schema": {"unit_price": {
            "type": "number",
            "confirmation_policy": "player_and_authorized_counterpart",
            "confirm_permissions": ["player", "supplier_ceo"],
            "propose_permissions": ["player", "supplier_ceo"],
        }},
        "phases": [{"phase_id": "opening"}],
        "completion_conditions": {"all": [{
            "field": "unit_price", "operator": "<=", "value": 85,
            "required_status": "confirmed",
        }]},
    }
    accepted_state = initial_task_state(accepted_config)
    player_accept = validate_public_intent(
        character={"character_id": "user", "authority": {
            "can_propose": ["unit_price"], "can_confirm": ["unit_price"],
        }}, state=accepted_state, turn_id=1,
        intent={"kind": "decision", "subject": "unit price 85 RMB",
                "field": "unit_price", "value": 85, "transition": "accepted"},
    )
    commit_public_intent(
        accepted_state, intent=player_accept,
        public_quote="I accept the unit price of 85 RMB.", tick=0,
    )
    supplier_accept = validate_public_intent(
        character=supplier, state=accepted_state, turn_id=1,
        intent={"kind": "decision", "subject": "unit price 85 RMB",
                "field": "unit_price", "value": 85, "transition": "accepted"},
    )
    commit_public_intent(
        accepted_state, intent=supplier_accept,
        public_quote="We accept the unit price of 85 RMB.", tick=1,
    )
    apply_evaluator_updates(
        task_config=accepted_config, state=accepted_state,
        parsed={"updates": [], "events": []}, characters=[supplier],
        player_text="", npc_turns=[], turn_id=1,
    )
    assert accepted_state["variables"]["unit_price"]["value"] == 85
    assert accepted_state["variables"]["unit_price"]["status"] == "confirmed"
    assert set(accepted_state["variables"]["unit_price"]["confirmations"]) == {"user", "supplier_ceo"}
    assert accepted_state["completion_status"] == "completed"

    # G3.5 commits each explicit confirmation from the grounded evaluator
    # evidence even while the aggregate field status is still proposed.
    projected_state = initial_task_state(accepted_config)
    apply_evaluator_updates(
        task_config=accepted_config, state=projected_state,
        parsed={"updates": [{
            "field": "unit_price", "value": 85, "status": "proposed",
            "proposed_by": "user", "confirmed_by": ["user"],
            "evidence": [{"speaker_id": "user", "quote": "I accept the unit price of 85 RMB."}],
        }], "events": []},
        characters=[supplier], player_text="I accept the unit price of 85 RMB.",
        npc_turns=[], turn_id=1,
    )
    assert projected_state["variables"]["unit_price"]["status"] == "proposed"
    assert projected_state["variables"]["unit_price"]["confirmations"] == ["user"]
    apply_evaluator_updates(
        task_config=accepted_config, state=projected_state,
        parsed={"updates": [{
            "field": "unit_price", "value": 85, "status": "confirmed",
            "proposed_by": "supplier_ceo", "confirmed_by": ["supplier_ceo"],
            "evidence": [{"speaker_id": "supplier_ceo", "quote": "We accept the unit price of 85 RMB."}],
        }], "events": []},
        characters=[supplier], player_text="",
        npc_turns=[{"speaker_id": "supplier_ceo", "content": "We accept the unit price of 85 RMB."}],
        turn_id=2,
    )
    assert projected_state["variables"]["unit_price"]["status"] == "confirmed"
    assert set(projected_state["variables"]["unit_price"]["confirmations"]) == {
        "user", "supplier_ceo",
    }
    assert projected_state["completion_status"] == "completed"

    # G3.6 does not depend on the evaluator correctly filling confirmed_by.
    # Quote-level parsing normalizes numeric values with units and accumulates
    # the two authorized confirmations without inferring conditional language.
    quote_projected = initial_task_state(accepted_config)
    apply_evaluator_updates(
        task_config=accepted_config, state=quote_projected,
        parsed={"updates": [{
            "field": "unit_price", "value": "84 RMB", "status": "proposed",
            "proposed_by": "user", "confirmed_by": [],
            "evidence": [{"speaker_id": "user", "quote": "I accept the unit price of 84 RMB."}],
        }], "events": []},
        characters=[supplier], player_text="I accept the unit price of 84 RMB.",
        npc_turns=[], turn_id=1,
    )
    assert quote_projected["variables"]["unit_price"]["value"] == 84.0
    assert quote_projected["variables"]["unit_price"]["confirmations"] == ["user"]
    apply_evaluator_updates(
        task_config=accepted_config, state=quote_projected,
        parsed={"updates": [], "events": []}, characters=[supplier], player_text="",
        npc_turns=[{
            "speaker_id": "supplier_ceo",
            "content": "We formally confirm the agreed unit price of 84 RMB.",
        }], turn_id=2,
    )
    assert quote_projected["variables"]["unit_price"]["value"] == 84.0
    assert quote_projected["variables"]["unit_price"]["status"] == "confirmed"
    assert set(quote_projected["variables"]["unit_price"]["confirmations"]) == {
        "user", "supplier_ceo",
    }

    atomic_quote = initial_task_state(accepted_config)
    apply_evaluator_updates(
        task_config=accepted_config, state=atomic_quote,
        parsed={"updates": [], "events": []}, characters=[supplier],
        player_text=(
            "I confirm the unit price of 84 RMB. "
            "Delivery remains conditional on the capacity review."
        ),
        npc_turns=[], turn_id=1,
    )
    assert atomic_quote["variables"]["unit_price"]["confirmations"] == ["user"]

    conditional_quote = initial_task_state(accepted_config)
    apply_evaluator_updates(
        task_config=accepted_config, state=conditional_quote,
        parsed={"updates": [], "events": []}, characters=[supplier], player_text="",
        npc_turns=[{
            "speaker_id": "supplier_ceo",
            "content": "We confirm the unit price of 84 RMB conditionally, subject to capacity review.",
        }], turn_id=1,
    )
    assert conditional_quote["variables"]["unit_price"]["status"] == "unknown"
    leaked_plan = (
        "I will first confirm the purchase volume to set the foundation, aiming "
        "to lock an annual framework agreement for at least 100k units. My bottom "
        "line is a unit price no lower than 82 RMB and no uncapped penalty"
    )
    assert speech_rejection_reason(leaked_plan, active_plan_text=leaked_plan)
    assert speech_rejection_reason(
        "I appreciate the proposal, but the 5% cap is non"
    ) == "truncated"
    assert speech_rejection_reason(
        "I need 30% upfront and the balance within 30"
    ) == "truncated"
    assert speech_rejection_reason(
        "Thank you for the proposal. We can review the full package together."
    ) is None
    mislabeled_statement = {
        "kind": "statement", "transition": "proposed",
        "simulation_scope": "discussion", "evidence_source": "public_statement",
        "validation": "accepted", "tool_result_id": "",
    }
    assert terminal_current_world_action_reason(
        "Containment is now active at the edge firewall.",
        validated_intent=mislabeled_statement,
    ) == "current_world_completion_requires_simulated_tool_result"
    passive = normalized_public_propositions(
        "All traffic to the affected service has been blocked."
    )
    assert passive and passive[0]["object"] == "traffic"
    assert passive[0]["predicate"] == "blocked"
    assert passive[0]["modality"] == "asserted_current"
    # Frozen G3.6 counterexamples: passive voice and terse artifact fragments
    # must not bypass source-typed grounding.
    assert terminal_current_world_action_reason(
        "All traffic to the affected service has been blocked, so the ETA for completion is zero minutes.",
        validated_intent=mislabeled_statement,
    ) == "current_world_completion_requires_simulated_tool_result"
    assert speech_rejection_reason(
        "Sample log entries attached.", validated_intent=mislabeled_statement,
    ) in {
        "unsupported_artifact_claim",
        "current_world_completion_requires_simulated_tool_result",
    }
    assert speech_rejection_reason(
        "The email has been successfully delivered.",
        validated_intent=mislabeled_statement,
    ) in {
        "unsupported_artifact_claim",
        "current_world_completion_requires_simulated_tool_result",
        "speech_exceeds_validated_lifecycle",
    }
    assert speech_rejection_reason(
        "The memory dumps have been completed and archived.",
        validated_intent=mislabeled_statement,
    ) in {
        "unsupported_artifact_claim",
        "current_world_completion_requires_simulated_tool_result",
        "speech_exceeds_validated_lifecycle",
    }
    assert speech_rejection_reason(
        "Once the health check is complete, we will publish the update.",
        validated_intent=mislabeled_statement,
    ) is None
    assert retain_safe_public_clauses(
        "The impact affects all regions. Containment is now active at the edge firewall.",
        validated_intent=mislabeled_statement,
    ) == "The impact affects all regions."
    draft_instruction = "Ask for the commercial conditions needed to make the proposal workable without inventing a commitment."
    assert speech_rejection_reason(
        draft_instruction,
        public_draft_text=draft_instruction,
    ) == "public_draft_echo"
    supplier_secret = ["The supplier's exact reservation unit price is 82 RMB."]
    assert protected_information_reason(
        "We need to clarify our reservation unit price of 82 RMB.",
        protected_secrets=supplier_secret,
    ) == "protected_information_leak"
    assert speech_rejection_reason(
        "Our exact reservation unit price is 82 RMB.",
        protected_secrets=supplier_secret,
    ) == "protected_information_leak"
    assert speech_rejection_reason(
        "We require sustainable margin and dependable annual volume.",
        protected_secrets=supplier_secret,
    ) is None
    assert player_speech_rejection_reason(
        '{"content": "A truncated proposal", "intent": "compromise with long'
    ) == "structured_output"
    assert player_speech_rejection_reason(
        "Let’s review the complete package before deciding."
    ) is None
    assert speech_rejection_reason(
        "I've attached the verified capacity report for approval."
    ) == "unsupported_artifact_claim"
    retrospective = {
        "kind": "fact", "transition": "proposed", "simulation_scope": "retrospective",
    }
    assert speech_rejection_reason(
        "In my previous role, I attached the revised weighting table after the workshop.",
        validated_intent=retrospective,
    ) is None
    assert speech_rejection_reason(
        "Here is the updated risk canvas; see the attached PDF.",
        validated_intent=retrospective,
    ) == "unsupported_artifact_claim"
    assert speech_rejection_reason(
        "I've just emailed you the historical scorecard.",
        validated_intent=retrospective,
    ) == "unsupported_artifact_claim"
    assert speech_rejection_reason(
        "The supporting file is at https://invented.example/interview-evidence.",
        validated_intent=retrospective,
    ) == "unsupported_url"
    assert speech_rejection_reason(
        "I've just emailed you the signed capacity letter, and the attachment includes the schedule."
    ) == "unsupported_artifact_claim"
    assert speech_rejection_reason(
        "Archive upload completed and the checksums match the source hashes."
    ) == "unsupported_artifact_claim"
    assert speech_rejection_reason(
        "The evidence is stored at repo://evidence/incident/archive."
    ) == "unsupported_url"
    assert speech_rejection_reason(
        "I will send the signed capacity letter tomorrow."
    ) is None, "future commitments remain valid work items rather than fabricated completion"
    assert speech_rejection_reason(
        "Could you confirm whether the signed capacity letter has been emailed?"
    ) is None, "a request for evidence is not itself a fabricated completion claim"
    assert speech_rejection_reason(
        "We still need confirmation that the evidence archive and its checksum have been verified. Could you share the verification status?"
    ) is None, "a grammatical confirmation request must not become a completed artifact claim"
    assert speech_rejection_reason(
        "Review https://invented.example/report for the evidence."
    ) == "unsupported_url"
    assert player_speech_rejection_reason(
        "Based on the evidence so far, rollback was reported complete and monitoring shows no anomalies.",
        public_context=(
            "[sre_lead]: Can you confirm the rollback is complete?\n"
            "[security_lead]: Have the checksums been verified?"
        ),
        validated_intent={
            "kind": "decision", "transition": "proposed",
            "simulation_scope": "discussion",
        },
    ) == "question_treated_as_public_evidence"
    assert player_speech_rejection_reason(
        "Based on the metrics, the service remains degraded.",
        public_context="[sre_lead]: Metrics show the error rate remains above 10%.",
        validated_intent={
            "kind": "statement", "transition": "proposed",
            "simulation_scope": "discussion",
        },
    ) is None
    assert player_speech_rejection_reason(
        "Based on the logs, the rollback completed.",
        public_context="[sre_lead]: The rollback completed at 10:15 UTC.",
        validated_intent={
            "kind": "statement", "transition": "proposed",
            "simulation_scope": "discussion",
        },
    ) is None
    assert player_speech_rejection_reason(
        "Based on the evidence available, we cannot confirm recovery and should defer closure pending verification.",
        public_context="[sre_lead]: Can you confirm the rollback is complete?",
        validated_intent={
            "kind": "statement", "transition": "proposed",
            "simulation_scope": "discussion",
        },
    ) is None
    assert player_speech_rejection_reason(
        (
            "Based on the evidence we have so far, the rollback was started. "
            "We cannot yet confirm that it completed or restored service."
        ),
        public_context=(
            "[sre_lead]: Can you confirm the rollback is complete?\n"
            "[security_lead]: Please provide the rollback logs."
        ),
        validated_intent={
            "kind": "statement", "transition": "proposed",
            "simulation_scope": "discussion",
        },
    ) == "question_treated_as_public_evidence", (
        "a later cautious clause must not excuse an earlier invented evidence claim"
    )
    assert player_speech_rejection_reason(
        (
            "Based on the current evidence—rollback logs showing completion and "
            "service health metrics within normal ranges—we can safely conclude "
            "the service is back up, but because the evidence archive and its "
            "checksum have not yet been verified, we cannot confirm data integrity."
        ),
        public_context=(
            "[sre_lead]: Can you confirm the rollback is complete and the service has recovered?\n"
            "[user]: I need confirmation that the rollback has completed. Could you share the latest deployment status and health metrics?\n"
            "[security_lead]: Have the evidence archive and checksum already been verified?\n"
            "[user]: Security Lead, we have not yet verified the evidence archive or its checksum."
        ),
        validated_intent={
            "kind": "decision", "transition": "proposed",
            "simulation_scope": "discussion",
        },
    ) == "question_treated_as_public_evidence", (
        "unrelated negative evidence must not ground a positive recovery claim"
    )
    assert speech_rejection_reason(
        "The SHA-256 is 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef."
    ) == "unsupported_hash"
    assert speech_rejection_reason(
        "I can access https://known.example/report.",
        public_context="Earlier, the team shared https://known.example/report.",
    ) is None
    assert normalize_player_content(
        '{"content":"I will answer with a concrete example.","intent":"opening"}'
    ) == "I will answer with a concrete example."
    assert normalize_player_content(
        '{"content":"{\\"content\\":\\"I am ready for the first question.\\"}"}'
    ) == "I am ready for the first question."
    interview_messages = [
        {
            "speaker_id": "user", "speaker_type": "user",
            "content": "In Q2 2021 I resolved the Feature Z rollout conflict.",
        },
        {
            "speaker_id": "people_partner", "speaker_type": "npc",
            "content": "How did you ensure different voices were heard?",
        },
    ]
    assert retrospective_continuity_anchor(
        interview_messages,
        pending_questions=pending_public_questions(interview_messages),
        evidence_mode="retrospective_claim",
    ) == "In Q2 2021 I resolved the Feature Z rollout conflict."
    interview_messages[-1]["content"] = "Can you give a different project example?"
    assert retrospective_continuity_anchor(
        interview_messages,
        pending_questions=pending_public_questions(interview_messages),
        evidence_mode="retrospective_claim",
    ) == ""
    nested_evaluation = '{"content":"{\\"phase\\":\\"evidence\\",\\"updates\\":[{\\"field\\":\\"outcome\\",\\"value\\":true,\\"status\\":\\"proposed\\"}]}"}'
    assert normalize_evaluator_payload(nested_evaluation)["updates"][0]["field"] == "outcome"
    assert "bottom line" not in PUBLIC_RESPONSE_DRAFT.casefold()
    assert "active plan" not in PUBLIC_RESPONSE_DRAFT.casefold()
    config = {
        "state_schema": {"outcome": {"type": "boolean"}},
        "phases": [{"phase_id": "active"}],
        "completion_conditions": {"all": [
            {"field": "outcome", "operator": "==", "value": True, "required_status": "confirmed"}
        ]},
    }
    state = initial_task_state(config)
    state["variables"]["outcome"].update(value=True, status="proposed")
    assert evaluate_conditions(config, state)["completion_status"] == "in_progress"
    state["variables"]["outcome"]["status"] = "confirmed"
    assert evaluate_conditions(config, state)["completion_status"] == "completed"

    # A conversational claim of completion cannot override unmet configured
    # conditions.  It becomes a truthful conditional/deferred terminal result.
    premature_state = initial_task_state(config)
    premature_state["outcome"] = {
        "type": "completed", "status": "explicit", "reason": "We are done", "evidence": []
    }
    evaluated_premature = evaluate_conditions(config, premature_state)
    assert evaluated_premature["completion_status"] == "deferred"
    assert evaluated_premature["outcome"]["claimed_type"] == "completed"
    assert evaluated_premature["outcome"]["unmet_conditions"] == ["outcome"]

    phase_config = {
        "state_schema": {
            "facts_known": {"type": "boolean"},
            "action_done": {"type": "boolean"},
        },
        "phases": [
            {"phase_id": "observe"},
            {"phase_id": "act", "entry_conditions": {"all": [
                {"field": "facts_known", "operator": "==", "value": True, "required_status": "confirmed"}
            ]}},
            {"phase_id": "close", "entry_conditions": {"all": [
                {"field": "action_done", "operator": "==", "value": True, "required_status": "confirmed"}
            ]}},
        ],
        "completion_conditions": {"all": []},
    }
    phase_state = initial_task_state(phase_config)
    phase_state["variables"]["facts_known"].update(value=True, status="confirmed")
    assert advance_phase(phase_config, phase_state) == "act"
    phase_state["variables"]["facts_known"].update(value=False, status="disputed")
    assert advance_phase(phase_config, phase_state) == "act", "phase progression must be monotonic"
    phase_state["variables"]["action_done"].update(value=True, status="confirmed")
    assert advance_phase(phase_config, phase_state) == "close"

    # Confirmations from authorized speakers commonly arrive in separate turns.
    # They must accumulate for the same typed value instead of being overwritten.
    cross_turn_config = {
        "state_schema": {
            "outcome": {
                "type": "boolean",
                "propose_permissions": ["player", "owner"],
                "confirm_permissions": ["player", "owner"],
                "confirmation_policy": "player_and_responsible_participant",
            }
        },
        "phases": [{"phase_id": "work"}, {"phase_id": "done", "entry_conditions": {"all": [
            {"field": "outcome", "operator": "==", "value": True, "required_status": "confirmed"}
        ]}}],
        "completion_conditions": {"all": [
            {"field": "outcome", "operator": "==", "value": True, "required_status": "confirmed"}
        ]},
    }
    owner = SimpleNamespace(character_id="owner", authority={
        "can_confirm": ["outcome", "capacity_evidence"],
        "can_provide": ["capacity_evidence"],
    })
    cross_state = initial_task_state(cross_turn_config)
    apply_evaluator_updates(
        task_config=cross_turn_config,
        state=cross_state,
        parsed={"updates": [{
            "field": "outcome", "value": True, "status": "confirmed",
            "proposed_by": "user", "confirmed_by": ["user"],
            "evidence": [{"speaker_id": "user", "quote": "I confirm outcome true"}],
        }]},
        characters=[owner],
        player_text="I confirm outcome true",
        npc_turns=[],
    )
    assert cross_state["variables"]["outcome"]["status"] == "proposed"
    assert cross_state["variables"]["outcome"]["confirmations"] == ["user"]
    before_signature = task_progress_signature(cross_state)
    apply_evaluator_updates(
        task_config=cross_turn_config,
        state=cross_state,
        parsed={"updates": [{
            "field": "outcome", "value": True, "status": "confirmed",
            "proposed_by": "owner", "confirmed_by": ["owner"],
            "evidence": [{"speaker_id": "owner", "quote": "Outcome true is confirmed"}],
        }]},
        characters=[owner],
        player_text="Thank you",
        npc_turns=[{"speaker_id": "owner", "content": "Outcome true is confirmed"}],
    )
    assert cross_state["variables"]["outcome"]["status"] == "confirmed"
    assert set(cross_state["variables"]["outcome"]["confirmations"]) == {"user", "owner"}
    assert cross_state["completion_status"] == "completed"
    assert cross_state["phase"] == "done"
    assert task_progress_signature(cross_state) != before_signature
    assert public_task_result(cross_state)["variables"]["outcome"]["value"] is True

    # A later proposal cannot silently reopen a confirmed item.
    apply_evaluator_updates(
        task_config=cross_turn_config,
        state=cross_state,
        parsed={"updates": [{
            "field": "outcome", "value": False, "status": "proposed",
            "proposed_by": "user", "confirmed_by": [],
            "evidence": [{"speaker_id": "user", "quote": "I propose outcome false"}],
        }]},
        characters=[owner],
        player_text="I propose outcome false",
        npc_turns=[],
        turn_id=3,
    )
    assert cross_state["variables"]["outcome"]["value"] is True
    assert cross_state["variables"]["outcome"]["status"] == "confirmed"
    assert cross_state["variables"]["outcome"]["superseded_proposals"][-1]["value"] is False

    # Evidence remains valid across harmless whitespace changes, and an omitted
    # proposer can be recovered from the verified public speaker.
    inferred_state = initial_task_state(cross_turn_config)
    apply_evaluator_updates(
        task_config=cross_turn_config,
        state=inferred_state,
        parsed={"updates": [{
            "field": "outcome", "value": True, "status": "proposed",
            "proposed_by": "", "confirmed_by": [],
            "evidence": [{"speaker_id": "owner", "quote": "Outcome true is proposed"}],
        }]},
        characters=[owner],
        player_text="",
        npc_turns=[{"speaker_id": "owner", "content": "Outcome true\n is   proposed"}],
    )
    assert inferred_state["variables"]["outcome"]["status"] == "proposed"
    assert inferred_state["variables"]["outcome"]["proposals"][-1]["proposed_by"] == "owner"

    # A claimed confirmation without an exact public evidence excerpt is rejected.
    bad_state = initial_task_state(cross_turn_config)
    apply_evaluator_updates(
        task_config=cross_turn_config,
        state=bad_state,
        parsed={"updates": [{
            "field": "outcome", "value": True, "status": "confirmed",
            "proposed_by": "owner", "confirmed_by": ["owner"],
            "evidence": [{"speaker_id": "owner", "quote": "invented confirmation"}],
        }]},
        characters=[owner],
        player_text="",
        npc_turns=[{"speaker_id": "owner", "content": "I need more information."}],
    )
    assert bad_state["variables"]["outcome"]["status"] != "confirmed"

    # Generic event governance is scenario-neutral. A promise is distinct from
    # delivery, duplicate promises do not create progress, and explicit
    # deferral is a valid terminal outcome for open-ended simulations.
    event_state = initial_task_state({
        "state_schema": {}, "phases": [{"phase_id": "active"}],
        "completion_conditions": {"all": []},
    })
    apply_evaluator_updates(
        task_config={"state_schema": {}, "phases": [{"phase_id": "active"}], "completion_conditions": {"all": []}},
        state=event_state,
        parsed={"updates": [], "events": [{
            "event_type": "artifact_offered", "subject": "capacity evidence",
            "status": "proposed", "actor_id": "owner",
            "summary": "The decision is blocked until the owner provides capacity evidence.",
            "task_critical": True,
            "criticality_reason": "The decision cannot close until this evidence is provided.",
            "evidence": [{"speaker_id": "owner", "quote": "We cannot decide until I send the capacity evidence"}],
        }]},
        characters=[owner], player_text="",
        npc_turns=[{"speaker_id": "owner", "content": "We cannot decide until I send the capacity evidence."}],
        turn_id=1,
    )
    assert event_state["work_items"]["capacity_evidence"]["status"] == "promised"
    coordinated = prepare_turn_governance(
        event_state,
        characters=[owner],
        turn_id=3,
        safety_max_turns=10,
        max_stagnant_turns=6,
    )
    focus = coordinated["progress"]["focus"]
    assert focus["issue"] == "work:capacity_evidence"
    assert focus["owner_ids"] == ["owner"]
    assert focus["due_now"] is True
    assert coordinated["coordination_history"][-1]["turn_id"] == 3

    # Player-only work is tracked in the ledger but is not selected as an NPC
    # coordinator focus because the shared comparison player cannot see the
    # private RoomMind coordinator.
    player_only_state = initial_task_state({
        "state_schema": {}, "phases": [{"phase_id": "active"}],
        "completion_conditions": {"all": []},
    })
    player_only_state["work_items"] = {
        "player_report": {
            "required": True, "status": "promised", "owner_id": "player",
            "target_id": "", "promised_turn": 1,
        },
        "owner_report": {
            "required": True, "status": "promised", "owner_id": "owner",
            "target_id": "", "promised_turn": 2,
        },
    }
    player_focus = prepare_turn_governance(
        player_only_state, characters=[owner], turn_id=4,
        safety_max_turns=10, max_stagnant_turns=6,
    )["progress"]["focus"]
    assert player_focus["issue"] == "work:owner_report"
    assert player_focus["owner_ids"] == ["owner"]

    # Incidental offers remain auditable but do not enter the coordinator queue.
    incidental_state = initial_task_state({
        "state_schema": {}, "phases": [{"phase_id": "active"}],
        "completion_conditions": {"all": []},
    })
    apply_evaluator_updates(
        task_config={"state_schema": {}, "phases": [{"phase_id": "active"}], "completion_conditions": {"all": []}},
        state=incidental_state,
        parsed={"updates": [], "events": [{
            "event_type": "artifact_offered", "subject": "optional appendix",
            "status": "proposed", "actor_id": "owner", "task_critical": False,
            "criticality_reason": "optional follow-up",
            "summary": "Owner offers an optional appendix.",
            "evidence": [{"speaker_id": "owner", "quote": "I can draft an optional appendix later"}],
        }]},
        characters=[owner], player_text="",
        npc_turns=[{"speaker_id": "owner", "content": "I can draft an optional appendix later."}],
        turn_id=1,
    )
    assert incidental_state["work_items"]["optional_appendix"].get("required") is not True
    assert prepare_turn_governance(
        incidental_state, characters=[owner], turn_id=2,
        safety_max_turns=10, max_stagnant_turns=6,
    )["progress"]["focus"] is None

    # A side issue cannot promote itself into a new completion prerequisite in
    # a schema-driven task just by using the word "blocked".
    scoped_state = initial_task_state(accepted_config)
    apply_evaluator_updates(
        task_config=accepted_config, state=scoped_state,
        parsed={"updates": [], "events": [{
            "event_type": "blocker", "subject": "optional liability appendix",
            "status": "blocked", "actor_id": "supplier_ceo",
            "task_critical": True,
            "criticality_reason": "called a blocker",
            "evidence": [{
                "speaker_id": "supplier_ceo",
                "quote": "The optional liability appendix is blocked.",
            }],
        }]},
        characters=[supplier], player_text="",
        npc_turns=[{
            "speaker_id": "supplier_ceo",
            "content": "The optional liability appendix is blocked.",
        }], turn_id=1,
    )
    assert scoped_state["work_items"]["optional_liability_appendix"].get("required") is not True

    # A blocked item can lead for two turns, then rotates to another critical
    # state instead of monopolizing the rest of the meeting.
    rotation_state = initial_task_state(cross_turn_config)
    rotation_state["work_items"] = {
        "blocked_report": {
            "required": True, "status": "blocked", "owner_id": "owner",
            "target_id": "", "subject": "blocked report",
        }
    }
    first_rotation = prepare_turn_governance(
        rotation_state, characters=[owner], turn_id=1,
        safety_max_turns=10, max_stagnant_turns=6,
    )
    second_rotation = prepare_turn_governance(
        first_rotation, characters=[owner], turn_id=2,
        safety_max_turns=10, max_stagnant_turns=6,
    )
    third_rotation = prepare_turn_governance(
        second_rotation, characters=[owner], turn_id=3,
        safety_max_turns=10, max_stagnant_turns=6,
    )
    assert first_rotation["progress"]["focus"]["issue"] == "work:blocked_report"
    assert second_rotation["progress"]["focus"]["issue"] == "work:blocked_report"
    assert third_rotation["progress"]["focus"]["issue"] == "outcome"
    assert third_rotation["progress"]["focus"]["kind"] == "state_variable"
    assert third_rotation["progress"]["focus"]["rotated_from_issue"] == "work:blocked_report"

    # State variables are also bounded.  With an alternative, focus rotates;
    # with only one unresolved field, the third turn requires honest outcome
    # resolution instead of repeating the same proposal indefinitely.
    two_field_config = {
        "state_schema": {
            "first": {"type": "boolean"},
            "second": {"type": "boolean"},
        },
        "phases": [{"phase_id": "active"}],
        "completion_conditions": {"all": []},
    }
    two_field_state = initial_task_state(two_field_config)
    first_state_focus = prepare_turn_governance(
        two_field_state, characters=[owner], turn_id=1,
        safety_max_turns=10, max_stagnant_turns=6,
    )
    second_state_focus = prepare_turn_governance(
        first_state_focus, characters=[owner], turn_id=2,
        safety_max_turns=10, max_stagnant_turns=6,
    )
    rotated_state_focus = prepare_turn_governance(
        second_state_focus, characters=[owner], turn_id=3,
        safety_max_turns=10, max_stagnant_turns=6,
    )["progress"]["focus"]
    assert rotated_state_focus["issue"] == "second"
    assert rotated_state_focus["rotated_from_issue"] == "first"

    sole_state = initial_task_state(config)
    sole_first = prepare_turn_governance(
        sole_state, characters=[owner], turn_id=1,
        safety_max_turns=10, max_stagnant_turns=6,
    )
    sole_second = prepare_turn_governance(
        sole_first, characters=[owner], turn_id=2,
        safety_max_turns=10, max_stagnant_turns=6,
    )
    sole_resolution = prepare_turn_governance(
        sole_second, characters=[owner], turn_id=3,
        safety_max_turns=10, max_stagnant_turns=6,
    )["progress"]["focus"]
    assert sole_resolution["kind"] == "outcome_resolution"
    assert sole_resolution["origin_focus_issue"] == "outcome"
    promised_signature = task_progress_signature(event_state)
    apply_evaluator_updates(
        task_config={"state_schema": {}, "phases": [{"phase_id": "active"}], "completion_conditions": {"all": []}},
        state=event_state,
        parsed={"updates": [], "events": [{
            "event_type": "artifact_offered", "subject": "capacity evidence",
            "status": "proposed", "actor_id": "owner",
            "summary": "Same promise again.",
            "evidence": [{"speaker_id": "owner", "quote": "I will send the capacity evidence"}],
        }]},
        characters=[owner], player_text="",
        npc_turns=[{"speaker_id": "owner", "content": "I will send the capacity evidence."}],
    )
    assert task_progress_signature(event_state) == promised_signature
    submitted_intent = validate_public_intent(
        character=owner,
        state=event_state,
        turn_id=4,
        intent={
            "kind": "artifact", "subject": "capacity evidence",
            "transition": "submitted", "simulation_scope": "in_session",
            "inline_content": "Capacity: 5,200 units monthly.",
        },
    )
    commit_public_intent(
        event_state, intent=submitted_intent,
        public_quote="Here is the capacity evidence: 5,200 units monthly.", tick=1,
    )
    apply_evaluator_updates(
        task_config={"state_schema": {}, "phases": [{"phase_id": "active"}], "completion_conditions": {"all": []}},
        state=event_state,
        parsed={"updates": [], "events": [{
            "event_type": "artifact_submitted", "subject": "capacity evidence",
            "status": "completed", "actor_id": "owner",
            "summary": "Capacity evidence delivered with figures.",
            "evidence": [{"speaker_id": "owner", "quote": "Here is the capacity evidence"}],
        }]},
        characters=[owner], player_text="",
        npc_turns=[{"speaker_id": "owner", "content": "Here is the capacity evidence: 5,200 units monthly."}],
    )
    assert event_state["work_items"]["capacity_evidence"]["status"] == "submitted"
    assert task_progress_signature(event_state) != promised_signature
    submitted_signature = task_progress_signature(event_state)
    verified_intent = validate_public_intent(
        character=owner,
        state=event_state,
        turn_id=5,
        intent={
            "kind": "artifact", "subject": "capacity evidence",
            "transition": "verified", "simulation_scope": "in_session",
            "value": "Reviewed capacity: 5,200 units monthly.",
            "inline_content": "Reviewed capacity: 5,200 units monthly.",
        },
    )
    commit_public_intent(
        event_state, intent=verified_intent,
        public_quote="I reviewed the capacity evidence: 5,200 units monthly.", tick=1,
    )
    apply_evaluator_updates(
        task_config={"state_schema": {}, "phases": [{"phase_id": "active"}], "completion_conditions": {"all": []}},
        state=event_state,
        parsed={"updates": [], "events": [{
            "event_type": "artifact_reviewed", "subject": "capacity evidence details",
            "work_item_key": "capacity_evidence", "status": "completed", "actor_id": "owner",
            "summary": "Capacity evidence reviewed.",
            "evidence": [{"speaker_id": "owner", "quote": "I reviewed the capacity evidence"}],
        }]},
        characters=[owner], player_text="",
        npc_turns=[{"speaker_id": "owner", "content": "I reviewed the capacity evidence."}],
    )
    assert event_state["work_items"]["capacity_evidence"]["status"] == "completed"
    assert task_progress_signature(event_state) != submitted_signature

    invalid_review_state = initial_task_state({
        "state_schema": {}, "phases": [{"phase_id": "active"}],
        "completion_conditions": {"all": []},
    })
    apply_evaluator_updates(
        task_config={"state_schema": {}, "phases": [{"phase_id": "active"}], "completion_conditions": {"all": []}},
        state=invalid_review_state,
        parsed={"updates": [], "events": [{
            "event_type": "artifact_reviewed", "subject": "unsubmitted report",
            "status": "completed", "actor_id": "owner",
            "summary": "Claims to review a missing report.",
            "evidence": [{"speaker_id": "owner", "quote": "I reviewed the report"}],
        }]},
        characters=[owner], player_text="",
        npc_turns=[{"speaker_id": "owner", "content": "I reviewed the report."}],
    )
    assert "unsubmitted_report" not in invalid_review_state["work_items"]
    assert invalid_review_state["event_ledger"][-1]["transition_valid"] is False

    # Executable state cannot be confirmed by speech alone. It becomes
    # confirmable only after the corresponding public action is verified.
    executor = SimpleNamespace(
        character_id="executor",
        authority={"can_confirm": ["containment_active"], "can_execute": ["containment_active"]},
    )
    executable_config = {
        "state_schema": {
            "containment_active": {
                "type": "boolean", "confirmation_policy": "responsible_participant",
            }
        },
        "phases": [{"phase_id": "active"}],
        "completion_conditions": {"all": [{
            "field": "containment_active", "operator": "==", "value": True,
        }]},
    }
    executable_state = initial_task_state(executable_config)
    capability_focus = prepare_turn_governance(
        executable_state, characters=[executor], turn_id=1,
        safety_max_turns=10, max_stagnant_turns=6,
    )["progress"]["focus"]
    assert capability_focus["kind"] == "capability_boundary"
    assert capability_focus["tool_result_required"] is True
    assert capability_focus["tool_result_available"] is False
    assert "not available" in capability_focus["instruction"]
    persisted_boundary = prepare_turn_governance(
        {**executable_state, "capability_boundaries": {
            "containment_active": {
                "field": "containment_active", "status": "unavailable",
                "first_observed_turn": 1,
            },
        }},
        characters=[executor], turn_id=2,
        safety_max_turns=10, max_stagnant_turns=6,
    )
    assert persisted_boundary["progress"]["focus"] is None
    reconcile_capability_boundary_closure(
        executable_config, persisted_boundary, turn_id=2,
    )
    assert persisted_boundary["completion_status"] == "conditional"
    assert persisted_boundary["outcome"]["unmet_conditions"] == ["containment_active"]
    claimed_update = {
        "updates": [{
            "field": "containment_active", "value": True, "status": "confirmed",
            "confirmed_by": ["executor"],
            "evidence": [{"speaker_id": "executor", "quote": "Containment is active"}],
        }]
    }
    apply_evaluator_updates(
        task_config=executable_config, state=executable_state, parsed=claimed_update,
        characters=[executor], player_text="",
        npc_turns=[{"speaker_id": "executor", "content": "Containment is active."}],
        turn_id=1,
    )
    assert executable_state["variables"]["containment_active"]["status"] == "proposed"
    record_simulated_tool_result(
        executable_state, result_id="sim-tool-1", actor_id="executor",
        field="containment_active", inline_content="Traffic isolation command executed.",
        turn_id=2,
    )
    executable_state["coordination_history"] = []
    available_focus = prepare_turn_governance(
        executable_state, characters=[executor], turn_id=2,
        safety_max_turns=10, max_stagnant_turns=6,
    )["progress"]["focus"]
    assert available_focus["kind"] == "state_variable"
    assert available_focus["tool_result_available"] is True
    submitted_action = validate_public_intent(
        character=executor, state=executable_state, turn_id=2,
        intent={
            "kind": "action", "subject": "activate containment",
            "field": "containment_active", "transition": "submitted",
            "simulation_scope": "in_session", "inline_content": "Traffic isolation command executed.",
            "evidence_source": "simulated_tool_result", "tool_result_id": "sim-tool-1",
        },
    )
    unsupported_action = validate_public_intent(
        character=executor, state=executable_state, turn_id=2,
        intent={
            "kind": "action", "subject": "activate containment",
            "field": "containment_active", "transition": "submitted",
            "simulation_scope": "in_session", "inline_content": "I say it ran.",
            "evidence_source": "public_statement",
        },
    )
    assert unsupported_action["transition"] == "committed"
    assert unsupported_action["validation_reason"] == "action_completion_requires_simulated_tool_result"
    invented_tool_action = validate_public_intent(
        character=executor, state=executable_state, turn_id=2,
        intent={
            "kind": "action", "subject": "activate containment",
            "field": "containment_active", "transition": "submitted",
            "simulation_scope": "in_session", "inline_content": "Invented result.",
            "evidence_source": "simulated_tool_result", "tool_result_id": "invented-id",
        },
    )
    assert invented_tool_action["transition"] == "committed"
    assert "unregistered_simulated_tool_result" in invented_tool_action["validation_reason"]
    commit_public_intent(
        executable_state, intent=submitted_action,
        public_quote="Traffic isolation command executed.", tick=1,
    )
    record_simulated_tool_result(
        executable_state, result_id="sim-tool-2", actor_id="executor",
        field="containment_active",
        inline_content="Isolation verified from the stated traffic result.",
        turn_id=3,
    )
    verified_action = validate_public_intent(
        character=executor, state=executable_state, turn_id=3,
        intent={
            "kind": "action", "subject": "activate containment",
            "field": "containment_active", "transition": "verified",
            "value": True,
            "simulation_scope": "in_session", "inline_content": "Isolation verified from the stated traffic result.",
            "evidence_source": "simulated_tool_result", "tool_result_id": "sim-tool-2",
        },
    )
    commit_public_intent(
        executable_state, intent=verified_action,
        public_quote="Isolation is verified from the stated traffic result.", tick=1,
    )
    apply_evaluator_updates(
        task_config=executable_config, state=executable_state, parsed=claimed_update,
        characters=[executor], player_text="",
        npc_turns=[{"speaker_id": "executor", "content": "Containment is active."}],
        turn_id=3,
    )
    assert executable_state["variables"]["containment_active"]["status"] == "confirmed"
    assert executable_state["completion_status"] == "completed"

    info_state = initial_task_state({
        "state_schema": {}, "phases": [{"phase_id": "active"}],
        "completion_conditions": {"all": []},
    })
    apply_evaluator_updates(
        task_config={"state_schema": {}, "phases": [{"phase_id": "active"}], "completion_conditions": {"all": []}},
        state=info_state,
        parsed={"updates": [], "events": [{
            "event_type": "information_provided", "subject": "service impact details",
            "status": "completed", "actor_id": "owner",
            "summary": "Impact facts provided.",
            "evidence": [{"speaker_id": "owner", "quote": "The outage affects payment traffic"}],
        }]},
        characters=[owner], player_text="",
        npc_turns=[{"speaker_id": "owner", "content": "The outage affects payment traffic only."}],
    )
    assert info_state["work_items"]["service_impact"]["status"] == "completed"

    closure_state = initial_task_state(cross_turn_config)
    closure_state["variables"]["outcome"].update(value=True, status="proposed")
    apply_evaluator_updates(
        task_config=cross_turn_config, state=closure_state,
        parsed={"updates": [], "events": []}, characters=[owner],
        player_text="The meeting is now adjourned.", npc_turns=[],
    )
    assert closure_state["completion_status"] == "deferred"
    assert closure_state["outcome"]["status"] == "explicit_closure"
    set_progress_metadata(event_state, stagnant_turns=3, turn_id=7, progress_made=False)
    assert public_task_result(event_state)["progress"]["stagnant_turns"] == 3
    stalled = finalize_stalled_task_state(event_state, turn_id=10)
    assert stalled["completion_status"] == "stalled"
    assert stalled["outcome"]["type"] == "stalled"

    pending = pending_public_questions([
        {"speaker_id": "user", "speaker_type": "user", "content": "Please advise."},
        {"speaker_id": "first", "speaker_type": "npc", "content": "Can you provide the evidence?"},
        {"speaker_id": "second", "speaker_type": "npc", "content": "What decision do you recommend?"},
    ])
    assert [row["speaker_id"] for row in pending] == ["first", "second"]
    long_pending = pending_public_questions([
        {"speaker_id": "user", "speaker_type": "user", "content": "Please advise."},
        {
            "speaker_id": "lead", "speaker_type": "npc",
            "content": "x" * 800 + ". Can you confirm the bounded decision now?",
        },
    ])
    assert long_pending == [{
        "speaker_id": "lead",
        "question": "Can you confirm the bounded decision now?",
    }]

    chars = [
        SimpleNamespace(character_id="first", display_name="First", character_name="First", job_title="Lead", aliases=[], sort_order=0),
        SimpleNamespace(character_id="second", display_name="Second", character_name="Second", job_title="Advisor", aliases=[], sort_order=1),
    ]
    assert orch_support.match_mentioned_characters("Second, answer before First.", chars) == ["second", "first"]
    assert [
        char.character_id for char in generative_orchestrator._agent_order(
            chars, [], [], ["second"]
        )
    ] == ["second", "first"]
    print("NPC speech safety and task-state smoke test: ok")


if __name__ == "__main__":
    main()
