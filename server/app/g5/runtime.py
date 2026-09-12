"""Shared sequential reference loop for all four factorial conditions.

Callbacks are dependency-injected adapters, not implementations of cognition or
governance. Tests use local scripted adapters; no LLM or production API is wired.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import inspect
from contextvars import ContextVar
from typing import Awaitable, Callable, Tuple

from app.factorial_study import ARMS, digest, verify_manifest
from app.g5.world import Conflict, Decision, World, WORLD_CONTRACT_SHA256, canonical
from app.g5.attempts import new_record, finished
from app.g5.role_inputs import validate_inputs, actor_view
from app.g5.components import verify_components, specification
from app.g5.question_journal import QuestionJournal, QUESTION_PROTOCOL
from app.g5.session_journal import SessionJournal, SESSION_PROTOCOL
from app.g5.model_session import SessionAnnotation
from app.g5.reopening import PROTOCOL as REOPENING_PROTOCOL, validate as validate_reopening

_reopening_context = ContextVar("g5_reopening_context", default=None)

Policy = Callable[[dict, Tuple[str, ...]], Awaitable[Decision]]
Cognition = Callable[[dict], Awaitable[dict]]


@dataclass(frozen=True)
class Review:
    allowed: bool
    reason: str = ""


Governance = Callable[[dict, Decision], Awaitable[Review]]


def detached(value):
    return json.loads(canonical(value))


class Runtime:
    def __init__(self, **kwargs):
        self._configure(**kwargs)
        if inspect.iscoroutinefunction(self.world.create):
            raise ValueError("Use await Runtime.open() with asynchronous stores")
        self.world.create(self.world_id, self.spec, self.binding)

    @classmethod
    async def open(cls, **kwargs):
        runtime = cls.__new__(cls)
        runtime._configure(**kwargs)
        await runtime._store("create", runtime.world_id, runtime.spec, runtime.binding)
        return runtime

    async def _store(self, method, *args, **kwargs):
        result = getattr(self.world, method)(*args, **kwargs)
        return await result if inspect.isawaitable(result) else result

    async def _invoke(self, stage, version, actor, function, /, *args, **kwargs):
        self._verify_components()
        record = new_record(stage, version, actor)
        request_context = _reopening_context.get()
        if request_context is not None and request_context[0] is self:
            record["reopen_request"] = detached(request_context[1])
        await self._store("record_attempt", self.world_id, record)
        from app.g5.capacity import measurements
        captured = []
        token = measurements.set(captured)
        try:
            result = function(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
            # Validation belongs to the attempt: malformed responses are failures.
            if stage == "policy":
                if not isinstance(result, Decision):
                    raise ValueError("Policy must return a Decision")
                result.validate()
            elif stage == "cognition":
                if not isinstance(result, dict):
                    raise ValueError("Cognition must return JSON state")
                detached(result)
            elif stage == "governance":
                if (not isinstance(result, Review) or type(result.allowed) is not bool
                        or not isinstance(result.reason, str) or (not result.allowed and not result.reason.strip())):
                    raise ValueError("Invalid governance response")
            elif stage == "session_annotation":
                annotation = result.annotation if isinstance(result, SessionAnnotation) else result
                if annotation is not None and not isinstance(annotation, dict):
                    raise ValueError("Session annotation must be an object or null")
                detached(asdict(result) if isinstance(result, SessionAnnotation) else result)
            elif stage == "annotation":
                if not isinstance(result, list):
                    raise ValueError("Annotations must be a list")
                detached(result)
        except BaseException as error:
            # A process kill may leave only 'started'; recovery must retain it as
            # indeterminate, not invent a successful/failed provider response.
            if captured:
                record["model_io"] = detached(captured)
            await self._store("record_attempt", self.world_id, finished(record, error))
            raise
        finally:
            measurements.reset(token)
        if captured:
            record["model_io"] = detached(captured)
        await self._store("record_attempt", self.world_id, finished(record))
        return result

    def _verify_components(self):
        if self.binding.get("cognition_storage") != self.storage_binding:
            raise ValueError("Cognition storage binding changed")
        if self.storage_binding is not None:
            from app.g5.cognition_storage import validate_spec
            validate_spec(self.storage_binding)
        if self.request_budget is not None:
            from app.g5.capacity import verify_runtime_budget
            verify_runtime_budget((self.policy, self.cognition, self.governance, self.annotator, self.session_annotator), self.request_budget)
        if self.observation_binding is not None:
            from app.g5.observation import ObservationWindow
            if type(self.observation_window) is not ObservationWindow or self.observation_window.runtime_specification() != self.observation_binding:
                raise ValueError("Common observation window changed")
        elif self.observation_window is not None:
            raise ValueError("Unfrozen observation window")
        if type(self.allow_reopening) is not bool or self.allow_reopening != (
                self.binding["stopping_policy"].get("reopening") in (
                    "explicit-request-next-scheduled-role-v1", REOPENING_PROTOCOL)):
            raise ValueError("Reopening policy changed")
        if type(self.reliable_reopening) is not bool or self.reliable_reopening != (
                self.binding["stopping_policy"].get("reopening") == REOPENING_PROTOCOL):
            raise ValueError("Reopening identity protocol changed")
        if self.session_binding is not None:
            if self.session_annotator is None or digest(specification(self.session_annotator)) != digest(self.session_binding):
                raise ValueError("Session annotator specification changed")
        elif self.session_annotator is not None:
            raise ValueError("Unfrozen session annotator")
        if self.scheduler_binding is not None:
            if self.scheduler is None or digest(specification(self.scheduler)) != digest(self.scheduler_binding):
                raise ValueError("Scheduler specification changed")
        elif self.scheduler is not None:
            raise ValueError("Unfrozen scheduler")
        if self.annotation_binding is not None:
            if self.annotator is None or digest(specification(self.annotator)) != digest(self.annotation_binding):
                raise ValueError("Question annotator specification changed")
        elif self.annotator is not None:
            raise ValueError("Unfrozen question annotator")
        if self.component_bindings is not None:
            verify_components(self.component_bindings, self.arm, policy=self.policy,
                              cognition=self.cognition, governance=self.governance)

    def _configure(self, *, world: World, world_id: str, spec: dict,
                 manifest: dict, ordinal: int, policy: Policy,
                 max_steps: int, max_revisions: int = 1,
                 cognition: Cognition | None = None, governance: Governance | None = None,
                 role_inputs: dict | None = None, question_annotator=None, scheduler=None, session_annotator=None,
                 allow_reopening=False, reliable_reopening=False, observation_window=None):
        verify_manifest(manifest)
        if type(ordinal) is not int or not 1 <= ordinal <= len(manifest["assignments"]):
            raise ValueError("Assignment ordinal is out of range")
        assignment = manifest["assignments"][ordinal - 1]
        switches = ARMS[assignment["arm"]]
        if switches["cognition"] != (cognition is not None):
            raise ValueError("Cognition adapter must be present iff the assigned arm enables it")
        if switches["governance"] != (governance is not None):
            raise ValueError("Governance adapter must be present iff the assigned arm enables it")
        if type(max_steps) is not int or max_steps < 1 or type(max_revisions) is not int or max_revisions < 0:
            raise ValueError("Invalid stopping policy")
        shared = manifest["design"]["arms"][assignment["arm"]]["shared"]
        scenario = next(s for s in manifest["design"]["scenarios"] if s["id"] == assignment["scenario_id"])
        # In this reference adapter a scenario snapshot is exactly its world spec.
        if (shared["world_sha256"] != WORLD_CONTRACT_SHA256
                or scenario["snapshot_sha256"] != digest(spec)):
            raise ValueError("World does not match the frozen assignment")
        stop = {"max_steps": max_steps, "max_revisions": max_revisions}
        if type(allow_reopening) is not bool:
            raise ValueError("Explicit reopening switch required")
        if type(reliable_reopening) is not bool or (reliable_reopening and not allow_reopening):
            raise ValueError("Reliable reopening requires explicit enabling")
        if allow_reopening:
            if "session_annotation" not in manifest["design"]:
                raise ValueError("Reopening requires frozen session annotation")
            stop["reopening"] = REOPENING_PROTOCOL if reliable_reopening else "explicit-request-next-scheduled-role-v1"
        if "session_annotation" in manifest["design"]:
            stop["session"] = detached(SESSION_PROTOCOL)
        if shared["stopping_policy_sha256"] != digest(stop):
            raise ValueError("Stopping policy differs from the frozen design")
        binding = {"protocol": "g5-local-reference-loop-v1", "assignment": assignment,
                   "manifest_sha256": manifest["manifest_sha256"], "stopping_policy": stop}
        self.role_inputs = None
        if role_inputs is not None:
            validate_inputs(role_inputs, spec["roles"])
            role_index = manifest["design"].get("scenario_role_inputs_sha256")
            expected_role_sha = (role_index[assignment["scenario_id"]]
                                 if role_index is not None else shared["role_inputs_sha256"])
            if expected_role_sha != digest(role_inputs):
                raise ValueError("Role inputs differ from the frozen design")
            self.role_inputs = detached(role_inputs)
            binding["role_inputs"] = detached(role_inputs)
        self.spec, self.binding = detached(spec), detached(binding)
        self.world, self.world_id = world, world_id
        self.policy, self.cognition, self.governance = policy, cognition, governance
        self.max_steps, self.max_revisions = max_steps, max_revisions
        self.allow_reopening = allow_reopening
        self.reliable_reopening = reliable_reopening
        self.roles = tuple(spec["roles"])
        self.arm = assignment["arm"]
        self.observation_window = observation_window
        self.observation_binding = detached(manifest["design"].get("observation_window"))
        if self.observation_binding is not None:
            self.binding["observation_window"] = detached(self.observation_binding)
        self.session_annotator = session_annotator
        self.session_binding = detached(manifest["design"].get("session_annotation"))
        self.session_journal = None
        if self.session_binding is not None:
            self.binding["session"] = detached(SESSION_PROTOCOL)
            self.binding["session_annotation"] = detached(self.session_binding)
            self.session_journal = SessionJournal(world, world_id)
        self.annotator = question_annotator
        self.scheduler = scheduler
        self.scheduler_binding = detached(manifest["design"].get("scheduling"))
        if self.scheduler_binding is not None:
            from app.g5.scheduling import QuestionScheduler
            if type(scheduler) is not QuestionScheduler:
                raise ValueError("Supported scheduler implementation required")
            if scheduler.enabled and question_annotator is None:
                raise ValueError("Priority scheduling requires frozen question annotation")
            self.binding["scheduling"] = detached(self.scheduler_binding)
        self.annotation_binding = detached(manifest["design"].get("question_annotation"))
        self.question_journal = None
        if self.annotation_binding is not None:
            self.binding["questions"] = detached(QUESTION_PROTOCOL)
            self.binding["question_annotation"] = detached(self.annotation_binding)
            self.question_journal = QuestionJournal(world, world_id)
        self.component_bindings = detached(manifest["design"].get("components"))
        self.storage_binding = detached(manifest["design"].get("cognition_storage"))
        if "cognition_storage" in manifest["design"]:
            self.binding["cognition_storage"] = detached(manifest["design"]["cognition_storage"])
        self.request_budget = detached(manifest["design"].get("request_budget"))
        if self.request_budget is not None:
            self.binding["request_budget"] = detached(self.request_budget)
        self._verify_components()
        if self.component_bindings is not None:
            if role_inputs is None:
                raise ValueError("Strict component runs require frozen role cards")
            self._verify_components()
            self.binding["components"] = detached(self.component_bindings)

    async def step(self, *, reopen=False, reopen_request=None) -> dict:
        self._verify_components()
        if reopen_request is None:
            if reopen and self.reliable_reopening:
                raise ValueError("Reliable reopening requires a stable targeted request")
            return await self._step(reopen=reopen)
        if not self.reliable_reopening or reopen is not False:
            raise ValueError("Targeted requests require the frozen v2 protocol")
        request = validate_reopening(reopen_request)
        result = await self._store("reopening", self.world_id, request)
        if result is not None:
            return result
        token = _reopening_context.set((self, request))
        try:
            try:
                result = await self._step(reopen=True, reopen_request=request)
            except Conflict:
                # Another contender may have committed while this model was computing.
                result = await self._store("reopening", self.world_id, request)
                if result is None:
                    raise
                return result
            if result["status"] == "dialogue_frozen":
                return await self._store("reopening", self.world_id, request)
            if result["status"] != "committed":
                return await self._store("reopening", self.world_id, request, result)
            return result
        finally:
            _reopening_context.reset(token)

    async def _step(self, *, reopen=False, reopen_request=None) -> dict:
        self._verify_components()
        if type(reopen) is not bool or (reopen and not self.allow_reopening):
            raise ValueError("Reopening must be explicitly enabled and requested")
        seal = await self._store("frozen", self.world_id)
        if seal is not None:
            return {"status": "dialogue_frozen", "seal_sha256": seal["sha256"], "task_completed": None}
        events = await self._store("events", self.world_id)
        if self.session_journal is not None:
            session = await self.session_journal.project()
            if reopen_request is not None and (len(events) != reopen_request["version"]
                    or session["episode"] != reopen_request["episode"] or session["status"] != "closed"):
                raise Conflict("Reopening target changed before generation")
            if reopen and session["status"] != "closed":
                raise ValueError("Only a closed session can be reopened")
            if session["status"] == "closed" and not reopen:
                return {"status": "session_closed", "reason": "all_participants_end_intent",
                        "task_completed": None, "episode": session["episode"]}
        if len(events) >= self.max_steps:
            return {"status": "cutoff", "reason": "step_limit", "task_completed": False}
        # Cursor is derived from the atomic event log, not a separate checkpoint.
        actor = self.roles[len(events) % len(self.roles)]
        selection = None
        if self.scheduler is not None:
            history = []
            for event in events:
                previous = event["payload"]["audit"].get("scheduling")
                if not isinstance(previous, dict) or previous.get("actor") != event["payload"]["actor"]:
                    raise ValueError("Missing or inconsistent committed scheduling history")
                history.append(previous)
            projection = await self.question_journal.project() if self.scheduler.enabled else None
            selection = self.scheduler.select(list(self.roles), projection, history)
            actor = selection["actor"]
        version, view = await self._store("observe", self.world_id, actor)
        if version != len(events):
            raise Conflict("World changed while choosing the next actor")
        if self.role_inputs is not None:
            view = actor_view(view, self.role_inputs)
        delivery = None
        if self.observation_window is not None:
            view, delivery = await self._invoke("observation", version, actor, self.observation_window.apply, view)
        view["memory_scope"] = digest([self.world_id, self.binding])
        audit = {"arm": self.arm, "cognition_called": self.cognition is not None,
                 "governance_called": self.governance is not None, "attempts": []}
        if delivery is not None:
            audit["observation_delivery"] = detached(delivery)
        if reopen_request is not None:
            audit["reopen_request"] = detached(reopen_request)
        if selection is not None:
            audit["scheduling"] = detached(selection)
        if self.cognition is not None:
            state = await self._invoke("cognition", version, actor, self.cognition, detached(view))
            if not isinstance(state, dict):
                raise ValueError("Cognition must return a JSON state object")
            audit["cognition_state"] = detached(state)
            if "cognition_storage" in self.binding:
                from app.g5.cognition_storage import encode, replay
                prior, base_event, count = replay(self.binding, self.world_id, events, actor).get(actor, ({}, None, 0))
                audit["cognition_state"] = encode(state, prior, scope=view["memory_scope"],
                    actor=actor, base_event=base_event, ordinal=count + 1)
            exporter = getattr(self.cognition, "policy_context", None)
            view["cognition"] = detached(exporter(state) if exporter else state)
        feedback: tuple[str, ...] = ()
        policy_view = detached(view)
        policy_view.pop("cognition_state", None)
        policy_view.pop("memory_scope", None)
        if reopen:
            policy_view["session_reopening"] = {"requested": True, "episode": session["episode"],
                "meaning": "Opportunity to propose reopening; not evidence or an obligation to agree."}
            audit["reopening_requested"] = True
        for attempt in range(self.max_revisions + 1):
            decision = await self._invoke("policy", version, actor, self.policy, detached(policy_view), feedback)
            if not isinstance(decision, Decision):
                raise ValueError("Policy must return a Decision")
            decision.validate()
            review = Review(True)
            if self.governance is not None:
                review = await self._invoke("governance", version, actor, self.governance, detached(policy_view), decision)
                if (not isinstance(review, Review) or type(review.allowed) is not bool
                        or not isinstance(review.reason, str) or (not review.allowed and not review.reason.strip())):
                    raise ValueError("Governance rejection requires a specific reason")
            audit["attempts"].append({"decision": asdict(decision), "review": asdict(review)})
            if review.allowed:
                break
            feedback += (review.reason,)
        else:
            # No synthetic refusal prose and no claim of successful task closure.
            decision = Decision("wait")
            audit["outcome"] = "unresolved_after_revisions"
        session_annotation = None
        if self.session_journal is not None and decision.action == "speak":
            context = {"actor": actor, "participants": list(self.roles),
                       "observations": detached(policy_view["observations"]),
                       "session": await self.session_journal.project()}
            if delivery is not None:
                context["observation_delivery"] = detached(policy_view["observation_delivery"])
            session_annotation = await self._invoke("session_annotation", version, actor,
                self.session_annotator, context, Decision(decision.action, decision.content, decision.operation))
            if isinstance(session_annotation, SessionAnnotation):
                audit["session_annotation_evidence"] = detached(session_annotation.model_evidence)
                session_annotation = session_annotation.annotation
        if reopen and (session_annotation or {}).get("kind") != "reopen":
            # A request grants an opportunity, not permission to publish through a closed session.
            # Attempts remain recorded; no dialogue, cognition state or cursor is committed.
            return {"status": "reopen_declined", "task_completed": None}
        annotations = None
        if self.question_journal is not None:
            annotations = []
            if decision.action == "speak":
                context = {"actor": actor, "participants": list(self.roles),
                           "observations": detached(policy_view["observations"]),
                           "questions": await self.question_journal.project()}
                if delivery is not None:
                    context["observation_delivery"] = detached(policy_view["observation_delivery"])
                annotations = await self._invoke("annotation", version, actor, self.annotator,
                                                 context, Decision(decision.action, decision.content, decision.operation))
                evidence = getattr(annotations, "model_evidence", None)
                if evidence is not None:
                    audit["question_annotation_evidence"] = detached(evidence)
        if self.session_journal is not None:
            event = await self._invoke("commit", version, actor, self.session_journal.commit,
                expected_version=version, request_id=f"step:{version + 1}", actor=actor,
                decision=decision, annotation=session_annotation, question_annotations=annotations, audit=audit,
                **({"reopen_request": reopen_request} if reopen_request is not None else {}))
        elif self.question_journal is not None:
            event = await self._invoke("commit", version, actor, self.question_journal.commit,
                expected_version=version, request_id=f"step:{version + 1}", actor=actor,
                decision=decision, annotations=annotations, audit=audit)
        else:
            event = await self._invoke("commit", version, actor, self._store, "commit", self.world_id, expected_version=version,
                                  request_id=f"step:{version + 1}", actor=actor,
                                  decision=decision, audit=audit)
        return {"status": "committed", "event": event}
