"""Research provenance and blinded-review contracts.

This module deliberately contains no dialogue-generation logic.  It describes
the architecture that generated a run and binds later ratings to the exact
public transcript that was observed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CURRENT_GENERATION_ID = "G3.3"
CURRENT_ARCHITECTURE_VERSION = "g3.3-contextual-speech-boundary-ledger-simulation"
EXPERIMENT_PROTOCOL_VERSION = "roommind-generational-experiment-v1"
HUMAN_REVIEW_PROTOCOL_VERSION = "blinded-bilingual-expert-review-v4"

STUDY_PHASES = {"exploration", "screening", "confirmation"}


REALISM_RUBRIC: dict[str, dict[str, Any]] = {
    "role_strategic_fidelity": {
        "label_en": "Role & strategic fidelity",
        "label_zh": "角色与策略忠实度",
        "description_en": "Do participants behave like distinct business roles with stable interests, responsibilities, and authority?",
        "description_zh": "参与者是否像具有稳定利益、职责与权限的不同商务角色？",
        "indicators": [
            ("role_identity", "Role identity and professional behavior", "角色身份与职业行为"),
            ("strategic_consistency", "Strategic interests remain consistent", "策略利益前后一致"),
            ("authority_discipline", "Statements and commitments respect role authority", "发言与承诺符合角色权限"),
        ],
    },
    "epistemic_fidelity": {
        "label_en": "Information boundaries",
        "label_zh": "信息边界真实性",
        "description_en": "Do participants know, disclose, and infer only what their roles plausibly allow?",
        "description_zh": "参与者是否只知道、披露和推断其角色合理可获得的信息？",
        "indicators": [
            ("knowledge_scope", "Knowledge matches role and evidence", "知识范围符合角色与证据"),
            ("private_information", "Private information is not improperly shared", "私有信息未被不当共享"),
            ("unsupported_claims", "No invented facts or unjustified precision", "没有虚构事实或无依据的精确数字"),
        ],
    },
    "temporal_coherence": {
        "label_en": "Temporal coherence",
        "label_zh": "时序连贯性",
        "description_en": "Does the conversation retain earlier facts, commitments, and unresolved issues without contradiction?",
        "description_zh": "对话是否保留先前事实、承诺与未决事项，且不发生矛盾？",
        "indicators": [
            ("agreement_retention", "Earlier agreements are retained", "先前协议得到保留"),
            ("context_continuity", "Replies use the relevant preceding context", "回应使用相关的前序语境"),
            ("contradiction_control", "Few unexplained reversals or contradictions", "很少出现无解释的反转或矛盾"),
        ],
    },
    "interaction_structure_fidelity": {
        "label_en": "Interaction structure",
        "label_zh": "互动结构真实性",
        "description_en": "Are speaker selection, turn-taking, and responses plausible for a real multi-person meeting?",
        "description_zh": "发言人选择、轮流发言和回应方式是否符合真实多人会议？",
        "indicators": [
            ("speaker_relevance", "The relevant role speaks at the right time", "相关角色在合适时间发言"),
            ("response_directness", "Utterances respond directly to current issues", "发言直接回应当前议题"),
            ("turn_taking", "Turn-taking and interruptions are plausible", "轮流发言与插话方式合理"),
        ],
    },
    "multi_party_dynamics_fidelity": {
        "label_en": "Multi-party dynamics",
        "label_zh": "多方互动真实性",
        "description_en": "Do multiple participants make distinct, interdependent contributions rather than acting as one voice?",
        "description_zh": "多个参与者是否作出有区别且相互依赖的贡献，而非像同一个声音？",
        "indicators": [
            ("distinct_contributions", "Roles contribute distinct information or interests", "各角色贡献不同信息或利益"),
            ("cross_role_response", "Participants react to one another, not only to the player", "参与者相互回应，而非只回应玩家"),
            ("productive_tension", "Disagreement, alignment, and negotiation are plausible", "分歧、结盟与协商合理"),
        ],
    },
    "procedural_fidelity": {
        "label_en": "Procedural fidelity",
        "label_zh": "业务流程真实性",
        "description_en": "Does the meeting follow a plausible domain-neutral business process from evidence to decision and closure?",
        "description_zh": "会议是否遵循从证据到决策再到收尾的合理通用商务流程？",
        "indicators": [
            ("evidence_before_commitment", "Evidence precedes consequential commitments", "重要承诺之前具有证据"),
            ("issue_progression", "Open issues progress rather than loop", "未决事项持续推进而非循环"),
            ("closure_quality", "The ending reflects resolved and unresolved work", "结束方式反映已解决与未解决事项"),
        ],
    },
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def public_transcript_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the exact stored public utterances in stable order.

    Content is never translated, summarized, regenerated, or normalized.
    """
    rows = []
    for message in bundle.get("messages") or []:
        if message.get("speaker_type") not in {"user", "npc"}:
            continue
        rows.append({
            "sequence_no": message.get("sequence_no"),
            "turn_id": message.get("turn_id"),
            "speaker_id": message.get("speaker_id"),
            "speaker_type": message.get("speaker_type"),
            "speaker_source": message.get("speaker_source"),
            "content": message.get("content"),
            "created_at": message.get("created_at"),
        })
    return sorted(rows, key=lambda row: (int(row.get("sequence_no") or 0), int(row.get("turn_id") or 0)))


def transcript_provenance(bundle: dict[str, Any]) -> dict[str, Any]:
    rows = public_transcript_rows(bundle)
    session = bundle.get("session") or {}
    return {
        "source": "persisted_session_messages",
        "content_policy": "verbatim_no_translation_no_regeneration",
        "session_uuid": session.get("session_uuid"),
        "session_status": session.get("status"),
        "message_count": len(rows),
        "transcript_sha256": sha256_json(rows),
    }


def source_revision() -> str:
    """Best-effort Git revision without starting a subprocess in the API."""
    root = Path(__file__).resolve().parents[2]
    git_path = root / ".git"
    try:
        if git_path.is_file():
            pointer = git_path.read_text(encoding="utf-8").strip().split(":", 1)[1].strip()
            git_path = (root / pointer).resolve()
        head = (git_path / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = head.split(":", 1)[1].strip()
            return (git_path / ref).read_text(encoding="utf-8").strip()
        return head
    except (OSError, IndexError):
        return "unrecorded"


def experiment_manifest(*, study_phase: str, random_seed: int) -> dict[str, Any]:
    phase = study_phase if study_phase in STUDY_PHASES else "exploration"
    manifest = {
        "protocol": EXPERIMENT_PROTOCOL_VERSION,
        "generation_id": CURRENT_GENERATION_ID,
        "architecture_version": CURRENT_ARCHITECTURE_VERSION,
        "source_revision": source_revision(),
        "study_phase": phase,
        "evidence_use": {
            "exploration": "development_only",
            "screening": "candidate_selection_only",
            "confirmation": "held_out_confirmatory_evidence",
        }[phase],
        "random_seed": random_seed,
        "immutability": "Dialogue artifacts are append-only; later evaluation references their SHA-256.",
    }
    return {**manifest, "manifest_sha256": sha256_json(manifest)}
