"""Synthetic storage, replay, isolation and legacy compatibility checks."""
import copy
import random
import unittest

from app.factorial_study import ARMS, digest, freeze_design
from app.g5.cognition_storage import PROTOCOL, encode, decode, replay
from app.g5.world import World, Decision, canonical, Conflict
from app.g5.runtime import Runtime
from test_g5_runtime import spec, manifest


def storage_options(world, arm="D"):
    from test_g5_capacity import budget_options
    from app.g5.capacity import RequestBudget
    harness, _, _, args = budget_options(world, arm, RequestBudget(100000, 100000))
    design = args["manifest"]["design"]
    design["cognition_storage"] = copy.deepcopy(PROTOCOL)
    args["manifest"] = freeze_design(design)
    return harness, None, args


class StorageTests(unittest.IsolatedAsyncioTestCase):
    async def test_forty_turn_lossless_storage_and_periodic_checkpoints(self):
        from test_g5_capacity import long_probe
        from app.g5.cognition_storage_profile import profile
        world = World(":memory:")
        self.addCleanup(world.close)
        source = await long_probe(world, "D", delta_storage=True)
        report = profile(source)
        self.assertEqual(report["events"], 40)
        self.assertEqual(len(report["states"]), 40)
        self.assertGreater(report["saved_fraction"], .65)
        for actor in source["spec"]["roles"]:
            states = [r for r in report["states"] if r["actor"] == actor]
            self.assertEqual(states[0]["mode"], "checkpoint")
            self.assertEqual(states[16]["mode"], "checkpoint")

    def test_exact_json_tree_reconstruction_and_canonical_types(self):
        rng = random.Random(20260911)
        old = {}
        states = [{"bool": True}, {"bool": 1}, {"bool": 1.0}, {},
                  {"items": list(range(100)), "中文/🙂": {"old": None}},
                  {"items": list(range(100)) + [False, "完整"], "中文/🙂": {"new": []}},
                  {"items": list(range(20))}, {"items": []}]
        states += [{"history": list(range(i)), "changing": rng.choice([False, 0, None, "文字", {}])}
                   for i in range(100)]
        for i, state in enumerate(states, 1):
            kwargs = dict(scope="s", actor="a", base_event=str(i - 1), ordinal=i)
            record = encode(state, old, **kwargs)
            self.assertEqual(canonical(decode(record, old, **kwargs)), canonical(state))
            if (i - 1) % 16 == 0:
                self.assertEqual(record["mode"], "checkpoint")
            old = copy.deepcopy(state)

    def test_wrong_base_owner_scope_hash_and_malformed_patch_rejected(self):
        old = {"items": list(range(100))}
        kwargs = dict(scope="scope", actor="a", base_event="previous", ordinal=2)
        record = encode({"items": list(range(101))}, old, **kwargs)
        self.assertEqual(record["mode"], "delta")
        for key, value in (("scope", "other"), ("actor", "b"), ("base_event", "future"),
                           ("ordinal", True), ("base_sha256", "0" * 64), ("state_sha256", "0" * 64),
                           ("data", ["prefix", -1, []]), ("mode", "unknown")):
            bad = copy.deepcopy(record)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                decode(bad, old, **kwargs)
        with self.assertRaises(ValueError):
            decode(record, {}, **kwargs)

    async def test_store_cas_atomic_rejection_and_historical_role_isolation(self):
        from app.g5.world import Snapshot
        world = World(":memory:")
        self.addCleanup(world.close)
        binding = {"cognition_storage": PROTOCOL}
        world.create("test", spec(), binding)
        scope = digest(["test", binding])
        states = {r: {} for r in spec()["roles"]}
        for i in range(8):
            actor = spec()["roles"][i % 2]
            events = world.events("test")
            old, base, count = replay(binding, "test", events, actor).get(actor, ({}, None, 0))
            state = {"owner": actor, "private": [actor] * (100 + i)}
            record = encode(state, old, scope=scope, actor=actor, base_event=base, ordinal=count + 1)
            kwargs = dict(expected_version=i, request_id=str(i), actor=actor,
                          decision=Decision("wait"), audit={"cognition_called": True, "cognition_state": record})
            broken = copy.deepcopy(kwargs)
            broken["audit"]["cognition_state"]["base_sha256"] = "bad"
            with self.assertRaises(ValueError):
                world.commit("test", **broken)
            self.assertEqual(world.events("test"), events)
            event = world.commit("test", **kwargs)
            self.assertEqual(world.commit("test", **kwargs), event)
            states[actor] = state
            for role in states:
                self.assertEqual(world.observe("test", role)[1]["cognition_state"], states[role])
            historical = Snapshot("test", spec(), binding, events)
            self.assertEqual(historical.observe("test", actor)[1]["cognition_state"], old)
        with self.assertRaises(Conflict):
            world.commit("test", **{**kwargs, "request_id": "stale"})

    async def test_legacy_snapshot_stays_raw_and_new_binding_cannot_replace_it(self):
        world = World(":memory:")
        self.addCleanup(world.close)
        frozen = manifest()
        ordinal = next(a["ordinal"] for a in frozen["assignments"] if a["arm"] == "B")
        args = dict(world=world, world_id="old", spec=spec(), manifest=frozen, ordinal=ordinal,
                    policy=lambda view, feedback: Decision("wait"), max_steps=4, cognition=lambda view: {"x": 1})
        runtime = Runtime(**args)
        await runtime.step()
        before = world.events("old")
        self.assertEqual(before[0]["payload"]["audit"]["cognition_state"], {"x": 1})
        design = copy.deepcopy(frozen["design"])
        design["cognition_storage"] = copy.deepcopy(PROTOCOL)
        with self.assertRaises(ValueError):
            Runtime(**{**args, "manifest": freeze_design(design)})
        self.assertEqual(world.events("old"), before)
        design["cognition_storage"]["checkpoint_interval"] = 8
        with self.assertRaises(ValueError):
            freeze_design(design)

    async def test_runtime_reconstructed_state_equals_actual_full_cognition_result(self):
        world = World(":memory:")
        self.addCleanup(world.close)
        _, _, args = storage_options(world)
        original = args["cognition"]
        captured = []
        class Capture:
            def __getattr__(self, key):
                return getattr(original, key)
            async def __call__(self, view):
                state = await original(view)
                captured.append((view["actor"], copy.deepcopy(state)))
                return state
        args["cognition"] = Capture()
        runtime = Runtime(**args)
        for _ in range(4):
            await runtime.step()
            actor, state = captured[-1]
            self.assertEqual(canonical(world.observe("D", actor)[1]["cognition_state"]), canonical(state))
        await runtime._store("freeze", "D")
        source = world.export_source("D")
        from app.g5.artifacts import verify_source
        verify_source(source, args["manifest"])
        # Rehash the entire outer envelope/chain: logical corruption must still fail.
        bad = copy.deepcopy(source)
        previous = digest([bad["world_id"], bad["spec"], bad["binding"]])
        bad["events"][0]["payload"]["audit"]["cognition_state"]["state_sha256"] = "0" * 64
        for event in bad["events"]:
            p = event["payload"]
            event["request_hash"] = digest([p["actor"], p["decision"], p["audit"]])
            event["event_id"] = digest([bad["world_id"], event["seq"], event["request_id"], event["request_hash"], previous, p])
            previous = event["event_id"]
        bad["sha256"] = digest({k: v for k, v in bad.items() if k != "sha256"})
        with self.assertRaisesRegex(ValueError, "Cognition reconstruction"):
            verify_source(bad)


if __name__ == "__main__":
    import argparse
    import asyncio
    from pathlib import Path
    import os
    from app.g5.cognition_storage_profile import profile
    from test_g5_capacity import long_probe
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    directory = Path(args.output_dir)
    directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    def write_evidence(path, value):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(canonical(value))
            stream.flush()
            os.fsync(stream.fileno())
    async def run():
        world = World(str(directory / "synthetic-world.sqlite"))
        try:
            reports = {}
            for arm in ARMS:
                source = await long_probe(world, arm, delta_storage=True)
                write_evidence(directory / (arm + "-source.json"), source)
                reports[arm] = profile(source)
                write_evidence(directory / (arm + "-profile.json"), reports[arm])
            raw = {"schema": "g5-synthetic-delta-storage-probe-v1", "arms": reports,
                   "real_model_calls": 0, "qualification": "not_inferred"}
            write_evidence(directory / "summary.json", {**raw, "sha256": digest(raw)})
            print({arm: {k: report[k] for k in ("stored_cognition_bytes", "logical_full_cognition_bytes",
                "saved_fraction", "source_bytes")} for arm, report in reports.items()})
        finally:
            world.close()
    asyncio.run(run())
