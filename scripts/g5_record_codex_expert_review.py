#!/usr/bin/env python3
"""Record a single Codex expert review without misrepresenting it as human reference data."""
import argparse
import json
from collections import Counter
from pathlib import Path

from app.factorial_study import digest


DECISIONS = {
    58: {
        "role_strategy": ("violation", [14, 16], "Jordan confirms incident scope even though the declared authority surface reserves that confirmation to the SRE role."),
        "epistemic_fidelity": ("uncertain", [2, 6], "The dialogue states dashboard findings and that a recovery-plan draft was posted, but the supplied public text contains no independent world or artifact receipt with which to verify those claims."),
        "temporal_coherence": ("clear", [2, 16, 20], "Containment is reported as activated, a later request seeks formal confirmation, and the unresolved recovery approval is explicitly deferred to the next review rather than falsely closed."),
        "interaction_structure_fidelity": ("violation", [13, 16, 18], "Priya is directly asked twice to confirm active containment; the second request receives no SRE answer before the conversation redirects to closure."),
        "multi_party_dynamics": ("clear", [1, 3, 11], "The participants contribute distinct incident-command, customer-communication, and evidence-preservation perspectives rather than merely echoing one another."),
        "procedural_fidelity": ("clear", [16, 20], "The missing formal containment response remains visible and recovery-plan approval is scheduled for the next review rather than represented as already complete."),
    },
    138: {
        "role_strategy": ("violation", [31, 36, 37], "The sales lead asserts that Operations confirmed readiness, the candidate is addressed by the wrong name, and Operations subsequently says readiness is still pending."),
        "epistemic_fidelity": ("violation", [31, 37], "A public claim that Samir confirmed operational readiness is directly contradicted by Samir's later statement that key staffing and control artifacts are still missing."),
        "temporal_coherence": ("violation", [31, 32, 37], "Operational readiness is declared complete and then withdrawn without an explicit evidence-based revision or reconciliation."),
        "interaction_structure_fidelity": ("violation", [30, 33, 34], "Dana is asked to name the follow-up owner, other roles substitute an answer, and Dana's prompted reply still does not name that owner."),
        "multi_party_dynamics": ("clear", [2, 5, 10], "Finance, Sales, and Operations expose materially different budget, demand, staffing, and control constraints."),
        "procedural_fidelity": ("violation", [30, 32, 37], "The launch prerequisites are treated as confirmed before the operational artifacts and staffing requirements that Operations itself defined are met."),
    },
    171: {
        "role_strategy": ("clear", [2, 4, 6], "Each interviewer pursues the advertised product, engineering, or people-leadership domain, while the candidate consistently answers as the candidate."),
        "epistemic_fidelity": ("uncertain", [11, 21, 35], "The candidate supplies detailed artifact names and excerpts, but the artifacts are not actually present; the public transcript alone cannot establish whether the historical claims are true."),
        "temporal_coherence": ("clear", [3, 9, 40], "The checkout example, later badge iteration, and follow-up ownership remain chronologically compatible and no explicit commitment is reversely asserted."),
        "interaction_structure_fidelity": ("violation", [10, 21, 24], "The product-evidence request is repeatedly reissued after substantive answers, creating an avoidable verification loop before the same public excerpts are finally accepted."),
        "multi_party_dynamics": ("clear", [4, 6, 42], "The panel maintains distinct product, engineering, and leadership lines and explicitly hands confirmation to the relevant interviewer."),
        "procedural_fidelity": ("clear", [21, 35, 42], "The panel marks missing evidence as unconfirmed, requests public excerpts, and only then records product and engineering evidence as satisfied."),
    },
    173: {
        "role_strategy": ("violation", [14, 46, 51], "The supplier CEO repeatedly confirms the joint quality protocol even though that confirmation belongs to the quality director under the declared authority surface."),
        "epistemic_fidelity": ("violation", [11, 33, 34], "The asserted contract summary restores a 5% liability cap after the parties publicly accepted a 10% escalation for high defects, so the claimed document content conflicts with public evidence."),
        "temporal_coherence": ("violation", [13, 33, 36], "The agreed 10% escalation is later summarized as a 5% cap and only subsequently corrected, without acknowledging the intervening inconsistency."),
        "interaction_structure_fidelity": ("clear", [3, 7, 12], "Capacity, price, and inspection questions are routed to the responsible roles and receive responsive answers or explicit deferrals."),
        "multi_party_dynamics": ("clear", [2, 3, 6], "Commercial margin, quality capacity, and market-benchmark positions are distinct and materially shape the negotiated package."),
        "procedural_fidelity": ("violation", [13, 33, 34], "A contract representation omits the agreed defect-triggered 10% liability term, requiring the quality lead to reopen a supposedly settled condition."),
    },
    241: {
        "role_strategy": ("clear", [2, 3, 4], "The three panelists ask domain-appropriate product, engineering, and people questions and the candidate stays in the candidate role."),
        "epistemic_fidelity": ("uncertain", [45, 47, 69], "Many operational and outcome figures are narrated without the underlying dashboard, test, or artifact; public text alone cannot verify the historical facts."),
        "temporal_coherence": ("clear", [5, 45, 47], "The Q2 2023 project, later monitoring incident, and subsequent analysis can coexist chronologically and no decisive commitment is explicitly reversed."),
        "interaction_structure_fidelity": ("violation", [46, 51, 64], "The Product VP repeats substantially the same unanswered A/B-test request across many turns rather than bounding, deferring, or closing the question."),
        "multi_party_dynamics": ("violation", [6, 7, 8], "Three simultaneous question chains are repeatedly advanced without coordinated floor control, causing long parallel loops instead of a bounded panel exchange."),
        "procedural_fidelity": ("clear", [20, 35, 44], "Panelists record evidence completion only within their own stated domains and continue to hold the unresolved product-evidence item open."),
    },
    242: {
        "role_strategy": ("violation", [6, 10, 12], "After the domain owners confirm their own areas, Morgan separately confirms market, operational, and budget states despite only having authority to confirm the launch decision."),
        "epistemic_fidelity": ("violation", [5, 23, 26], "The transcript claims an attached financial model, sent invitations with a placeholder date, and uploaded SharePoint artifacts despite no public receipt or artifact surface."),
        "temporal_coherence": ("violation", [44, 45, 46], "The same day-30 review is proposed for October 9, the week of October 30, and October 4 in adjacent responses without acknowledging or reconciling the conflict before selection."),
        "interaction_structure_fidelity": ("clear", [9, 10, 11], "The explicitly targeted operational and budget questions receive direct, domain-local responses before the launch decision."),
        "multi_party_dynamics": ("clear", [6, 7, 8], "Market, staffing/monitoring, and budget-review constraints remain distinguishable and contribute to a bounded phased-launch decision."),
        "procedural_fidelity": ("clear", [10, 11, 15], "The phased launch is approved only after explicit operational safeguards and budget controls are stated and confirmed by their responsible roles."),
    },
    257: {
        "role_strategy": ("violation", [54, 55, 57], "Participants assign decisive work to unregistered Alex Patel, and Security creates that ownership despite the declared roster and authority surface."),
        "epistemic_fidelity": ("violation", [32, 47, 49], "The dialogue claims a status-page publication and produces a checksum-like receipt without an artifact or tool-backed evidentiary surface, then treats it as verification."),
        "temporal_coherence": ("violation", [42, 54, 58], "Latency is still above target, yet full restoration is recommended immediately and then put back on hold pending a new integrity check."),
        "interaction_structure_fidelity": ("violation", [22, 24, 57], "Sofia says she is still awaiting an ETA after Priya has supplied it, and direct requests to an absent/unregistered Alex Patel cannot receive an answer."),
        "multi_party_dynamics": ("violation", [61, 65, 69], "The group repeatedly restates the same pending checksum owner and closure condition instead of resolving or cleanly deferring it."),
        "procedural_fidelity": ("violation", [47, 54, 55], "A fabricated-looking integrity receipt is accepted, traffic restoration is recommended before the health gate is green, and the final check is reassigned to an unregistered participant."),
    },
    292: {
        "role_strategy": ("clear", [2, 6, 7], "Supplier commercial, quality feasibility, and procurement benchmark responsibilities remain distinguishable throughout the negotiation."),
        "epistemic_fidelity": ("violation", [25, 53, 62], "The dialogue claims documents were dispatched or attached and later cites an attached spreadsheet, although no actual artifact or receipt is present in the supplied evidence."),
        "temporal_coherence": ("clear", [29, 34, 66], "The price-volume condition, provisional inspection feasibility, and later capacity validation form a consistent progression toward confirmation."),
        "interaction_structure_fidelity": ("violation", [40, 44, 56], "Substantially identical requests for the same Thursday feasibility confirmation and supporting figures recur across many turns after responsive provisional answers."),
        "multi_party_dynamics": ("violation", [41, 42, 43], "Late-stage contributions largely repeat the same pending confirmation and benchmark rather than adding distinct negotiation information or closing the loop."),
        "procedural_fidelity": ("clear", [48, 66, 70], "The agreement remains conditional until the quality lead completes cost and capacity checks, after which the relevant terms are explicitly confirmed."),
    },
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    packet = json.loads(Path(args.packet).read_text())
    tasks = packet["tasks"]
    assert len(tasks) == 48
    rows = []
    seen = set()
    for task in tasks:
        size = len(task["evidence_catalog"])
        dim = task["dimension"]
        label, sequences, rationale = DECISIONS[size][dim]
        by_sequence = {}
        for unit in task["evidence_catalog"]:
            previous = by_sequence.get(unit["sequence_no"])
            if previous is None or len(unit["text"]) > len(previous["text"]):
                by_sequence[unit["sequence_no"]] = unit
        citations = [{"evidence_id": by_sequence[seq]["evidence_id"],
                      "sequence_no": seq,
                      "speaker_id": by_sequence[seq]["speaker_id"],
                      "quote": by_sequence[seq]["text"]}
                     for seq in sequences]
        rows.append({"task_id": task["task_id"], "task_sha256": task["sha256"],
                     "dimension": dim, "label": label, "citations": citations,
                     "rationale": rationale, "condition_guess": "not_recorded",
                     "condition_guess_confidence": None})
        seen.add((size, dim))
    assert seen == {(size, dim) for size in DECISIONS for dim in DECISIONS[size]}
    raw = {"schema": "g5-codex-single-expert-review-v1",
           "classification": "internal-development-evidence",
           "reviewer": {"id": "codex-primary-agent-2026-09-12", "kind": "ai"},
           "independent_human_reference": False,
           "human_annotations_collected": 0,
           "scientific_limitations": [
               "This is one AI expert pass, not two independent human ratings.",
               "It cannot establish inter-rater reliability or human-grounded scorer accuracy.",
               "The reviewer had access only to the blinded reviewer packet during labeling, but model-family independence is not claimed.",
               "Use for development diagnosis only; do not use as confirmatory-study reference truth."],
           "packet_sha256": packet["sha256"], "rows": rows,
           "summary": {"cases": len(rows), "labels": dict(sorted(Counter(r["label"] for r in rows).items())),
                       "dimensions": dict(sorted(Counter(r["dimension"] for r in rows).items()))}}
    result = {**raw, "sha256": digest(raw)}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"output": str(output), "sha256": result["sha256"], **result["summary"]}, sort_keys=True))


if __name__ == "__main__":
    main()
