"""Evidence-triggered reflection/planning composition with injectable generators.

Citations establish provenance, NOT semantic entailment. Reflections remain
hypotheses; plans remain intentions and cannot execute actions or alter facts.
"""
from __future__ import annotations

from copy import deepcopy

from app.factorial_study import digest
from app.g5.memory import MemoryCognition

SCHEMA = "g5-reflection-plan-v1"
PLAN_REPAIR_PROTOCOL = "g5-plan-validation-feedback-v1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def references(ids, available):
    require(isinstance(ids, list) and bool(ids) and all(isinstance(x, str) for x in ids),
            "Nonempty memory source IDs required")
    require(len(ids) == len(set(ids)) and set(ids) <= set(available),
            "Duplicate or unavailable memory source")


def history(rows):
    require(isinstance(rows, list), "Invalid cognition history")
    seen = set()
    for row in rows:
        require(isinstance(row, dict), "Invalid cognition record")
        raw = {key: value for key, value in row.items() if key != "id"}
        require(row.get("id") == digest(raw) and row["id"] not in seen, "Cognition record corrupted")
        seen.add(row["id"])


class ReflectiveCognition:
    def __init__(self, *, memory: MemoryCognition, reflector, planner, reflector_id: str, planner_id: str,
                 hierarchical=False, plan_updates=False, max_active_tasks=64,
                 max_plan_revisions=0):
        require(callable(reflector) and callable(planner), "Reflection and planning adapters required")
        require(all(isinstance(x, str) and x for x in (reflector_id, planner_id)), "Frozen adapter IDs required")
        self.memory, self.reflector, self.planner = memory, reflector, planner
        require(type(hierarchical) is bool, "Explicit hierarchy switch required")
        self.hierarchical = hierarchical
        require(type(plan_updates) is bool and (not plan_updates or hierarchical), "Updates require hierarchical plans")
        require(type(max_active_tasks) is int and max_active_tasks > 0, "Positive active task capacity required")
        require(type(max_plan_revisions) is int and 0 <= max_plan_revisions <= 4,
                "Bounded plan revisions required")
        self.plan_updates, self.max_active_tasks = plan_updates, max_active_tasks
        self.max_plan_revisions = max_plan_revisions
        self.specification = {"schema": SCHEMA, "memory": deepcopy(memory.specification),
                              "reflector_id": reflector_id, "planner_id": planner_id}
        self.specification = self.runtime_specification()

    @staticmethod
    def policy_context(state):
        return deepcopy(state["context"])

    def runtime_specification(self):
        require(type(self.hierarchical) is bool, "Explicit hierarchy switch required")
        require(type(self.plan_updates) is bool and (not self.plan_updates or self.hierarchical), "Updates require hierarchy")
        spec = {**deepcopy(self.specification), "memory": self.memory.runtime_specification()}
        spec.pop("plan_protocol", None)
        if self.hierarchical:
            from app.g5.planning import PROTOCOL
            spec["plan_protocol"] = PROTOCOL
        spec.pop("plan_updates", None)
        if self.plan_updates:
            from app.g5.planning import DELTA_PROTOCOL
            require(type(self.max_active_tasks) is int and self.max_active_tasks > 0, "Invalid active task capacity")
            spec["plan_updates"] = {"schema": DELTA_PROTOCOL, "max_active_tasks": self.max_active_tasks}
        spec.pop("plan_repair", None)
        if self.max_plan_revisions:
            spec["plan_repair"] = {"schema": PLAN_REPAIR_PROTOCOL,
                                   "max_revisions": self.max_plan_revisions}
        for name in ("reflector", "planner"):
            getter = getattr(getattr(self, name), "runtime_specification", None)
            spec.pop(name + "_specification", None)
            if getter is not None:
                spec[name + "_specification"] = deepcopy(getter())
        return spec

    async def __call__(self, view):
        require(self.runtime_specification() == self.specification, "Cognitive configuration drift")
        previous = view.get("cognition_state") or {}
        require(isinstance(previous, dict), "Invalid cognitive state")
        if previous:
            require((previous.get("schema"), previous.get("owner"), previous.get("scope"),
                     previous.get("configuration")) ==
                    (SCHEMA, view["actor"], view.get("memory_scope"), self.specification),
                    "Cognition owner, scope or configuration changed")
        memory_view = deepcopy(view)
        memory_view["cognition_state"] = deepcopy(previous.get("memory", {}))
        memory = await self.memory(memory_view)
        reflections = deepcopy(previous.get("reflections", []))
        plans = deepcopy(previous.get("plans", []))
        receipts = deepcopy(previous.get("generation_receipts", []))
        history(receipts)
        history(reflections)
        history(plans)
        # Trigger on observed evidence, role goals or available capabilities, not
        # invisible global event counts or every scheduler tick.
        trigger = digest({"facts": view["facts"], "observations": view["observations"],
                          "role": view.get("own_role"), "operations": view["operations"]})
        selected = self.memory.policy_context(memory)
        if self.hierarchical:
            from app.g5.planning import pin_sources
            selected = pin_sources(selected, memory, plans[-1] if plans else None, view["facts"], active_only=self.plan_updates)
        available = {node["id"]: node for node in selected["retrieved"]}
        # Rebuild active projections from validated history, not a cached context.
        current_reflections = [deepcopy(row) for row in reflections if row["trigger"] == previous.get("trigger")]
        active_plan = deepcopy(plans[-1]) if plans else None
        if trigger != previous.get("trigger"):
            context = {"actor": view["actor"], "own_role": deepcopy(view.get("own_role", {})),
                       "operations": deepcopy(view["operations"]), "memory": selected,
                       "epistemic_rule": "Reflections are hypotheses; plans do not prove execution."}
            generated = await self.reflector(deepcopy(context))
            require(isinstance(generated, list), "Reflector must return a list")
            current_reflections = []
            for item in generated:
                require(isinstance(item, dict) and set(item) == {"text", "source_ids"}, "Invalid hypothesis fields")
                require(isinstance(item["text"], str) and bool(item["text"].strip()), "Empty hypothesis")
                references(item["source_ids"], available)
                raw = {"kind": "hypothesis", "text": item["text"], "source_ids": deepcopy(item["source_ids"]),
                       "disclosable": all(available[x]["disclosable"] for x in item["source_ids"]),
                       "trigger": trigger}
                row = {"id": digest(raw), **raw}
                if not any(old["id"] == row["id"] for old in reflections):
                    reflections.append(row)
                if not any(old["id"] == row["id"] for old in current_reflections):
                    current_reflections.append(row)
            previous_context = deepcopy(active_plan)
            if self.plan_updates:
                from app.g5.planning import projection
                previous_context = projection(active_plan, self.max_active_tasks)
            planner_context = {**deepcopy(context), "hypotheses": deepcopy(current_reflections),
                               "previous_plan": previous_context}
            rejected_plans = []
            for revision in range(self.max_plan_revisions + 1):
                generated_proposal = await self.planner(deepcopy(planner_context))
                try:
                    proposal = generated_proposal
                    if self.plan_updates:
                        from app.g5.planning import expand_updates
                        proposal = expand_updates(proposal, active_plan, available)
                    require(isinstance(proposal, dict) and set(proposal) == {"goal", "steps"}, "Invalid plan fields")
                    require(isinstance(proposal["goal"], str) and proposal["goal"].strip(), "Empty plan goal")
                    require(isinstance(proposal["steps"], list) and proposal["steps"], "Plan requires explicit steps")
                    if self.hierarchical:
                        from app.g5.planning import validate
                        validation_sources = ({node["id"]: node for node in memory["nodes"]}
                                              if self.plan_updates else available)
                        validate(proposal, active_plan, view["actor"], view["operations"], validation_sources)
                    break
                except ValueError as error:
                    evidence = getattr(generated_proposal, "generation_evidence", None)
                    if evidence is not None:
                        rejected_plans.append({"stage": "planning_rejected", "trigger": trigger,
                            "evidence": deepcopy(evidence), "validation_error": str(error)})
                    if revision >= self.max_plan_revisions:
                        raise
                    planner_context["validation_feedback"] = {
                        "schema": PLAN_REPAIR_PROTOCOL, "revision": revision + 1,
                        "error": str(error),
                        "instruction": "Correct only the rejected structure using supplied source IDs."}
            for step in (() if self.hierarchical else proposal["steps"]):
                require(isinstance(step, dict) and set(step) == {"actor", "intent", "text", "operation", "source_ids"},
                        "Invalid plan step fields")
                require(step["actor"] == view["actor"], "Cannot plan actions on another role's behalf")
                require(step["intent"] in ("ask", "speak", "execute", "wait", "defer", "decline"), "Invalid plan intent")
                require(isinstance(step["text"], str) and step["text"].strip(), "Empty plan step")
                if step["intent"] == "execute":
                    require(step["operation"] in view["operations"], "Unavailable planned operation")
                else:
                    require(step["operation"] == "", "Non-execution step cannot execute an operation")
                # Cold start may legitimately wait/ask/defer without pretending
                # to possess evidence. It cannot justify a claim or execution.
                if not available and step["intent"] in ("ask", "wait", "defer", "decline"):
                    require(step["source_ids"] == [], "No sources exist at cold start")
                else:
                    references(step["source_ids"], available)
            raw = {"kind": "intention", "proposal": deepcopy(proposal), "trigger": trigger,
                   "supersedes": active_plan["id"] if active_plan else None}
            if self.hierarchical:
                origins = deepcopy(active_plan.get("task_origins", {})) if active_plan else {}
                for step in proposal["steps"]:
                    origins.setdefault(step["id"], sorted(node["id"] for node in memory["nodes"]))
                raw["task_origins"] = origins
            if self.plan_updates:
                raw["update_proposal"] = deepcopy(generated_proposal)
            active_plan = {"id": digest(raw), **raw}
            if self.plan_updates:
                projection(active_plan, self.max_active_tasks)
            plans.append(active_plan)
            for raw in rejected_plans:
                row = {"id": digest(raw), **raw}
                if not any(old["id"] == row["id"] for old in receipts):
                    receipts.append(row)
            for stage, output in (("reflection", generated), ("planning", generated_proposal)):
                evidence = getattr(output, "generation_evidence", None)
                if evidence is not None:
                    raw = {"stage": stage, "trigger": trigger, "evidence": deepcopy(evidence)}
                    row = {"id": digest(raw), **raw}
                    if not any(old["id"] == row["id"] for old in receipts):
                        receipts.append(row)
        require(self.runtime_specification() == self.specification, "Cognitive configuration drift")
        policy_plan = active_plan
        if self.plan_updates:
            from app.g5.planning import projection
            policy_plan = projection(active_plan, self.max_active_tasks)
            selected = pin_sources(self.memory.policy_context(memory), memory, active_plan, view["facts"],
                active_only=True, extra_ids=[source for row in current_reflections for source in row["source_ids"]])
        return {"schema": SCHEMA, "owner": view["actor"], "scope": view["memory_scope"],
                "configuration": deepcopy(self.specification), "memory": memory,
                "reflections": reflections, "plans": plans, "trigger": trigger,
                "generation_receipts": receipts,
                "context": {**selected, "hypotheses": current_reflections, "plan": policy_plan}}
