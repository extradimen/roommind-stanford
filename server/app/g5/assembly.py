"""Allowlisted offline assembly; configuration never imports executable code.

Transport factories are explicitly trusted local callables, not a sandbox or a
network firewall. No credentials, environment lookup, or route discovery occurs.
"""
from copy import deepcopy

from app.factorial_study import digest
from app.g5.capacity import BudgetTransport, RequestBudget
from app.g5.governance import CandidateGovernance
from app.g5.memory import MemoryCognition
from app.g5.model_auditor import ModelAuditor
from app.g5.model_cognition import ModelCognitionGenerator
from app.g5.model_policy import ModelBinding, ModelPolicy
from app.g5.model_questions import ModelQuestionAnnotator
from app.g5.model_session import ModelSessionAnnotator
from app.g5.observation import ObservationWindow
from app.g5.reflection import ReflectiveCognition
from app.g5.scheduling import QuestionScheduler
from app.g5.semantic import EmbeddingBinding, EmbeddingScorer
from app.g5.world import canonical


def exact(instance, expected):
    if canonical(instance.runtime_specification()) != canonical(expected):
        raise ValueError("Archived component specification mismatch")
    return instance


class OfflineAssembler:
    def __init__(self, transport_factories):
        if not isinstance(transport_factories, dict) or not all(
                isinstance(k, str) and k and callable(v) for k, v in transport_factories.items()):
            raise ValueError("Explicit local transport factories required")
        self.factories = dict(transport_factories)
        self.allowed_model_providers = {"offline"}

    def component(self, specification):
        s = deepcopy(specification)
        if not isinstance(s, dict):
            raise ValueError("Component object required")
        try:
            return exact(self._build(s), s)
        except (KeyError, TypeError) as error:
            raise ValueError("Unsupported or incomplete archived specification") from error

    def _build(self, s):
        kind = s.get("adapter", s.get("schema", s.get("scheduler")))
        if kind == "g5-budgeted-transport-v1":
            b = s["budget"]
            budget = exact(RequestBudget(b["max_request_bytes"], b["max_response_bytes"]), b)
            delegate = self.factories[s["delegate_id"]]()
            getter = getattr(delegate, "runtime_specification", None)
            if not callable(delegate) or canonical(getter() if getter else None) != canonical(s["delegate_spec"]):
                raise ValueError("Local transport declaration mismatch")
            return BudgetTransport(delegate, budget, delegate_id=s["delegate_id"])
        models = {"g5-decision-json-v1": ModelPolicy, "g5-model-auditor-v1": ModelAuditor,
                  "g5-model-questions-v1": ModelQuestionAnnotator,
                  "g5-model-session-v1": ModelSessionAnnotator}
        if kind in models or kind in ("g5-cognitive-json-v1", "g5-batch-cosine-v1"):
            if s["binding"]["provider"] not in self.allowed_model_providers:
                raise ValueError("Model provider is not allowed by this assembler")
            binding = (EmbeddingBinding if kind == "g5-batch-cosine-v1" else ModelBinding)(**s["binding"])
            transport = self.component(s["transport"])
            if kind == "g5-cognitive-json-v1":
                return ModelCognitionGenerator(s["kind"], binding, transport)
            return (EmbeddingScorer if kind == "g5-batch-cosine-v1" else models[kind])(binding, transport)
        if kind == "g5-source-memory-v1":
            semantic = s.get("semantic_specification")
            return MemoryCognition(top_k=s["top_k"], semantic_id=s["semantic_id"],
                                   semantic_scorer=self.component(semantic) if semantic else None)
        if kind == "g5-reflection-plan-v1":
            updates = s.get("plan_updates")
            return ReflectiveCognition(memory=self.component(s["memory"]),
                reflector=self.component(s["reflector_specification"]),
                planner=self.component(s["planner_specification"]), reflector_id=s["reflector_id"],
                planner_id=s["planner_id"], hierarchical="plan_protocol" in s,
                plan_updates=updates is not None, max_active_tasks=updates["max_active_tasks"] if updates else 64,
                max_plan_revisions=(s.get("plan_repair") or {}).get("max_revisions", 0))
        if kind == "g5-candidate-governance-v1":
            return CandidateGovernance(self.component(s["auditor"]), auditor_id=s["auditor_id"])
        if kind == "g5-common-observation-window-v1":
            return ObservationWindow(s["max_observations"], s["max_chars"])
        if kind == "g5-bounded-question-opportunities-v1":
            return QuestionScheduler(priority_enabled=s["priority_enabled"], max_priority_streak=s["max_priority_streak"])
        raise ValueError("Unsupported archived component type")

    def factory(self, *, world, manifest, runtime_inputs):
        """runtime_inputs maps scenario IDs to frozen Runtime non-component inputs.

        Runtime._configure checks scenario/role hashes, stop rules, arm switches
        and all reconstructed specifications before any batch world is created.
        """
        from app.g5.runtime import Runtime
        from app.factorial_study import verify_manifest
        verify_manifest(manifest)
        manifest, inputs = deepcopy(manifest), deepcopy(runtime_inputs)
        allowed = {"spec", "role_inputs", "max_steps", "max_revisions", "allow_reopening", "reliable_reopening"}
        for value in inputs.values():
            if not isinstance(value, dict) or set(value) - allowed:
                raise ValueError("Unsupported runtime input")

        def build(assignment):
            if assignment not in manifest["assignments"]:
                raise ValueError("Assignment not in frozen manifest")
            d = manifest["design"]
            args = deepcopy(inputs[assignment["scenario_id"]])
            args.update(world=world,
                world_id="g5-assembly-" + digest(
                    [manifest["manifest_sha256"], assignment["ordinal"]]),
                manifest=deepcopy(manifest), ordinal=assignment["ordinal"])
            arm = assignment["arm"]
            for name in ("policy", "cognition", "governance"):
                enabled = name == "policy" or (name == "cognition" and arm in ("B", "D")) or (name == "governance" and arm in ("C", "D"))
                args[name] = self.component(d["components"][name]) if enabled else None
            for arg, key in (("question_annotator", "question_annotation"), ("session_annotator", "session_annotation"),
                             ("scheduler", "scheduling"), ("observation_window", "observation_window")):
                args[arg] = self.component(d[key])
            runtime = Runtime.__new__(Runtime)
            runtime._configure(**args)
            return args
        return build


