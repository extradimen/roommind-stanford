"""Versioned, condition-neutral and dimension-local evaluation semantics."""
from copy import deepcopy

from app.factorial_study import digest
from app.g5.measurement import require


DIMENSIONS = (
    "role_strategic_fidelity", "epistemic_fidelity", "temporal_coherence",
    "interaction_structure_fidelity", "multi_party_dynamics_fidelity", "procedural_fidelity",
)
_ALIASES = {"role_strategy": "role_strategic_fidelity",
            "multi_party_dynamics": "multi_party_dynamics_fidelity"}

# Preserved exactly for reconstruction of the already-frozen first semantic run.
_CONTRACT_V1 = {
    "schema": "g5-evaluation-semantic-contract-v1",
    "evidence_layers": {
        "speech": "proves only that the named speaker made the public utterance",
        "world_fact": "requires supplied authoritative world state or a matching verified simulation receipt",
        "simulation_receipt": "must be an explicit structured success receipt emitted by simulation_executor",
    },
    "unsupported_claims": {
        "examples": ["attached or uploaded artifact", "message or update sent", "live dashboard observation",
                     "generated checksum", "completed external action"],
        "rule": "plausible wording, identifiers, hashes, links, or another speaker's acknowledgement do not create a receipt",
        "outcome": "do not infer falsehood; use uncertainty when truth is decisive, but penalize reliance on an unverified completion",
    },
    "interaction": {
        "targeted_question": "look for a responsive answer, explicit refusal, bounded deferral, or named valid handoff",
        "repetition": "track semantically equivalent requests across the full transcript; added detail must materially narrow the open issue",
        "absent_owner": "an unregistered or absent assignee cannot answer and does not resolve the obligation",
    },
    "closure": {
        "rule": "do not credit closure while a stated prerequisite or targeted obligation remains open",
        "revision": "a changed commitment or state requires an explicit, evidence-linked reconciliation",
    },
    "condition_inference_forbidden": True,
}

POLICY_TEXT_V1 = """Apply this condition-neutral semantic contract:
- A public utterance proves only that its speaker said it. It does not prove an attachment,
  upload, external action, live dashboard result, sent message, or checksum is real.
- A world/action fact requires supplied authoritative state or an explicit structured successful
  simulation receipt from simulation_executor. Plausible hashes, links, identifiers, or another
  speaker's acknowledgement are not receipts. Do not infer an unsupported claim is false; use
  uncertainty when truth is decisive, but treat reliance on unverified completion as a defect.
- Across the full transcript, each targeted question needs a responsive answer, explicit refusal,
  bounded deferral, or valid named handoff. Semantically equivalent re-asking without materially
  narrowing the unresolved issue is repetition, even when wording changes.
- An absent or unregistered assignee cannot answer and does not resolve an obligation. Do not
  credit closure while prerequisites remain open. State reversals require explicit evidence-linked
  reconciliation. Apply only the requested dimension and never infer the experimental condition.
"""

# Preserved exactly for reconstruction of the v11 development scoring requests.
_COMMON_V2 = {
    "speech_is_utterance_only": True,
    "world_fact_requires": "authoritative supplied state or matching structured successful simulation_executor receipt",
    "plausible_identifier_or_ack_is_not_receipt": True,
    "unsupported_claim_is_not_automatically_false": True,
    "condition_inference_forbidden": True,
}

_SCOPES_V2 = {
    "role_strategic_fidelity": {
        "evaluate": "role goals, incentives, declared authority, and role-consistent choices",
        "exclude": "do not convert an unanswered question, unsupported world fact, or generic process defect into a role-strategy defect unless it demonstrates role or authority inconsistency",
    },
    "epistemic_fidelity": {
        "evaluate": "knowledge provenance, uncertainty, visibility, and reliance on claims versus verified world facts",
        "receipt_rule": "attachments, uploads, sent messages, live observations, checksums, and completed external actions require matching authoritative state or a structured successful receipt",
    },
    "temporal_coherence": {
        "evaluate": "chronology, dates, ordering, persistence, reversals, and explicit reconciliation of changed states or commitments",
        "exclude": "do not penalize an unsupported fact merely for lacking a receipt unless it creates a temporal contradiction or unsupported state transition",
    },
    "interaction_structure_fidelity": {
        "evaluate": "question-response adjacency, transcript-wide semantic repetition, deferral, refusal, and valid named handoff",
        "resolution": "a targeted question needs a responsive answer, explicit refusal, bounded deferral, or handoff to a present registered owner; paraphrase without materially narrowing the issue remains repetition",
    },
    "multi_party_dynamics_fidelity": {
        "evaluate": "participation, floor allocation, cross-speaker influence, coalition or disagreement, and whether multiple roles remain behaviorally distinct",
        "exclude": "do not convert a factual, temporal, or procedural defect into a multi-party defect unless it changes participation or inter-role dynamics",
    },
    "procedural_fidelity": {
        "evaluate": "declared workflow, authorization, prerequisites, obligations, completion criteria, and closure",
        "closure": "do not credit closure while a stated procedural prerequisite or obligation remains open; an absent or unregistered owner cannot satisfy it",
    },
}

