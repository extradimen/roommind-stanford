"""Independent expected event traces for the shared virtual world contract."""
import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.world.executor import KEY, SCHEMA, execute, prompt, request_execution


def config():
    return {"simulation_executor": {"schema": SCHEMA,
        "initial_facts": {"evidence_preserved": False},
        "actions": {
            "preserve": {"actors": ["security"], "field": "evidence_preserved", "value": True},
            "contain": {"actors": ["sre"], "field": "containment_active", "value": True,
                        "requires": {"evidence_preserved": True}},
            "recover": {"actors": ["sre"], "field": "recovered", "value": True,
                        "requires": {"containment_active": True}, "outcome": "failed"},
        }}}


class ExecutorTests(unittest.TestCase):
    def test_trace_permissions_prerequisites_failure_and_restart(self):
        cfg, state = config(), {}
        events = [("sre", "a", "contain", "blocked"),
                  ("other", "b", "preserve", "blocked"),
                  ("security", "c", "preserve", "success"),
                  ("sre", "d", "contain", "success"),
                  ("sre", "e", "recover", "failed")]
        for actor, rid, operation, expected in events:
            row = execute(cfg, state, actor_id=actor, turn_id=1,
                          request={"request_id": rid, "operation": operation})
            self.assertEqual(row["status"], expected)
            state = json.loads(json.dumps(state))  # Persist/reload between every event.
        self.assertEqual(state[KEY]["facts"], {"evidence_preserved": True, "containment_active": True})
        before = copy.deepcopy(state)
        execute(cfg, state, actor_id="sre", turn_id=99,
                request={"request_id": "d", "operation": "contain"})
        self.assertEqual(state, before)

    def test_id_collision_and_contract_drift_cannot_rewrite_result(self):
        cfg, state = config(), {}
        execute(cfg, state, actor_id="security", turn_id=1,
                request={"request_id": "a", "operation": "preserve"})
        before = copy.deepcopy(state)
        with self.assertRaises(ValueError):
            execute(cfg, state, actor_id="security", turn_id=2,
                    request={"request_id": "a", "operation": "contain"})
        self.assertEqual(state, before)
        cfg["simulation_executor"]["initial_facts"]["evidence_preserved"] = True
        with self.assertRaises(ValueError):
            request_execution(cfg, state, actor_id="security", turn_id=2, request={})
        self.assertEqual(state, before)

    def test_same_contract_and_sequence_produce_identical_condition_results(self):
        states = [{}, {}]
        for state in states:
            for actor, operation in [("security", "preserve"), ("sre", "contain")]:
                execute(config(), state, actor_id=actor, turn_id=1,
                        request={"request_id": operation, "operation": operation})
        self.assertEqual(states[0], states[1])
        self.assertEqual(prompt(config(), states[0], "sre"), prompt(config(), states[1], "sre"))

    def test_malformed_request_has_no_execution_effect(self):
        state = {}
        result = request_execution(config(), state, actor_id="sre", request={}, turn_id=1)
        self.assertEqual(result["status"], "blocked")
        self.assertNotIn(KEY, state)
        self.assertEqual(len(state["simulation_request_rejections"]), 1)

    def test_disabled_and_unknown_actions_do_not_create_success(self):
        self.assertEqual(prompt({}, {}, "sre"), "")
        result = request_execution({}, {}, actor_id="sre", request={}, turn_id=1)
        self.assertEqual(result["status"], "blocked")
        result = execute(config(), {}, actor_id="sre", turn_id=1,
                         request={"request_id": "x", "operation": "shell"})
        self.assertEqual(result["reason"], "unknown_operation")

    def test_missing_or_wrong_type_prerequisite_is_not_satisfied(self):
        cfg = config()
        for initial, required in [({}, None), ({"evidence_preserved": 1}, True)]:
            cfg["simulation_executor"]["initial_facts"] = initial
            cfg["simulation_executor"]["actions"]["contain"]["requires"] = {"evidence_preserved": required}
            row = execute(cfg, {}, actor_id="sre", turn_id=1,
                          request={"request_id": "typed", "operation": "contain"})
            self.assertEqual(row["status"], "blocked")

    def test_parameters_are_declared_and_cannot_control_outcome(self):
        row = execute(config(), {}, actor_id="security", turn_id=1,
                      request={"request_id": "forged", "operation": "preserve",
                               "parameters": {"outcome": "success"}})
        self.assertEqual(row["reason"], "invalid_parameters")


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_versioned_incident_can_reach_containment_through_registered_results(self):
        from app.agent.act import AgentDecision, execute_decision
        from app.models.db import CharacterTemplate
        from app.task_state import refresh_task_state_from_public_ledger
        path = Path(__file__).resolve().parents[2] / "research/scenario-designs/world-v2/incident-response-command-world-v2.json"
        snapshot = json.loads(path.read_text())
        characters = [CharacterTemplate(character_id=row["character_id"],
                      display_name=row["character_name"], character_name=row["character_name"],
                      authority=row["authority"], private_state=row["private_state"])
                      for row in snapshot["characters"]]
        by_id = {row.character_id: row for row in characters}
        state = {}
        with patch("app.agent.act._record_action_memory", new=AsyncMock()):
            for turn, (actor, operation) in enumerate([
                ("sre_lead", "diagnose_scope"), ("security_lead", "preserve_evidence"),
                ("sre_lead", "activate_containment")], 1):
                result = await execute_decision(
                    None, character=by_id[actor], store=None, nodes=[],
                    decision=AgentDecision(action="execute", simulation_action={
                        "request_id": operation, "operation": operation}),
                    user_input="", turn_id=turn, tick=0, conversation_context="", npc_llm=None,
                    speak_quota_remaining=1, mentioned=True,
                    task_state=state, task_config=snapshot["task_config"])
                self.assertEqual(result.public_intent["simulation_receipt"]["status"], "success")
                refresh_task_state_from_public_ledger(snapshot["task_config"], state, characters)
        self.assertEqual(state[KEY]["facts"]["containment_active"], True)
        self.assertEqual(state["variables"]["containment_active"]["status"], "confirmed")
        self.assertEqual(len(state["public_ledger"]["tool_results"]), 3)
        self.assertNotEqual(state.get("completion_status"), "completed")

    async def test_terminal_restart_prevents_model_calls_and_execution(self):
        from app.orchestrator.generative import generative_orchestrator
        from app.agent.act import AgentDecision, execute_decision
        state = {"completion_status": "completed"}
        with patch("app.orchestrator.generative.orch_support.get_llm_config", new=AsyncMock()) as model_config:
            events = [row async for row in generative_orchestrator.process_turn_stream(
                None, session_id=1, scenario=None, characters=[SimpleNamespace(character_id="sre")],
                dispatch_rules=[], user_input="Continue", messages=[], current_phase="closed",
                shared_state={"task_state": state, "_pending_responses": ["sre"]},
                orchestration_config=None, user_turn_count=2)]
            model_config.assert_not_awaited()
        self.assertEqual(events[-1]["replies"], [])
        result = await execute_decision(
            None, character=SimpleNamespace(character_id="sre"), store=None, nodes=[],
            decision=AgentDecision(action="execute", simulation_action={}),
            user_input="Continue", turn_id=2, tick=0, conversation_context="",
            npc_llm=None, speak_quota_remaining=1, mentioned=True,
            task_state=state, task_config=config())
        self.assertFalse(result.spoke)
        self.assertEqual(state, {"completion_status": "completed"})
        from app.agent.act import execute_plan_fallback_speak
        fallback = await execute_plan_fallback_speak(
            None, character=None, scenario=None, store=None, nodes=[], user_input="Continue",
            turn_id=2, tick=0, conversation_context="", current_phase="closed",
            npc_llm=None, timeline=None, task_state=state)
        self.assertIsNone(fallback)

    async def test_real_adapters_share_receipt_and_roommind_registers_evidence(self):
        from app.agent.act import AgentDecision, execute_decision
        from app.baseline_chat import generate_baseline_turn
        from app.models.db import CharacterTemplate, GameSession, ScenarioTemplate

        cfg = config()
        cfg["state_schema"] = {"evidence_preserved": {
            "type": "boolean", "confirm_permissions": ["security"],
            "propose_permissions": ["security"], "confirmation_policy": "responsible_participant"}}
        character = CharacterTemplate(character_id="security", character_name="Security",
            job_title="Security", sort_order=0, authority={
                "can_execute": ["evidence_preserved"], "can_confirm": ["evidence_preserved"]})
        scenario = ScenarioTemplate(title="Virtual execution test", description="Test",
                                    task_config=cfg, characters=[character])
        session = GameSession(run_config={}, shared_state={}, current_phase="triage")
        request = {"request_id": "same-request", "operation": "preserve"}
        binding = SimpleNamespace(provider="test", model="test", temperature=0,
                                  max_tokens=1000, label=lambda: "test/test")
        with patch("app.baseline_chat.orch_support.get_llm_config", new=AsyncMock(return_value={})), \
             patch("app.baseline_chat.resolve_llm", return_value=binding), \
             patch("app.baseline_chat.llm_client.chat_completion", new=AsyncMock(return_value=json.dumps({
                 "action": "execute", "simulation_action": request}))), \
             patch("app.baseline_chat.orch_support.parse_json", side_effect=json.loads):
            baseline = await generate_baseline_turn(None, session, scenario, [
                {"speaker_id": "user", "speaker_type": "user", "content": "Preserve evidence."}])
        state = {}
        with patch("app.agent.act._record_action_memory", new=AsyncMock()):
            roommind = await execute_decision(
                None, character=character, store=None, nodes=[],
                decision=AgentDecision(action="execute", simulation_action=request),
                user_input="Preserve evidence.", turn_id=1, tick=0,
                conversation_context="", npc_llm=binding, speak_quota_remaining=1,
                mentioned=True, task_state=state, task_config=cfg)
        self.assertEqual(roommind.content, baseline.replies[0]["content"])
        self.assertEqual(state[KEY], session.shared_state["_baseline_simulation"][KEY])
        self.assertEqual(roommind.public_intent["simulation_receipt"]["status"], "success")
        self.assertEqual(len(state["public_ledger"]["tool_results"]), 1)
        self.assertIsNotNone(roommind.public_ledger_event)
        self.assertNotIn("task_state", session.shared_state)


if __name__ == "__main__":
    unittest.main()
