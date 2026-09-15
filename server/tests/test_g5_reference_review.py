"""Blinded independent reference-review workflow tests; no human contact."""
import copy
import unittest

from app.g5.reference_review import adjudication_packet, build_panel, reviewer_packet, validate_submission


def cases():
    values = []
    dimensions = ["role_strategy", "epistemic_fidelity", "temporal_coherence",
        "interaction_structure_fidelity", "multi_party_dynamics", "procedural_fidelity"]
    for index in range(6):
        task = {"case_id": f"legacy-{index}", "dimension": dimensions[index],
            "rubric": "Respect authority.", "context": {"roster": ["alice", "bob"]},
            "messages": [{"message_id": f"m{index}", "speaker_id": "alice", "turn_id": index + 1,
                "sequence_no": 1, "content": f"Evidence statement {index}."}]}
        values.append({"task": task, "source_family": "secret-family", "source_condition": "RoomMind",
            "source_run_id": 400 + index})
    return values


class ReferenceReviewTests(unittest.TestCase):
    def setUp(self):
        self.panel = build_panel(cases(), "n" * 32)
        self.packets = [reviewer_packet(self.panel, slot["slot_id"]) for slot in self.panel["slots"]]

    def submission(self, packet, reviewer_id, changed=None):
        rows = []
        for task in packet["tasks"]:
            row = {"task_id": task["task_id"], "task_sha256": task["sha256"], "label": "clear",
                "citations": [{"evidence_id": task["evidence_catalog"][0]["evidence_id"],
                    "relevance": "Direct source evidence."}], "rationale": "Source supports the label.",
                "condition_guess": "uncertain", "condition_guess_confidence": 0.2}
            rows.append(row)
        if changed:
            changed(rows)
        return {"schema": "g5-blinded-reference-submission-v1", "slot_id": packet["slot_id"],
            "reviewer": {"id": reviewer_id, "kind": "human"}, "packet_sha256": packet["sha256"],
            "rows": rows}

    def test_packets_have_distinct_order_aliases_and_no_provenance_or_predictions(self):
        self.assertNotEqual([t["task_id"] for t in self.packets[0]["tasks"]],
                            [t["task_id"] for t in self.packets[1]["tasks"]])
        for packet in self.packets:
            rendered = str(packet)
            self.assertNotIn("secret-family", rendered)
            self.assertNotIn("RoomMind", rendered)
            self.assertNotIn("legacy-", rendered)
            self.assertTrue(packet["contains_model_predictions"] is False)
            for task in packet["tasks"]:
                self.assertFalse({"source_case_id", "source_family", "source_condition", "source_run_id",
                                  "reference_label", "prediction"} & set(task))

    def test_complete_source_bound_submission_validates(self):
        submission = self.submission(self.packets[0], "person-a")
        validated = validate_submission(self.packets[0], submission)
        self.assertEqual(len(validated["rows"]), 6)

    def test_missing_duplicate_unknown_and_unbound_rows_rejected(self):
        changes = [lambda rows: rows.pop(), lambda rows: rows.__setitem__(1, copy.deepcopy(rows[0])),
            lambda rows: rows[0]["citations"][0].__setitem__("evidence_id", "E9999"),
            lambda rows: rows[0].__setitem__("citations", [])]
        for change in changes:
            with self.assertRaises(ValueError):
                validate_submission(self.packets[0], self.submission(self.packets[0], "person-a", change))

    def test_only_disagreements_enter_adjudication_and_bind_both_rows(self):
        first = self.submission(self.packets[0], "person-a")
        second = self.submission(self.packets[1], "person-b",
            lambda rows: rows[0].update(label="violation"))
        result = adjudication_packet(self.panel, self.packets, [first, second])
        self.assertEqual(len(result["disagreements"]), 1)
        self.assertEqual(len(result["disagreements"][0]["based_on"]), 2)
        with self.assertRaises(ValueError):
            adjudication_packet(self.panel, self.packets,
                [first, self.submission(self.packets[1], "person-a")])
        changed = copy.deepcopy(self.panel); changed["master"][0]["source_condition"] = "baseline"
        with self.assertRaises(ValueError):
            adjudication_packet(changed, self.packets, [first, second])


if __name__ == "__main__":
    unittest.main()