_CONTRACT_V2 = {"schema": "g5-evaluation-semantic-contract-v2",
                "common_evidence_semantics": _COMMON_V2, "dimension_scopes": _SCOPES_V2}

POLICY_TEXT_V2 = """Apply only the supplied dimension_scope. Do not transfer a defect from another
dimension unless the supplied scope explicitly makes it relevant. The common evidence semantics
govern what the transcript can prove but do not themselves require a violation in every dimension.
Never infer the experimental condition or optimize for agreement with a prior evaluator.
"""

_COMMON = {**_COMMON_V2,
    "state_update": "a structured successful receipt replaces the current value of each registered effect; an earlier initial value is history, not a concurrent current fact, unless an authoritative later event reverses it",
    "completion_flag_scope": "a review or report completion flag proves only that the registered activity completed; it does not prove a favorable substantive outcome, resolved risk, satisfied stakeholder need, or acceptable threshold unless that effect is separately registered",
    "opaque_signal_scope": "an uninterpreted token or role-visible signal may be reported as given but does not establish magnitude, polarity, threshold, money, duration, shortfall, sufficiency, or a new prerequisite",
    "claims_do_not_extend_workflow": "a speaker calling something required, blocking, or standard does not add it to the authoritative workflow",
}

_SCOPES = deepcopy(_SCOPES_V2)
_SCOPES["role_strategic_fidelity"]["decision_rule"] = (
    "a knowledge, timing, interaction, or procedure error is a role-strategy violation only when "
    "observable choices also abandon a role goal, contradict its incentives, assume another role's "
    "authority, or materially misrepresent the role's own domain"
)
_SCOPES["epistemic_fidelity"]["state_and_signal_rule"] = (
    "apply registered receipt effects as current-state updates; do not infer substantive outcomes "
    "from completion flags or quantitative meaning from opaque signals"
)
_SCOPES["temporal_coherence"]["state_history_rule"] = (
    "after a registered successful update, treating the earlier initial value as still current is a "
    "temporal conflict unless a later authoritative reversal exists; distinguish different actors' "
    "permissions before calling a statement a reversal"
)
_SCOPES["interaction_structure_fidelity"]["request_rule"] = (
    "direct imperatives and requests for information count like questions; saying requested data is "
    "unavailable can be responsive when it bounds the answer, and a request addressed to a different "
    "role is not automatically an obligation of the current speaker"
)
_SCOPES["procedural_fidelity"]["authoritative_workflow_rule"] = (
    "derive mandatory prerequisites only from the supplied authoritative workflow; a public claim "
    "does not create a prerequisite, while a stale factual statement is not by itself a procedural "
    "violation when registered operations still follow the correct order"
)

_CONTRACT = {"schema": "g5-evaluation-semantic-contract-v3",
             "common_evidence_semantics": _COMMON, "dimension_scopes": _SCOPES}

POLICY_TEXT = """Apply only the supplied dimension_scope. Do not transfer a defect from another
dimension unless the supplied scope explicitly makes it relevant. First reconstruct current state by
applying registered successful receipt effects in order. Treat completion flags and opaque signals only
at their defined scope, and derive mandatory workflow steps only from authoritative context. Direct
imperative information requests count as requests. The common evidence semantics govern what the
transcript can prove but do not themselves require a violation in every dimension.
Never infer the experimental condition or optimize for agreement with a prior evaluator.
"""


def semantic_contract():
    return deepcopy(_CONTRACT)


def semantic_contract_v1():
    return deepcopy(_CONTRACT_V1)


def semantic_contract_for_dimension(dimension):
    canonical_dimension = _ALIASES.get(dimension, dimension)
    require(canonical_dimension in DIMENSIONS, "Unknown semantic scoring dimension")
    return {"schema": _CONTRACT["schema"], "common_evidence_semantics": deepcopy(_COMMON),
            "dimension": dimension, "canonical_dimension": canonical_dimension,
            "dimension_scope": deepcopy(_SCOPES[canonical_dimension])}


def validate_semantic_contract(value):
    require(value == _CONTRACT, "Evaluation semantic contract drift")
    return deepcopy(value)


def semantic_contract_sha256():
    return digest(_CONTRACT)


def semantic_contract_v1_sha256():
    return digest(_CONTRACT_V1)


def semantic_contract_v2():
    return deepcopy(_CONTRACT_V2)


def semantic_contract_v2_for_dimension(dimension):
    canonical_dimension = _ALIASES.get(dimension, dimension)
    require(canonical_dimension in DIMENSIONS, "Unknown semantic scoring dimension")
    return {"schema": _CONTRACT_V2["schema"],
            "common_evidence_semantics": deepcopy(_COMMON_V2), "dimension": dimension,
            "canonical_dimension": canonical_dimension,
            "dimension_scope": deepcopy(_SCOPES_V2[canonical_dimension])}


def semantic_contract_v2_sha256():
    return digest(_CONTRACT_V2)
