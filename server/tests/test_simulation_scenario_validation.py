import tempfile
import unittest
from pathlib import Path

from scripts.build_simulation_scenarios import build
from scripts.validate_simulation_scenarios import validate


class SimulationScenarioValidationTests(unittest.TestCase):
    def test_v3_is_valid_and_only_live_operation_has_executor(self):
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "world-v3"
            build(root, output, 3)
            self.assertEqual(validate(output), [])
            scenarios = list(output.glob("*-world-v3.json"))
            self.assertEqual(len(scenarios), 4)
            enabled = [path for path in scenarios if '"simulation_executor"' in path.read_text()]
            self.assertEqual([path.name for path in enabled],
                             ["incident-response-command-world-v3.json"])
