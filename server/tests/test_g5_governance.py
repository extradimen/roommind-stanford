import copy
import tempfile
import unittest

from app.g5.governance import CandidateGovernance
from app.g5.model_auditor import Findings
from app.g5.runtime import Runtime
from app.g5.world import World, Decision
from test_g5_runtime import spec, manifest


def finding(**changes):
    return {"code": "unsupported_fact", "severity": "hard", "certainty": "supported",
            "start": 0, "end": 3, "source_ids": ["fact:contained"],
            "reason": "Containment is not established; express uncertainty or request an action.", **changes}


def view():
    return {"actor": "security", "facts": {"contained": {"value": False, "disclosable": True}},
            "observations": [], "operations": [], "world_audit": "never-send"}


class GovernanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_exhausted_structured_repairs_conservatively_reject_candidate(self):
        calls = []
        async def auditor(context, candidate, feedback=None):
            calls.append(copy.deepcopy(feedback))
            result = Findings([finding(source_ids=[])])
            result.raw_response_content = '{"findings":[]}'
            result.model_evidence = {
                "request_sha256": "a" * 64, "response_sha256": "b" * 64}
            return result
        adapter = CandidateGovernance(auditor, auditor_id="exhaustion-test",
                                      max_structured_revisions=2)
        result = await adapter(view(), Decision("speak", "All contained"))
        self.assertFalse(result.allowed)
        self.assertIn("audit unavailable", result.reason)
        self.assertEqual(len(calls), 3)
        evidence = __import__("json").loads(result.model_evidence_json)
        self.assertTrue(evidence["repair_exhausted"])
        self.assertEqual(len(evidence["rejected"]), 3)
        self.assertEqual(adapter.runtime_specification()["audit_repair_exhaustion"], {
            "schema": "g5-conservative-governance-repair-exhaustion-v1",
            "action": "reject-candidate-and-let-runtime-revise-or-wait"})

    def adapter(self, findings):
        async def audit(context, candidate):
            self.assertNotIn("world_audit", context)
            return copy.deepcopy(findings)
        return CandidateGovernance(audit, auditor_id="script-v1")

    async def test_supported_hard_rejects_without_rewriting(self):
        decision = Decision("speak", "All contained")
        result = await self.adapter([finding()])(view(), decision)
        self.assertFalse(result.allowed)
        self.assertIn("uncertainty", result.reason)
        self.assertEqual(decision.content, "All contained")
        self.assertTrue(result.candidate_sha256)

    async def test_uncertain_and_advisory_do_not_block(self):
        for issue in (finding(certainty="uncertain"), finding(severity="advisory", code="brevity")):
            result = await self.adapter([issue])(view(), Decision("speak", "I disagree"))
            self.assertTrue(result.allowed)
            self.assertEqual(result.reason, "")
            self.assertNotEqual(result.findings_json, "[]")

    async def test_wait_and_execute_use_common_environment(self):
        async def unexpected(*args):
            self.fail("Speech auditor should not run")
        adapter = CandidateGovernance(unexpected, auditor_id="script")
        for decision in (Decision("wait"), Decision("execute", operation="contain")):
            self.assertTrue((await adapter(view(), decision)).allowed)

    async def test_positive_speech_passes_unchanged(self):
        for content in ("I decline.", "I do not know.", "Only if evidence supports it.", "We remain in disagreement."):
            decision = Decision("speak", content)
            self.assertTrue((await self.adapter([])(view(), decision)).allowed)
            self.assertEqual(decision.content, content)

    async def test_invalid_findings_are_errors_not_rejections(self):
        for issue in (finding(code="must_agree"), finding(source_ids=[]),
                      finding(source_ids=["hidden"]), finding(start=True), finding(end=999)):
            with self.assertRaises(ValueError):
                await self.adapter([issue])(view(), Decision("speak", "All contained"))

    async def test_runtime_revision_and_private_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            world = World(directory + "/test.sqlite")
            try:
                frozen = manifest()
                ordinal = next(a["ordinal"] for a in frozen["assignments"] if a["arm"] == "C")
                calls = []
                async def policy(context, feedback):
                    calls.append((context["actor"], feedback))
                    return Decision("speak", "All contained" if not feedback else "I need evidence.")
                async def auditor(context, candidate):
                    return [finding()] if candidate["content"] == "All contained" else []
                runtime = Runtime(world=world, world_id="test", spec=spec(), manifest=frozen,
                                  ordinal=ordinal, policy=policy, max_steps=4,
                                  governance=CandidateGovernance(auditor, auditor_id="script"))
                await runtime.step()
                self.assertEqual([c[0] for c in calls], ["security", "security"])
                self.assertTrue(calls[1][1])
                _, observed = world.observe("test", "sre")
                self.assertEqual(observed["observations"][0]["content"], "I need evidence.")
                self.assertNotIn("All contained", str(observed))
                self.assertIn("All contained", str(world.events("test")))
            finally:
                world.close()
