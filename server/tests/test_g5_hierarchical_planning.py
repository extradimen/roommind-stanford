"""Long-horizon engineering acceptance with synthetic memories and model output."""
import copy
import json
import unittest

from app.factorial_study import digest
from app.g5.memory import MemoryCognition
from app.g5.model_cognition import ModelCognitionGenerator
from app.g5.model_policy import ModelBinding, Completion
from app.g5.planning import required_goal_statuses, validate
from app.g5.reflection import ReflectiveCognition
from test_g5_reflection import view


def step(key, actor, sources, *, intent="ask", parent="root", text="Can we proceed?", **updates):
    return {"id": key, "actor": actor, "source_ids": sources, "parent": parent,
            "depends_on": [], "intent": intent, "text": text, "operation": "",
            "status": "planned", "status_source_ids": [], **updates}


def plan(actor, sources, operations=("contain",)):
    return {"goal": "Resolve a delayed commitment without inventing completion", "steps": [
        step("root", actor, sources, intent="goal", parent=None),
        step("ask", actor, sources),
        step("execute", actor, sources, intent="execute" if "contain" in operations else "wait",
             operation="contain" if "contain" in operations else "", depends_on=["ask"])]}


class Script:
    def __init__(self, mode="hold", top_k=1, updates=False):
        self.calls = []
        self.fail = False
        async def transport(request):
            self.calls.append(copy.deepcopy(request))
            if self.fail:
                raise TimeoutError("offline planning failure")
            context = json.loads(request["messages"][1]["content"])
            previous = context.get("previous_plan")
            proposal = copy.deepcopy(previous["proposal"]) if previous else plan(
                context["actor"], [context["memory"]["retrieved"][0]["id"]], context["operations"])
            if mode == "progress" and previous:
                for node in context["memory"]["retrieved"]:
                    if node["kind"] not in {"claim", "simulation_receipt"}:
                        continue
                    observation = json.loads(node["text"])
                    if observation.get("actor") != context["actor"]:
                        continue
                    if node["kind"] == "claim" and observation.get("content") == "Can we proceed?":
                        proposal["steps"][1].update(status="completed", status_source_ids=[node["id"]])
                    if node["kind"] == "simulation_receipt" and observation["receipt"]["status"] == "success":
                        proposal["steps"][2].update(status="completed", status_source_ids=[node["id"]])
                if all(r["status"] == "completed" for r in proposal["steps"][1:]):
                    proposal["steps"][0]["status"] = "completed"
            if mode == "defer":
                proposal["steps"][0]["status"] = "deferred"
                proposal["steps"][1].update(status="deferred", status_source_ids=proposal["steps"][1]["source_ids"])
            body = {"goal": proposal["goal"], "updates": proposal["steps"]} if updates else proposal
            return Completion(json.dumps(body), "offline", "fixed", "mock", digest(request), "stop")
        async def reflect(context):
            return []
        self.cognition = ReflectiveCognition(memory=MemoryCognition(top_k=top_k), reflector=reflect,
            planner=ModelCognitionGenerator("hierarchical_updates" if updates else "hierarchical_planning",
                ModelBinding("offline", "fixed", "mock", 0.2, 4096), transport),
            reflector_id="no-hypotheses-offline", planner_id="synthetic-hierarchy-v1", hierarchical=True, plan_updates=updates)


def session_hierarchy_options(world, arm):
    from test_g5_reopening import options
    from app.factorial_study import ARMS, freeze_design
    from app.g5.components import specification
    harness, state, args = options(world, arm)
    script = Script(updates=True)
    hierarchy = ReflectiveCognition(memory=harness.cognition.memory, reflector=harness.cognition.reflector,
        planner=script.cognition.planner, reflector_id="fixed-reflect", planner_id="synthetic-hierarchy-v1",
        hierarchical=True, plan_updates=True)
    design = args["manifest"]["design"]
    design["components"]["cognition"] = specification(hierarchy)
    for profile in design["arms"].values():
        profile["shared"]["model_bindings_sha256"] = digest(design["components"])
    args["manifest"] = freeze_design(design)
    args["cognition"] = hierarchy if ARMS[arm]["cognition"] else None
    return harness, state, script, args


