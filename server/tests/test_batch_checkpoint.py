import unittest
from types import SimpleNamespace as Row
from app.world.batch_checkpoint import resume_position


class CheckpointTests(unittest.TestCase):
    def fixture(self, condition="test"):
        key = "_baseline_state" if condition == "baseline" else "_test_state"
        return (Row(id=4, scenario_id=2, condition=condition,
                    result={"last_completed_turn_index": 3}),
                Row(scenario_id=2, session_mode=condition, status="active",
                    run_config={"batch_experiment_run_id": 4},
                    shared_state={key: {"completed_turns": 3}}))

    def test_both_conditions_continue(self):
        for condition in ("test", "baseline"):
            self.assertEqual(resume_position(*self.fixture(condition)), (4, []))

    def test_missing_or_wrong_session_rejected(self):
        run, session = self.fixture()
        with self.assertRaises(ValueError):
            resume_position(run, None)
        session.run_config = {}
        with self.assertRaises(ValueError):
            resume_position(run, session)

    def test_counter_drift_rejected(self):
        run, session = self.fixture()
        run.result["last_completed_turn_index"] = 2
        with self.assertRaises(ValueError):
            resume_position(run, session)

    def test_terminal_no_speech_boundary(self):
        run, session = self.fixture()
        session.status = "stopped"
        self.assertEqual(resume_position(run, session), (4, []))
        run.result["last_completed_turn_index"] = 4
        with self.assertRaises(ValueError):
            resume_position(run, session)
