"""Optional candidate review, separate from common world execution permissions.

Auditors produce findings, not replacement speech. Structural evidence checks
do not establish semantic correctness: calibration remains a separate gate.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from app.factorial_study import digest
from app.g5.runtime import Review
from app.g5.structured_output import (StructuredOutputError, capsule, feedback,
                                      repair_spec)

HARD_CODES = ("protected_disclosure", "role_impersonation", "unsupported_fact")


@dataclass(frozen=True)
class EvidenceReview(Review):
    findings_json: str = "[]"
    candidate_sha256: str = ""
    audit_context_sha256: str = ""
    model_evidence_json: str = "null"


class CandidateGovernance:
    def __init__(self, auditor, *, auditor_id: str, max_structured_revisions=0):
        if not callable(auditor) or not isinstance(auditor_id, str) or not auditor_id.strip():
            raise ValueError("Explicit governance auditor required")
        self.auditor, self.auditor_id = auditor, auditor_id
        repair_spec(max_structured_revisions)
        self.max_structured_revisions = max_structured_revisions
        self.specification = self.runtime_specification()

    def runtime_specification(self):
        spec = {"adapter": "g5-candidate-governance-v1", "auditor_id": self.auditor_id,
                "hard_codes": list(HARD_CODES), "uncertain_is_advisory": True,
                "replacement_speech": False}
        if self.max_structured_revisions:
            spec["structured_repair"] = repair_spec(self.max_structured_revisions)
        getter = getattr(self.auditor, "runtime_specification", None)
        if getter is not None:
            spec["auditor"] = deepcopy(getter())
        return spec

    async def __call__(self, view, decision):
        from app.g5.world import canonical
        decision.validate()
        if self.runtime_specification() != self.specification:
            raise ValueError("Governance configuration drift")
        candidate = {"action": decision.action, "content": decision.content, "operation": decision.operation}
        # Common executor owns action permissions. Extra speech review does not
        # penalize waiting, create receipts or inspect hidden world truth.
        context = {key: deepcopy(view[key]) for key in
                   ("actor", "public_roster", "facts", "observations", "operations", "observation_delivery") if key in view}
        sources = {"fact:" + key: deepcopy(fact) for key, fact in context.get("facts", {}).items()}
        for obs in context.get("observations", []):
            sources["event:" + obs["event_id"]] = deepcopy(obs)
        context["sources"] = sources
        findings, reasons, rejected, validation_feedback = [], [], [], None
        if decision.action == "speak":
            for revision in range(self.max_structured_revisions + 1):
                try:
                    args = (deepcopy(context), deepcopy(candidate))
                    findings = (await self.auditor(*args) if validation_feedback is None
                                else await self.auditor(*args, validation_feedback))
                    if not isinstance(findings, list):
                        raise ValueError("Auditor must return findings")
                    reasons = []
                    for item in findings:
                        if not isinstance(item, dict) or set(item) != {"code", "severity", "certainty", "start", "end", "source_ids", "reason"}:
                            raise ValueError("Invalid governance finding")
                        if (item["severity"] not in ("hard", "advisory") or item["certainty"] not in ("supported", "uncertain")
                                or not isinstance(item["code"], str) or not item["code"].strip()
                                or not isinstance(item["reason"], str) or not item["reason"].strip()
                                or type(item["start"]) is not int or type(item["end"]) is not int
                                or not 0 <= item["start"] < item["end"] <= len(decision.content)):
                            raise ValueError("Invalid governance finding values")
                        ids = item["source_ids"]
                        if (not isinstance(ids, list) or any(not isinstance(x, str) for x in ids)
                                or len(ids) != len(set(ids)) or not set(ids) <= set(sources)):
                            raise ValueError("Unavailable governance evidence")
                        if item["severity"] == "hard":
                            if item["code"] not in HARD_CODES:
                                raise ValueError("Unsupported hard constraint")
                            if item["certainty"] == "supported":
                                if not ids:
                                    raise ValueError("Supported hard finding requires evidence")
                                reasons.append(item["reason"])
                    break
                except ValueError as error:
                    inherited = getattr(error, "structured_failures", [])
                    if inherited:
                        rejected.extend(deepcopy(inherited))
                    elif "findings" in locals() and hasattr(findings, "raw_response_content"):
                        evidence = findings.model_evidence
                        rejected.append(capsule("governance_auditor", revision,
                            evidence["request_sha256"], findings.raw_response_content, error,
                            allowed_values={"source_ids": sorted(sources), "hard_codes": list(HARD_CODES)}))
                    if revision >= self.max_structured_revisions:
                        if rejected:
                            raise StructuredOutputError(str(error), rejected) from None
                        raise
                    if not rejected:
                        raise
                    validation_feedback = feedback(rejected[-1], revision + 1)
            if rejected:
                findings.model_evidence["rejected"] = deepcopy(rejected)
        if self.runtime_specification() != self.specification:
            raise ValueError("Governance configuration drift")
        return EvidenceReview(not reasons, "\n".join(reasons), canonical(findings),
                              digest(candidate), digest(context),
                              canonical(getattr(findings, "model_evidence", None)))