class ExplicitRouteAssembler(OfflineAssembler):
    """Rebuild allowlisted Ollama components from caller-supplied route factories.

    Construction is not execution authorization. Factories must return already
    configured transports whose public runtime specifications exactly match the
    frozen transport object. Credentials and URLs are neither accepted here nor
    serialized into the study manifest.
    """
    def __init__(self, transport_factories, route_factories):
        super().__init__(transport_factories)
        if not isinstance(route_factories, dict) or not all(
                isinstance(k, str) and k and callable(v) for k, v in route_factories.items()):
            raise ValueError("Explicit route factories required")
        self.route_factories = dict(route_factories)
        self.allowed_model_providers = {"offline", "ollama"}

    def _build(self, s):
        kind = s.get("adapter", s.get("schema", s.get("scheduler")))
        if kind in ("g5-ollama-http-v1", "g5-ollama-http-v2"):
            binding = s.get("binding")
            if not isinstance(binding, dict) or binding.get("provider") != "ollama":
                raise ValueError("Ollama transport requires an Ollama binding")
            endpoint = binding.get("endpoint_id")
            if endpoint not in self.route_factories:
                raise ValueError("Unregistered explicit route")
            adapter = self.route_factories[endpoint]()
            return exact(adapter, s)
        result = super()._build(s)
        if kind in {"g5-decision-json-v1", "g5-model-auditor-v1", "g5-model-questions-v1",
                    "g5-model-session-v1", "g5-cognitive-json-v1", "g5-batch-cosine-v1"}:
            provider = s["binding"]["provider"]
            transport = s.get("transport", {})
            delegate = (transport.get("delegate_spec", {})
                        if transport.get("adapter") == "g5-budgeted-transport-v1" else transport)
            if kind == "g5-batch-cosine-v1" and provider != "offline":
                raise ValueError("Ollama chat route is not an embedding transport")
            if provider == "ollama" and delegate.get("adapter") not in ("g5-ollama-http-v1", "g5-ollama-http-v2"):
                raise ValueError("Ollama model requires the frozen Ollama transport")
            if provider == "offline" and delegate.get("adapter") in ("g5-ollama-http-v1", "g5-ollama-http-v2"):
                raise ValueError("Offline model cannot use an Ollama route")
        return result
