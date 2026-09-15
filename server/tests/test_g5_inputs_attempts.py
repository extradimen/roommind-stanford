import asyncio
import copy
import json
import unittest

from app.factorial_study import freeze_design, digest
from app.g5.attempts import new_record
from app.g5.role_inputs import actor_view, validate_inputs
from app.g5.runtime import Runtime
from app.g5.structured_output import StructuredOutputError, capsule
from app.g5.world import Decision, World
from test_g5_runtime import manifest, spec


def cards():
    return {role: {"public": {"name": role, "job_title": role, "side": "internal", "kind": "npc"},
                   "private": {"persona": "careful", "goals": [role + "-only-goal"],
                               "instructions": role + "-only-instructions"}}
            for role in spec()["roles"]}


class RoleInputTests(unittest.TestCase):
    def test_only_own_private_card_is_visible_and_input_is_detached(self):
        inputs = cards()
        view = {"actor": "sre", "participants": spec()["roles"]}
        result = actor_view(view, inputs)
        self.assertNotIn("security-only-goal", json.dumps(result))
        self.assertIn("sre-only-goal", json.dumps(result))
        result["own_role"]["private"]["goals"].append("changed")
        self.assertEqual(inputs, cards())

    def test_undefined_roles_or_unclassified_fields_fail(self):
        for mutate in (lambda c: c.pop("sre"),
                       lambda c: c["security"].update(unclassified_secrets="x"),
                       lambda c: c["sre"]["public"].update(private_goals="x")):
            inputs = cards()
            mutate(inputs)
            with self.assertRaises(ValueError):
                validate_inputs(inputs, spec()["roles"])


class AttemptTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.world = World(":memory:")
        self.addCleanup(self.world.close)

    def runtime(self, policy, inputs=None):
        design = manifest()["design"]
        if inputs is not None:
            for arm in design["arms"].values():
                arm["shared"]["role_inputs_sha256"] = digest(inputs)
        frozen = freeze_design(design)
        ordinal = next(r["ordinal"] for r in frozen["assignments"] if r["arm"] == "A")
        return Runtime(world=self.world, world_id="attempt", spec=spec(), manifest=frozen,
                       ordinal=ordinal, policy=policy, max_steps=4, role_inputs=inputs)

    async def test_cards_reach_policy_and_mutation_cannot_leak_to_next_role(self):
        seen = []

        async def policy(view, feedback):
            seen.append(copy.deepcopy(view))
            view["own_role"]["private"]["goals"].append("tampered")
            return Decision("wait")

        runtime = self.runtime(policy, cards())
        await runtime.step()
        await runtime.step()
        self.assertNotIn("security-only-goal", json.dumps(seen[1]))
        self.assertNotIn("tampered", json.dumps(runtime.role_inputs))

    async def test_invalid_model_response_is_failed_not_successful_attempt(self):
        async def invalid(view, feedback):
            return {"action": "speak", "content": "invalid adapter output"}

        runtime = self.runtime(invalid)
        with self.assertRaises(ValueError):
            await runtime.step()
        records = self.world.attempts("attempt")
        self.assertEqual([r["status"] for r in records], ["started", "failed"])
        self.assertEqual(self.world.events("attempt"), [])

    async def test_rejected_structured_body_is_retained_only_in_attempt_journal(self):
        failure = capsule("policy", 0, "a" * 64, '{"action":"bad"}',
                          "Invalid decision fields")
        async def invalid(view, feedback):
            raise StructuredOutputError("Invalid decision fields", [failure])

        runtime = self.runtime(invalid)
        with self.assertRaises(StructuredOutputError):
            await runtime.step()
        records = self.world.attempts("attempt")
        self.assertEqual(records[-1]["structured_failures"], [failure])
        self.assertEqual(self.world.events("attempt"), [])

    async def test_role_card_change_cannot_reuse_frozen_manifest(self):
        async def policy(view, feedback):
            return Decision("wait")

        design = manifest()["design"]
        original = cards()
        for arm in design["arms"].values():
            arm["shared"]["role_inputs_sha256"] = digest(original)
        frozen = freeze_design(design)
        ordinal = next(r["ordinal"] for r in frozen["assignments"] if r["arm"] == "A")
        changed = cards()
        changed["sre"]["private"]["goals"].append("changed goal")
        with self.assertRaisesRegex(ValueError, "frozen design"):
            Runtime(world=self.world, world_id="changed", spec=spec(), manifest=frozen,
                    ordinal=ordinal, policy=policy, max_steps=4, role_inputs=changed)

    async def test_cancelled_call_and_orphan_start_are_retained(self):
        async def cancelled(view, feedback):
            raise asyncio.CancelledError()

        runtime = self.runtime(cancelled)
        self.world.record_attempt("attempt", new_record("policy", 0, "security"))
        with self.assertRaises(asyncio.CancelledError):
            await runtime.step()
        records = self.world.attempts("attempt")
        self.assertEqual([r["status"] for r in records], ["started", "started", "cancelled"])
        self.assertEqual(self.world.events("attempt"), [])

    async def test_committed_step_survives_missing_final_journal_entry(self):
        async def policy(view, feedback):
            return Decision("wait")

        runtime = self.runtime(policy)
        original = self.world.record_attempt

        def fail_final(world_id, record):
            if record["stage"] == "commit" and record["status"] == "succeeded":
                raise ConnectionError("journal unavailable after commit")
            original(world_id, record)

        self.world.record_attempt = fail_final
        with self.assertRaises(ConnectionError):
            await runtime.step()
        self.assertEqual(len(self.world.events("attempt")), 1)
        self.world.record_attempt = original
        result = await runtime.step()
        self.assertEqual(result["event"]["payload"]["actor"], "sre")
        self.assertEqual(len(self.world.events("attempt")), 2)

    async def test_lost_commit_acknowledgement_is_indeterminate_not_false_failure(self):
        async def policy(view, feedback):
            return Decision("wait")

        runtime = self.runtime(policy)
        original = self.world.commit

        def lost_ack(*args, **kwargs):
            original(*args, **kwargs)
            raise ConnectionError("acknowledgement lost after database commit")

        self.world.commit = lost_ack
        with self.assertRaises(ConnectionError):
            await runtime.step()
        self.assertEqual(self.world.attempts("attempt")[-1]["status"], "indeterminate")
        self.world.commit = original
        result = await runtime.step()
        self.assertEqual(result["event"]["payload"]["actor"], "sre")
        self.assertEqual(len(self.world.events("attempt")), 2)


if __name__ == "__main__":
    unittest.main()
