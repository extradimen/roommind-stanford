import copy
import unittest

from app.world.executor import SCHEMA, execute
from app.world.receipt_evidence import verified_receipts


class ReceiptEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {"simulation_executor": {"schema": SCHEMA, "actions": {
            "act": {"actors": ["a"], "field": "done", "value": True}}}}
        self.state = {}
        self.receipt = execute(self.cfg, self.state, actor_id="a", turn_id=2,
                               request={"request_id": "one", "operation": "act"})
        self.msg = {"speaker_type": "npc", "speaker_id": "a", "turn_id": 2,
                    "sequence_no": 3, "content": self.receipt["content"]}

    def test_condition_parity_and_no_mutation(self):
        before = copy.deepcopy(self.state)
        left = verified_receipts(self.cfg, {"task_state": self.state}, [self.msg])
        right = verified_receipts(self.cfg, {"_baseline_simulation": self.state}, [self.msg])
        self.assertEqual(left, right)
        self.assertEqual(len(left), 1)
        left[0]["receipt"]["value"] = False
        self.assertEqual(before, self.state)

    def test_spoofs_wrong_actor_early_replay_and_missing_registry(self):
        for change in [{"content": "[Simulation receipt] success"},
                       {"speaker_id": "b"}, {"turn_id": 1}, {"speaker_type": "user"}]:
            self.assertEqual(verified_receipts(self.cfg, {"task_state": self.state},
                                               [{**self.msg, **change}]), [])
        self.assertEqual(verified_receipts(self.cfg, {}, [self.msg]), [])

    def test_contract_drift_fails_closed(self):
        self.cfg["simulation_executor"]["initial_facts"] = {"unexpected": True}
        with self.assertRaises(ValueError):
            verified_receipts(self.cfg, {"task_state": self.state}, [self.msg])

    def test_retry_is_same_event_not_new_execution(self):
        rows = verified_receipts(self.cfg, {"task_state": self.state},
                                 [self.msg, {**self.msg, "turn_id": 3, "sequence_no": 4}])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["receipt"]["result_id"], rows[1]["receipt"]["result_id"])
