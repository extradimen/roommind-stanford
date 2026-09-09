"""Expected owners are specified independently of the runtime detector."""
import unittest
from app.agent.speech_safety import resolve_direct_question_targets


class TargetTests(unittest.TestCase):
    def test_explicit_groups_and_incidental_mentions(self):
        aliases = {"a": ["Alice"], "b": ["Bob"], "c": ["Carol"], "user": ["Alex"]}
        cases = [
            ("Alice and Bob, can you each give your assessment?", ["a", "b"]),
            ("Bob, Alice, and Carol: please confirm your responsibilities.", ["b", "a", "c"]),
            ("Alice, can you review Bob's proposal?", ["a"]),
            ("Alice, please answer. Bob, can you confirm?", ["a", "b"]),
            ("Alice and Bob finished their discussion.", []),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(resolve_direct_question_targets(text, participant_aliases=aliases), expected)


if __name__ == "__main__":
    unittest.main()
