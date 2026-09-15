"""Raw delivery equality is tested separately from cognition's retained memory."""
import copy
import json
import unittest

from app.factorial_study import ARMS, digest, freeze_design
from app.g5.memory import MemoryCognition
from app.g5.observation import ObservationWindow
from app.g5.runtime import Runtime, Review
from app.g5.world import World, Decision, Conflict, canonical
from test_g5_runtime import manifest, spec


def configure(args, window):
    design = copy.deepcopy(args["manifest"]["design"])
    design["observation_window"] = window.runtime_specification()
    for profile in design["arms"].values():
        profile["shared"]["observation_policy_sha256"] = digest(design["observation_window"])
    return {**args, "manifest": freeze_design(design), "observation_window": window}


def options(world, arm, window=None, *, steps=40):
    calls = {"policy": [], "governance": []}
    async def policy(view, feedback):
        calls["policy"].append(copy.deepcopy(view))
        return Decision("speak", f"Agenda {view['observation_delivery']['available_count']}.")
    async def governance(view, decision):
        calls["governance"].append(copy.deepcopy(view))
        return Review(True)
    frozen = manifest(max_steps=steps)
    args = dict(world=world, world_id=arm, spec=spec(), manifest=frozen,
        ordinal=next(a["ordinal"] for a in frozen["assignments"] if a["arm"] == arm),
        max_steps=steps, policy=policy, cognition=MemoryCognition(top_k=2) if ARMS[arm]["cognition"] else None,
        governance=governance if ARMS[arm]["governance"] else None)
    return calls, configure(args, window or ObservationWindow(2, 2048))


class ObservationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.world = World(":memory:")
        self.addCleanup(self.world.close)

    async def test_four_arms_40_turn_delivery_equality_retention_and_no_backfill(self):
        raw_by_arm = {}
        for arm in ARMS:
            calls, args = options(self.world, arm)
            runtime = Runtime(**args)
            for _ in range(40):
                await runtime.step()
            self.assertEqual((await runtime.step())["status"], "cutoff")
            events = self.world.events(arm)
            raw_by_arm[arm] = [[(o["actor"], o["content"]) for o in v["observations"]] for v in calls["policy"]]
            for index, (event, view) in enumerate(zip(events, calls["policy"])):
                receipt = event["payload"]["audit"]["observation_delivery"]
                self.assertEqual(receipt["delivered_sha256"], digest(view["observations"]))
                self.assertEqual(receipt["available_count"], index)
                self.assertLessEqual(len(view["observations"]), 2)
                self.assertEqual(view["observation_delivery"]["omitted_count"], max(0, index - 2))
                self.assertNotIn("visible_history_sha256", view)
                self.assertNotIn("secret" if view["actor"] == "sre" else "staffing", view["facts"])
                if ARMS[arm]["governance"]:
                    self.assertEqual(calls["governance"][index]["observations"], view["observations"])
            for actor in runtime.roles:
                consumed = {source for e in events if e["payload"]["actor"] == actor
                            for source in e["payload"]["audit"]["observation_delivery"]["delivered_ids"]}
                memory = self.world.observe(arm, actor)[1]["cognition_state"]
                if ARMS[arm]["cognition"]:
                    self.assertEqual({n["source"] for n in memory["nodes"] if n["kind"] == "claim"}, consumed)
                    self.assertGreater(len(consumed), 2)
                else:
                    self.assertEqual(memory, {})
            self.assertEqual(len(self.world.observe(arm, "sre")[1]["observations"]), 40)
        for arm in ARMS:
            self.assertEqual(raw_by_arm[arm], raw_by_arm["A"])

    async def test_cold_cognition_cannot_retrieve_omitted_preexisting_history(self):
        for arm in ("B", "D"):
            calls, args = options(self.world, arm)
            runtime = Runtime(**args)
            for index in range(12):
                self.world.commit(arm, expected_version=index, request_id=f"seed-{index}", actor="security",
                    decision=Decision("speak", f"Seeded claim {index}"), audit={})
            result = await runtime.step()
            state = result["event"]["payload"]["audit"]["cognition_state"]
            claims = [json.loads(n["text"])["content"] for n in state["nodes"] if n["kind"] == "claim"]
            self.assertEqual(claims, ["Seeded claim 10", "Seeded claim 11"])

    async def test_character_limit_keeps_whole_suffix_and_oversize_records_failure(self):
        observations = [{"event_id": str(i), "kind": "claim", "actor": "sre", "content": "证据" * (i + 1)} for i in range(3)]
        capacity = len(canonical(observations[-2:]))
        view, receipt = ObservationWindow(3, capacity).apply({"observations": observations})
        self.assertEqual(view["observations"], observations[-2:])
        self.assertEqual(receipt["json_chars"], capacity)
        for arm in ARMS:
            calls, args = options(self.world, arm, ObservationWindow(2, 2))
            runtime = Runtime(**args)
            await runtime.step()
            before = self.world.events(arm)
            with self.assertRaises(ValueError):
                await runtime.step()
            self.assertEqual(self.world.events(arm), before)
            self.assertEqual(len(calls["policy"]), 1)
            self.assertTrue(any(a["stage"] == "observation" and a["status"] == "failed" for a in self.world.attempts(arm)))

    async def test_drift_unfrozen_mode_and_legacy_world_rebinding_rejected(self):
        calls, args = options(self.world, "A")
        runtime = Runtime(**args)
        runtime.observation_window = ObservationWindow(3, 2048)
        with self.assertRaises(ValueError):
            await runtime.step()
        self.assertEqual(calls["policy"], [])
        changed = copy.deepcopy(args["manifest"]["design"])
        changed["arms"]["D"]["shared"]["observation_policy_sha256"] = digest("unequal")
        with self.assertRaises(ValueError):
            freeze_design(changed)
        with self.assertRaises(ValueError):
            Runtime(**{**args, "observation_window": None})
        legacy = manifest(max_steps=40)
        legacy_args = {**args, "manifest": legacy, "observation_window": None, "world_id": "legacy"}
        Runtime(**legacy_args)
        with self.assertRaises(Conflict):
            Runtime(**{**args, "world_id": "legacy"})

    async def test_reconstruction_preserves_delivered_memory_and_next_turn(self):
        calls, args = options(self.world, "B")
        runtime = Runtime(**args)
        for _ in range(20):
            await runtime.step()
        before = self.world.events("B")
        calls, args = options(self.world, "B")
        runtime = Runtime(**args)
        result = await runtime.step()
        self.assertEqual(self.world.events("B")[:20], before)
        self.assertEqual(result["event"]["payload"]["audit"]["observation_delivery"]["omitted_count"], 18)
        self.assertGreater(len(result["event"]["payload"]["audit"]["cognition_state"]["nodes"]), 2)