class HierarchyTests(unittest.IsolatedAsyncioTestCase):
    async def test_exhausted_update_repairs_conservatively_preserve_existing_plan(self):
        source = view()
        requests = []

        async def reflector(context): return []

        async def transport(request):
            context = json.loads(request["messages"][1]["content"])
            requests.append(context)
            if context["previous_plan"] is None:
                proposal = plan(context["actor"], [context["memory"]["retrieved"][0]["id"]],
                                context["operations"])
                body = {"goal": proposal["goal"], "updates": proposal["steps"]}
            else:
                old = copy.deepcopy(context["previous_plan"]["proposal"]["steps"][0])
                old["text"] = "invalid identity replacement"
                body = {"goal": context["previous_plan"]["proposal"]["goal"],
                        "updates": [old]}
            return Completion(json.dumps(body), "offline", "fixed", "mock",
                              digest(request), "stop")

        adapter = ReflectiveCognition(memory=MemoryCognition(top_k=8), reflector=reflector,
            planner=ModelCognitionGenerator("hierarchical_updates",
                ModelBinding("offline", "fixed", "mock", .2, 4096), transport),
            reflector_id="none", planner_id="fallback-recovery", hierarchical=True,
            plan_updates=True, max_plan_revisions=2)
        initial = await adapter(source)
        source["cognition_state"] = initial
        source["observations"].append({"event_id": "changed", "kind": "claim",
            "actor": "security", "content": "The scope changed."})
        requests.clear()
        result = await adapter(source)
        self.assertEqual(len(requests), 3)
        self.assertEqual(result["plans"][-1]["update_proposal"], {
            "goal": initial["plans"][-1]["proposal"]["goal"], "updates": []})
        self.assertEqual(result["plans"][-1]["proposal"],
                         initial["plans"][-1]["proposal"])
        rejected = [row for row in result["generation_receipts"]
                    if row["stage"] == "structured_rejected"]
        self.assertEqual(len(rejected), 3)
        self.assertEqual(adapter.runtime_specification()["plan_repair_exhaustion"], {
            "schema": "g5-conservative-plan-repair-exhaustion-v1",
            "action": "preserve-existing-plan", "requires_previous_plan": True})

    async def test_identity_then_retroactive_completion_use_exact_recovery_contract(self):
        source = view()
        requests = []

        async def reflector(context): return []

        async def transport(request):
            context = json.loads(request["messages"][1]["content"])
            requests.append(context)
            if context["previous_plan"] is None:
                proposal = plan(context["actor"], [context["memory"]["retrieved"][0]["id"]],
                                context["operations"])
                return Completion(json.dumps({"goal": proposal["goal"], "updates": proposal["steps"]}),
                                  "offline", "fixed", "mock", digest(request), "stop")
            revision = len([row for row in requests if row["previous_plan"] is not None]) - 1
            if revision == 0:
                old = copy.deepcopy(context["previous_plan"]["proposal"]["steps"][0])
                old["text"] = "silently changed identity"
                updates = [old]
            elif revision == 1:
                source_id = context["memory"]["retrieved"][0]["id"]
                updates = [step("invented-complete", context["actor"], [source_id],
                                status="completed", status_source_ids=[source_id])]
            else:
                updates = []
            return Completion(json.dumps({"goal": context["previous_plan"]["proposal"]["goal"],
                                          "updates": updates}),
                              "offline", "fixed", "mock", digest(request), "stop")

        adapter = ReflectiveCognition(memory=MemoryCognition(top_k=8), reflector=reflector,
            planner=ModelCognitionGenerator("hierarchical_updates",
                ModelBinding("offline", "fixed", "mock", .2, 4096), transport),
            reflector_id="none", planner_id="identity-recovery", hierarchical=True,
            plan_updates=True, max_plan_revisions=2)
        initial = await adapter(source)
        source["cognition_state"] = initial
        source["observations"].append({"event_id": "changed", "kind": "claim",
            "actor": "security", "content": "The scope changed."})
        requests.clear()
        result = await adapter(source)
        self.assertEqual(len(requests), 3)
        first = requests[1]["validation_feedback"]
        second = requests[2]["validation_feedback"]
        self.assertEqual(first["error"]["error_code"], "identity")
        self.assertTrue(first["allowed_values"]["mutable_existing_tasks"])
        self.assertTrue(all(set(row) == {"id", "parent", "depends_on", "actor", "intent",
                                        "text", "operation", "source_ids"}
                            for row in first["allowed_values"]["mutable_existing_tasks"]))
        self.assertTrue(all(not ids for ids in
                            first["allowed_values"]["completion_source_ids_by_task"].values()))
        self.assertEqual(first["allowed_values"]["required_goal_status_by_id"], {})
        self.assertEqual(first["allowed_values"]["terminal_task_ids"], [])
        self.assertEqual(first["allowed_values"]["actor"], "sre")
        self.assertEqual(first["allowed_values"]["operations"], ["contain"])
        self.assertEqual(first["allowed_values"]["safe_no_change_update"], {
            "goal": initial["plans"][-1]["proposal"]["goal"], "updates": []})
        self.assertEqual(second["error"]["field_path"], "$.updates[*].status")
        self.assertEqual(second["allowed_values"]["new_task_initial_status"], ["planned"])
        self.assertEqual(result["plans"][-1]["update_proposal"]["updates"], [])

    async def test_v5_missing_transition_evidence_is_repaired_with_allowed_source(self):
        source = view()
        requests = []

        async def reflector(context):
            return []

        async def transport(request):
            context = json.loads(request["messages"][1]["content"])
            requests.append(context)
            if context["previous_plan"] is None:
                proposal = plan(context["actor"], [context["memory"]["retrieved"][0]["id"]],
                                context["operations"])
                body = {"goal": proposal["goal"], "updates": proposal["steps"]}
                return Completion(json.dumps(body), "offline", "fixed", "mock", digest(request), "stop")
            ask = copy.deepcopy(next(row for row in context["previous_plan"]["proposal"]["steps"]
                                     if row["id"] == "ask"))
            ask["status"] = "completed"
            ask["status_source_ids"] = []
            if "validation_feedback" in context:
                observed = next(row["id"] for row in context["memory"]["retrieved"]
                                if "Can we proceed?" in row["text"])
                ask["status_source_ids"] = [observed]
            body = {"goal": context["previous_plan"]["proposal"]["goal"], "updates": [ask]}
            return Completion(json.dumps(body), "offline", "fixed", "mock", digest(request), "stop")

        adapter = ReflectiveCognition(memory=MemoryCognition(top_k=8), reflector=reflector,
            planner=ModelCognitionGenerator("hierarchical_updates",
                ModelBinding("offline", "fixed", "mock", .2, 4096), transport),
            reflector_id="none", planner_id="v5-regression", hierarchical=True,
            plan_updates=True, max_plan_revisions=2)
        initial = await adapter(source)
        source["cognition_state"] = initial
        source["observations"].append({"event_id": "own-question", "kind": "claim",
            "actor": "sre", "content": "Can we proceed?"})
        requests.clear()
        state = await adapter(source)
        self.assertEqual(len(requests), 2)
        error = requests[1]["validation_feedback"]["error"]
        self.assertEqual(error["error_code"], "transition_evidence")
        self.assertEqual(error["field_path"], "$.updates[*].status_source_ids")
        eligible = requests[1]["validation_feedback"]["allowed_values"]["completion_source_ids_by_task"]
        self.assertEqual(len(eligible["ask"]), 1)
        self.assertTrue(state["plans"][-1]["proposal"]["steps"][1]["status_source_ids"])
        rejected = [row["failure"] for row in state["generation_receipts"]
                    if row["stage"] == "structured_rejected"]
        self.assertEqual(len(rejected), 1)
        self.assertIn('"status_source_ids": []', rejected[0]["response_content"])

    async def test_bounded_validation_feedback_repairs_without_inventing_sources(self):
        requests = []
        async def reflect(context):
            return []
        async def transport(request):
            context = json.loads(request["messages"][1]["content"])
            requests.append(context)
            sources = ([context["memory"]["retrieved"][0]["id"]]
                       if "validation_feedback" in context else [])
            body = {"goal": "Keep the plan evidence-bound", "updates": [
                step("root", context["actor"], sources, intent="goal", parent=None),
                step("ask", context["actor"], sources),
            ]}
            return Completion(json.dumps(body), "offline", "fixed", "mock",
                              digest(request), "stop")
        adapter = ReflectiveCognition(memory=MemoryCognition(top_k=1), reflector=reflect,
            planner=ModelCognitionGenerator("hierarchical_updates",
                ModelBinding("offline", "fixed", "mock", .2, 4096), transport),
            reflector_id="none", planner_id="repair-script", hierarchical=True,
            plan_updates=True, max_plan_revisions=2)
        state = await adapter(view())
        self.assertEqual(len(requests), 2)
        self.assertNotIn("validation_feedback", requests[0])
        self.assertEqual(requests[1]["validation_feedback"]["error"]["message"], "Plan source required")
        allowed = requests[1]["validation_feedback"]["allowed_values"]
        self.assertIn("character-for-character", allowed["source_id_copy_rule"])
        self.assertIn("at least one", allowed["new_goal_rule"])
        self.assertEqual(allowed["non_execute_operation"], "")
        self.assertTrue(all(row["source_ids"] for row in state["plans"][-1]["proposal"]["steps"]))
        rejected = [row for row in state["generation_receipts"]
                    if row["stage"] == "structured_rejected"]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["failure"]["message"], "Plan source required")
        self.assertIn("response_content", rejected[0]["failure"])

    async def test_incremental_context_archives_terminal_bodies_without_erasing_history(self):
        requests = []
        async def reflector(context):
            return []
        async def transport(request):
            requests.append(copy.deepcopy(request))
            context = json.loads(request["messages"][1]["content"])
            previous = context.get("previous_plan")
            active = copy.deepcopy(previous["proposal"]["steps"]) if previous else []
            if not active:
                number = previous["terminal_counts"]["completed"] // 2 if previous else 0
                ids = [context["memory"]["retrieved"][0]["id"]]
                active = [step(f"root-{number}", "sre", ids, intent="goal", parent=None),
                          step(f"task-{number}", "sre", ids, parent=f"root-{number}", text=f"Unique commitment {number}.")]
            else:
                task = active[1]
                for node in context["memory"]["retrieved"]:
                    if node["kind"] == "claim":
                        observation = json.loads(node["text"])
                        if observation.get("actor") == "sre" and observation.get("content") == task["text"]:
                            task.update(status="completed", status_source_ids=[node["id"]])
                            active[0]["status"] = "completed"
            return Completion(json.dumps({"goal": "Keep sourced commitments", "updates": active}),
                              "offline", "fixed", "mock", digest(request), "stop")
        def adapter(capacity=4):
            return ReflectiveCognition(memory=MemoryCognition(top_k=1), reflector=reflector,
                planner=ModelCognitionGenerator("hierarchical_updates", ModelBinding("offline", "fixed", "mock", .2, 4096), transport),
                reflector_id="none", planner_id="delta-script", hierarchical=True, plan_updates=True, max_active_tasks=capacity)
        source = view()
        source["observations"] = []
        cognition = adapter()
        state = None
        for number in range(24):
            if state:
                source["cognition_state"] = state
                source["observations"].append({"event_id": f"trigger-{number}", "actor": "security", "kind": "claim", "content": f"Next agenda {number}"})
            state = await cognition(source)
            source["cognition_state"] = state
            source["observations"].append({"event_id": f"spoken-{number}", "actor": "sre", "kind": "claim", "content": f"Unique commitment {number}."})
            state = await cognition(source)
        self.assertEqual(len(state["plans"][-1]["proposal"]["steps"]), 48)
        self.assertEqual(state["context"]["plan"]["proposal"]["steps"], [])
        self.assertEqual(state["context"]["plan"]["terminal_counts"]["completed"], 48)
        self.assertNotIn("Unique commitment 0.", requests[-1]["messages"][1]["content"])
        self.assertTrue(all(len(r["messages"][1]["content"]) < 12000 for r in requests))
        self.assertEqual(len(state["generation_receipts"]), 48)
        source["cognition_state"] = state
        self.assertEqual(await adapter()(source), state)
        fresh = view()
        with self.assertRaises(ValueError):
            await adapter(capacity=1)(fresh)
        self.assertEqual(fresh["cognition_state"], {})

    async def test_delayed_intentions_survive_120_distractors_and_fact_reversal(self):
        script = Script("defer", top_k=1)
        source = view()
        source["observations"] = []
        state = await script.cognition(source)
        first_plan = copy.deepcopy(state["plans"][0])
        old_fact = state["memory"]["nodes"][0]["id"]
        for index in range(120):
            source["cognition_state"] = state
            source["observations"].append({"event_id": f"noise-{index}", "kind": "claim",
                "actor": "security", "content": f"Unrelated discussion item {index}"})
            if index == 60:
                source["facts"]["staffing"] = {"value": "fully staffed", "source": "new-simulation-receipt", "disclosable": True}
            state = await script.cognition(source)
        self.assertEqual(state["plans"][0], first_plan)
        self.assertEqual(state["plans"][-1]["proposal"]["steps"][1]["status"], "deferred")
        retained = next(row for row in state["context"]["retrieved"] if row["id"] == old_fact)
        self.assertTrue(retained["historical_fact"])
        self.assertEqual(retained["retrieval_reason"], "persistent_plan_source")
        self.assertEqual(len(state["memory"]["nodes"]), 122)
        self.assertEqual(len(state["plans"]), 121)
        self.assertEqual(len(state["generation_receipts"]), 121)
        source["cognition_state"] = copy.deepcopy(state)
        reconstructed = Script("defer", top_k=1)
        self.assertEqual(await reconstructed.cognition(source), state)
        self.assertEqual(reconstructed.calls, [])

    async def test_speech_then_receipt_progresses_hierarchy_not_world_facts(self):
        script = Script("progress", top_k=8)
        source = view()
        state = await script.cognition(source)
        source["cognition_state"] = state
        source["observations"].append({"event_id": "own-question", "kind": "claim", "actor": "sre", "content": "Can we proceed?"})
        state = await script.cognition(source)
        self.assertEqual(state["plans"][-1]["proposal"]["steps"][1]["status"], "completed")
        self.assertEqual(state["plans"][-1]["proposal"]["steps"][0]["status"], "planned")
        source["cognition_state"] = state
        source["observations"].append({"event_id": "actual-simulation", "kind": "simulation_receipt", "actor": "sre",
            "receipt": {"operation": "contain", "status": "success", "scope": "simulation_only"}})
        before = copy.deepcopy(source["facts"])
        state = await script.cognition(source)
        self.assertTrue(all(s["status"] == "completed" for s in state["plans"][-1]["proposal"]["steps"]))
        self.assertEqual(source["facts"], before)
        self.assertEqual(state["plans"][-1]["kind"], "intention")

    async def test_structural_and_false_completion_rejections(self):
        source = view()
        state = await Script("hold", top_k=8).cognition(source)
        previous = state["plans"][-1]
        available = {n["id"]: n for n in state["memory"]["nodes"]}
        def check(mutator):
            proposal = copy.deepcopy(previous["proposal"])
            mutator(proposal["steps"])
            with self.assertRaises(ValueError):
                validate(proposal, previous, "sre", ["contain"], available)
        for mutation in (
            lambda s: s.pop(),
            lambda s: s[1].update(actor="security"),
            lambda s: s[1].update(parent="ask"),
            lambda s: s[1].update(depends_on=["execute"]),
            lambda s: s[1].update(source_ids=["hidden-role-source"]),
            lambda s: s[2].update(status="completed", status_source_ids=s[2]["source_ids"]),
            lambda s: s[2].update(status="active", status_source_ids=s[2]["source_ids"]),
            lambda s: s[0].update(status="completed"),
            lambda s: s[2].update(operation="unregistered-upload"),
        ):
            check(mutation)

    def test_required_goal_status_feedback_is_derived_from_children(self):
        proposal = plan("sre", ["source"])
        self.assertEqual(required_goal_statuses(proposal), {"root": "planned"})
        proposal["steps"][1]["status"] = "completed"
        proposal["steps"][2]["status"] = "completed"
        self.assertEqual(required_goal_statuses(proposal), {"root": "completed"})

    async def test_older_receipt_and_other_speaker_cannot_complete_new_intention(self):
        source = view()
        source["observations"].append({"event_id": "old-receipt", "kind": "simulation_receipt", "actor": "sre",
            "receipt": {"operation": "contain", "status": "success"}})
        initial = await Script("hold", top_k=8).cognition(source)
        source["cognition_state"] = initial
        source["observations"].append({"event_id": "later", "kind": "claim", "actor": "security", "content": "Can we proceed?"})
        script = Script("progress", top_k=8)
        with self.assertRaises(ValueError):
            await script.cognition(source)
        self.assertEqual(source["cognition_state"], initial)

    async def test_failure_scope_isolation_and_configuration_drift(self):
        script = Script()
        source = view()
        initial = await script.cognition(source)
        source["cognition_state"] = copy.deepcopy(initial)
        for field, replacement in (("actor", "security"), ("memory_scope", "another-experiment")):
            altered = copy.deepcopy(source)
            altered[field] = replacement
            with self.assertRaises(ValueError):
                await script.cognition(altered)
        script.fail = True
        source["observations"].append({"event_id": "new", "kind": "claim", "actor": "sre", "content": "New evidence"})
        with self.assertRaises(TimeoutError):
            await script.cognition(source)
        self.assertEqual(source["cognition_state"], initial)
        script.cognition.hierarchical = False
        with self.assertRaises(ValueError):
            await script.cognition(source)
