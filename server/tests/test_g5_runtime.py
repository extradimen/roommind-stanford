"""Local reference-loop integration tests: no cloud calls or staging mutation."""
import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.factorial_study import ARMS, SHARED_FIELDS, PROTOCOL, digest, freeze_design
from app.g5.world import Conflict, Decision, World, WORLD_CONTRACT_SHA256, validate_spec
from app.g5.runtime import Review, Runtime


def spec():
    return {"roles": ["security", "sre"], "facts": {
        "preserved": {"value": False, "visible_to": None, "disclosable": True},
        "contained": {"value": False, "visible_to": None, "disclosable": True},
        "staffing": {"value": "two missing shifts", "visible_to": ["sre"], "disclosable": True},
        "secret": {"value": "protected-source", "visible_to": ["security"], "disclosable": False},
    }, "actions": {
        "preserve": {"actors": ["security"], "requires": {}, "effects": {"preserved": True},
                     "outcome": "success", "visible_to": None},
        "contain": {"actors": ["sre"], "requires": {"preserved": True},
                    "effects": {"contained": True}, "outcome": "success", "visible_to": None},
        "fail": {"actors": ["sre"], "requires": {}, "effects": {"contained": True},
                 "outcome": "failed", "visible_to": None},
    }}


def manifest(max_steps=4, max_revisions=1):
    shared = {key: digest(key) for key in SHARED_FIELDS}
    shared["world_sha256"] = WORLD_CONTRACT_SHA256
    shared["stopping_policy_sha256"] = digest({"max_steps": max_steps, "max_revisions": max_revisions})
    return freeze_design({"protocol": PROTOCOL, "source_revision": "a" * 40,
        "stage": "exploration", "scenarios": [{"id": "case", "family": "incident",
                                                "snapshot_sha256": digest(spec())}],
        "used_families": [], "repetitions": 1, "order_seed": 1,
        "sampling_seed_policy": "unsupported_recorded", "analysis_plan_sha256": "b" * 64,
        "sample_size_plan_sha256": "c" * 64,
        "arms": {arm: {**flags, "shared": copy.deepcopy(shared)} for arm, flags in ARMS.items()}})


class WorldTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "world.sqlite")
        self.world = World(self.path)
        self.world.create("w", spec(), {"test": True})

    def tearDown(self):
        self.world.close()
        self.tmp.cleanup()

    def commit(self, actor, decision, request=None, audit=None):
        version = len(self.world.events("w"))
        return self.world.commit("w", expected_version=version, request_id=request or str(version),
                                 actor=actor, decision=decision, audit=audit or {})

    def test_claims_are_not_facts_and_private_information_is_partitioned(self):
        self.commit("security", Decision("speak", "Containment is complete."))
        _, sre = self.world.observe("w", "sre")
        _, security = self.world.observe("w", "security")
        self.assertFalse(sre["facts"]["contained"]["value"])
        self.assertNotIn("secret", sre["facts"])
        self.assertNotIn("staffing", security["facts"])
        self.assertTrue(sre["facts"]["staffing"]["disclosable"])
        self.assertEqual(sre["observations"][0]["kind"], "claim")
        sre["facts"]["contained"]["value"] = True
        self.assertFalse(self.world.facts("w")["contained"]["value"])

    def test_authority_prerequisites_failure_and_exact_effects(self):
        for actor, operation, status in [("sre", "preserve", "blocked"),
                                         ("sre", "contain", "blocked"),
                                         ("security", "preserve", "success"),
                                         ("sre", "fail", "failed"),
                                         ("sre", "contain", "success")]:
            event = self.commit(actor, Decision("execute", operation=operation))
            self.assertEqual(event["payload"]["receipt"]["status"], status)
            if status != "success":
                self.assertEqual(event["payload"]["receipt"]["effects"], {})
        facts = self.world.facts("w")
        self.assertTrue(facts["contained"]["value"])
        self.assertEqual(facts["contained"]["source"], event["event_id"])
        self.assertEqual(facts["staffing"]["source"], "scenario")

    def test_restart_idempotency_stale_writer_and_immutable_log(self):
        event = self.commit("security", Decision("execute", operation="preserve"), "stable")
        self.world.close()
        self.world = World(self.path)
        again = self.world.commit("w", expected_version=0, request_id="stable", actor="security",
                                  decision=Decision("execute", operation="preserve"), audit={})
        self.assertEqual(event, again)
        self.assertEqual(len(self.world.events("w")), 1)
        with self.assertRaises(Conflict):
            self.world.commit("w", expected_version=0, request_id="new", actor="sre",
                              decision=Decision("wait"), audit={})
        with self.assertRaises(Conflict):
            self.commit("sre", Decision("wait"), "stable")
        with self.assertRaises(sqlite3.IntegrityError):
            self.world.db.execute("UPDATE g5_events SET seq=9")
        with self.assertRaises(sqlite3.IntegrityError):
            self.world.db.execute("DELETE FROM g5_events")

    def test_frozen_world_and_cross_world_isolation(self):
        changed = spec()
        changed["facts"]["preserved"]["value"] = True
        with self.assertRaises(Conflict):
            self.world.create("w", changed, {"test": True})
        self.commit("security", Decision("execute", operation="preserve"))
        self.world.create("other", spec(), {"test": True})
        self.assertFalse(self.world.facts("other")["preserved"]["value"])

    def test_receipt_cannot_declassify_private_facts(self):
        bad = spec()
        bad["actions"]["preserve"]["effects"]["secret"] = "leak"
        with self.assertRaises(ValueError):
            validate_spec(bad)

    def test_private_receipts_and_cognition_are_not_public_observations(self):
        cfg = spec()
        cfg["actions"]["private"] = {"actors": ["security"], "requires": {},
            "effects": {"secret": "new-protected-source"}, "outcome": "success",
            "visible_to": ["security"]}
        self.world.create("private-world", cfg, {})
        self.world.commit("private-world", expected_version=0, request_id="private",
            actor="security", decision=Decision("execute", operation="private"),
            audit={"cognition_state": {"reflection": "my confidential inference"}})
        _, security = self.world.observe("private-world", "security")
        _, sre = self.world.observe("private-world", "sre")
        self.assertEqual(security["facts"]["secret"]["value"], "new-protected-source")
        self.assertEqual(security["cognition_state"]["reflection"], "my confidential inference")
        self.assertEqual(sre["observations"], [])
        self.assertEqual(sre["cognition_state"], {})
        self.assertNotIn("secret", sre["facts"])

    def test_atomic_insert_failure_does_not_create_facts_or_consume_request(self):
        self.world.db.executescript("""CREATE TRIGGER fail_insert BEFORE INSERT ON g5_events
            BEGIN SELECT RAISE(ABORT, 'simulated disk failure'); END;""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.commit("security", Decision("execute", operation="preserve"), "same")
        self.assertEqual(self.world.events("w"), [])
        self.assertFalse(self.world.facts("w")["preserved"]["value"])
        self.world.db.execute("DROP TRIGGER fail_insert")
        self.commit("security", Decision("execute", operation="preserve"), "same")
        self.assertTrue(self.world.facts("w")["preserved"]["value"])

    def test_independent_writer_rejects_stale_observation(self):
        other = World(self.path)
        try:
            version, _ = other.observe("w", "sre")
            self.commit("security", Decision("speak", "New evidence arrived."))
            with self.assertRaises(Conflict):
                other.commit("w", expected_version=version, request_id="stale", actor="sre",
                             decision=Decision("speak", "I have not seen any evidence."), audit={})
            self.assertEqual(len(other.events("w")), 1)
        finally:
            other.close()

    def test_hash_chain_detects_corruption(self):
        self.commit("security", Decision("wait"))
        # Simulate file corruption/privileged tampering beyond append-only access.
        self.world.db.execute("DROP TRIGGER g5_events_no_update")
        self.world.db.execute("UPDATE g5_events SET event_hash='broken'")
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.world.observe("w", "sre")


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    def make_runtime(self, world, arm, policy, cognition=None, governance=None, max_steps=4):
        frozen = manifest(max_steps)
        ordinal = next(r["ordinal"] for r in frozen["assignments"] if r["arm"] == arm)
        return Runtime(world=world, world_id=arm, spec=spec(), manifest=frozen, ordinal=ordinal,
                       policy=policy, max_steps=max_steps, cognition=cognition, governance=governance)

    async def test_all_four_arms_share_observation_order_and_world_permissions(self):
        for arm, switches in ARMS.items():
            with self.subTest(arm=arm):
                world = World(":memory:")
                self.addCleanup(world.close)
                calls, actors = [], []

                async def cognition(view):
                    calls.append("cognition")
                    return {"hypothesis": "not ground truth", "actor": view["actor"]}

                async def governance(view, decision):
                    calls.append("governance")
                    return Review(True)

                async def policy(view, feedback):
                    actors.append(view["actor"])
                    if len(actors) == 1:
                        return Decision("speak", "SRE, preserve evidence please.")
                    self.assertEqual(view["observations"][0]["content"], "SRE, preserve evidence please.")
                    self.assertNotIn("secret", view["facts"])
                    self.assertNotIn("cognition_state", view)
                    return Decision("execute", operation="preserve")

                runtime = self.make_runtime(world, arm, policy,
                    cognition if switches["cognition"] else None,
                    governance if switches["governance"] else None)
                await runtime.step()
                result = await runtime.step()
                self.assertEqual(actors, ["security", "sre"])
                self.assertEqual(result["event"]["payload"]["receipt"]["status"], "blocked")
                self.assertEqual(calls.count("cognition"), 2 * switches["cognition"])
                self.assertEqual(calls.count("governance"), 2 * switches["governance"])

    async def test_governance_repair_is_same_actor_and_exhaustion_is_not_fake_speech(self):
        world = World(":memory:")
        self.addCleanup(world.close)
        attempts = []

        async def policy(view, feedback):
            attempts.append((view["actor"], feedback))
            return Decision("speak", "Unsupported completion.")

        async def reject(view, decision):
            return Review(False, "No matching receipt; ask for execution or report unknown.")

        runtime = self.make_runtime(world, "C", policy, governance=reject)
        result = await runtime.step()
        self.assertEqual([row[0] for row in attempts], ["security", "security"])
        self.assertEqual(len(attempts[1][1]), 1)
        self.assertEqual(result["event"]["payload"]["audit"]["outcome"], "unresolved_after_revisions")
        self.assertEqual(world.observe("C", "sre")[1]["observations"], [])

    async def test_restart_cursor_and_private_cognition_and_cutoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "recovery.sqlite")
            calls = []

            async def cognition(view):
                return {"count": view["cognition_state"].get("count", 0) + 1}

            async def policy(view, feedback):
                calls.append((view["actor"], view["cognition"]["count"]))
                return Decision("execute", operation="preserve") if len(calls) == 1 else Decision("wait")

            world = World(path)
            runtime = self.make_runtime(world, "B", policy, cognition, max_steps=3)
            await runtime.step()
            first = world.events("B")[0]["event_id"]
            world.close()
            world = World(path)
            try:
                runtime = self.make_runtime(world, "B", policy, cognition, max_steps=3)
                await runtime.step()
                await runtime.step()
                cutoff = await runtime.step()
                self.assertEqual(calls, [("security", 1), ("sre", 1), ("security", 2)])
                self.assertEqual(world.events("B")[0]["event_id"], first)
                self.assertEqual(len(world.events("B")), 3)
                self.assertEqual(cutoff, {"status": "cutoff", "reason": "step_limit", "task_completed": False})
            finally:
                world.close()

    async def test_provider_error_does_not_advance_cursor(self):
        world = World(":memory:")
        self.addCleanup(world.close)

        async def broken(view, feedback):
            raise TimeoutError("technical transport failure")

        runtime = self.make_runtime(world, "A", broken)
        with self.assertRaises(TimeoutError):
            await runtime.step()
        self.assertEqual(world.events("A"), [])

    async def test_accepted_revision_preserves_actor_and_disclosable_fact(self):
        world = World(":memory:")
        self.addCleanup(world.close)

        async def policy(view, feedback):
            if view["actor"] == "security":
                return Decision("wait")
            if not feedback:
                return Decision("speak", "Staffing is ready.")
            return Decision("speak", view["facts"]["staffing"]["value"])

        async def governance(view, decision):
            if decision.content == "Staffing is ready.":
                return Review(False, "Report the known staffing gap instead of readiness.")
            return Review(True)

        runtime = self.make_runtime(world, "C", policy, governance=governance)
        await runtime.step()
        result = await runtime.step()
        self.assertEqual(result["event"]["payload"]["actor"], "sre")
        _, view = world.observe("C", "security")
        self.assertEqual([x["content"] for x in view["observations"]], ["two missing shifts"])
        # Disclosure is a public claim; it does not silently promote it to global fact.
        self.assertNotIn("staffing", view["facts"])

    async def test_slow_policy_cannot_publish_after_another_writer_advances(self):
        world = World(":memory:")
        self.addCleanup(world.close)

        async def concurrent(view, feedback):
            world.commit("A", expected_version=0, request_id="step:1", actor="security",
                         decision=Decision("wait"), audit={})
            return Decision("speak", "Stale draft")

        runtime = self.make_runtime(world, "A", concurrent)
        with self.assertRaises(Conflict):
            await runtime.step()
        self.assertEqual(len(world.events("A")), 1)
        self.assertEqual(world.observe("A", "sre")[1]["observations"], [])

    async def test_disabled_adapter_cannot_run_and_world_mismatch_fails(self):
        world = World(":memory:")
        self.addCleanup(world.close)

        async def policy(view, feedback):
            return Decision("wait")

        async def cognition(view):
            return {}

        with self.assertRaises(ValueError):
            self.make_runtime(world, "A", policy, cognition)
        with self.assertRaises(ValueError):
            self.make_runtime(world, "D", policy)
        frozen = manifest()
        changed = spec()
        changed["facts"]["contained"]["value"] = True
        ordinal = next(r["ordinal"] for r in frozen["assignments"] if r["arm"] == "A")
        with self.assertRaises(ValueError):
            Runtime(world=world, world_id="invalid", spec=changed, manifest=frozen,
                    ordinal=ordinal, policy=policy, max_steps=4)

    async def test_multiple_scenario_inputs_share_engine_not_identical_facts(self):
        world = World(":memory:")
        self.addCleanup(world.close)
        design = manifest()["design"]
        second = spec()
        second["facts"]["preserved"]["value"] = True
        design["scenarios"].append({"id": "second", "family": "incident",
                                    "snapshot_sha256": digest(second)})
        frozen = freeze_design(design)

        async def policy(view, feedback):
            return Decision("wait")

        for scenario_id, snapshot, expected in (("case", spec(), False), ("second", second, True)):
            ordinal = next(row["ordinal"] for row in frozen["assignments"]
                           if row["arm"] == "A" and row["scenario_id"] == scenario_id)
            runtime = Runtime(world=world, world_id=scenario_id, spec=snapshot,
                              manifest=frozen, ordinal=ordinal, policy=policy, max_steps=4)
            await runtime.step()
            self.assertEqual(world.facts(scenario_id)["preserved"]["value"], expected)


if __name__ == "__main__":
    unittest.main()
