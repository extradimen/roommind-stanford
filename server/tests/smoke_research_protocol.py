"""Pure-Python checks for transcript authenticity and bilingual review schema."""

from app.external_observer import build_blinded_evaluation_packet
from app.research_protocol import REALISM_RUBRIC, transcript_provenance
from app.research_probes import run_integrity_probes


def main() -> None:
    bundle = {
        "session": {"session_uuid": "real-session-1", "status": "completed"},
        "scenario": {"id": 1, "slug": "case", "title": "Case", "task_config": {}},
        "speaker_directory": {
            "user": {"role": "user", "job_title": "Player"},
            "ceo": {"role": "npc", "job_title": "CEO", "interaction_role": "decision_maker", "authority": {}},
        },
        "messages": [
            {"sequence_no": 2, "turn_id": 1, "speaker_id": "ceo", "speaker_type": "npc", "speaker_source": "ai", "content": "Exact reply", "created_at": "2026-01-01T00:00:02Z"},
            {"sequence_no": 1, "turn_id": 1, "speaker_id": "user", "speaker_type": "user", "speaker_source": "ai", "content": "Exact prompt", "created_at": "2026-01-01T00:00:01Z"},
            {"sequence_no": 3, "turn_id": 1, "speaker_id": "system", "speaker_type": "system", "speaker_source": "system", "content": "hidden"},
        ],
        "external_observation": {"system_claim": {"status": "completed"}},
    }
    provenance = transcript_provenance(bundle)
    packet = build_blinded_evaluation_packet(bundle)
    assert provenance["message_count"] == 2
    assert len(provenance["transcript_sha256"]) == 64
    assert [row["content"] for row in packet["public_transcript"]] == ["Exact prompt", "Exact reply"]
    assert packet["source_provenance"]["transcript_sha256"] == provenance["transcript_sha256"]
    assert "session_uuid" not in packet["source_provenance"]
    assert packet["condition_hidden"] is True
    assert packet["speaker_aliases"]["ceo"] == "Participant A"
    assert len(REALISM_RUBRIC) == 6
    assert all(len(row["indicators"]) == 3 for row in REALISM_RUBRIC.values())
    assert all(row["label_en"] and row["label_zh"] for row in REALISM_RUBRIC.values())
    probes = run_integrity_probes(bundle)
    assert probes["checks"]["sequence_numbers_strictly_increasing"] is False
    assert probes["checks"]["all_public_speakers_registered"] is True


if __name__ == "__main__":
    main()
