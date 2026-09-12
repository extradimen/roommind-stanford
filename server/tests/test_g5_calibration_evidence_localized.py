"""Program-localized evidence protocol tests; no external calls."""
import copy
import json
import unittest

from app.factorial_study import digest
from app.g5.calibration_evidence_localized import LocalizedEvidencePredictor, localize_output
from app.g5.model_policy import Completion, ModelBinding


class LocalizedEvidenceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.task={"case_id":"x","dimension":"procedural_fidelity","rubric":"Respect authority.",
            "context":{},"messages":[
                {"message_id":"m1","speaker_id":"alice","turn_id":1,"sequence_no":1,"content":"Wait. I can propose containment."},
                {"message_id":"m2","speaker_id":"bob","turn_id":1,"sequence_no":2,"content":"Wait. I confirm recovery."}]}
        self.output={"prediction":"clear","rationale":"Roles use distinct actions.","citations":[
            {"message_id":"m2","quote":"I confirm recovery","relevance":"Bob confirms recovery."}]}

    async def test_code_derives_exact_speaker_and_unicode_offsets(self):
        result=localize_output(self.task,self.output); evidence=result["evidence"][0]
        self.assertEqual(evidence["speaker_id"],"bob")
        self.assertEqual(self.task["messages"][1]["content"][evidence["start"]:evidence["end"]],evidence["quote"])
        self.assertNotIn("speaker_id",result["model_citations"][0])

    async def test_unknown_nonexact_nonunique_and_duplicate_rejected(self):
        for change in ("unknown","nonexact","nonunique","duplicate"):
            value=copy.deepcopy(self.output)
            if change=="unknown": value["citations"][0]["message_id"]="m0"
            if change=="nonexact": value["citations"][0]["quote"]="confirm containment"
            if change=="nonunique": value["citations"][0]={"message_id":"m2","quote":".","relevance":"x"}
            if change=="duplicate": value["citations"].append(copy.deepcopy(value["citations"][0]))
            with self.subTest(change=change),self.assertRaises(ValueError): localize_output(self.task,value)

    async def test_decisive_requires_citation_and_abstain_may_be_empty(self):
        with self.assertRaises(ValueError): localize_output(self.task,{"prediction":"clear","rationale":"x","citations":[]})
        value=localize_output(self.task,{"prediction":"abstain","rationale":"Insufficient.","citations":[]})
        self.assertEqual(value["evidence"],[])

    async def test_model_receipt_and_frozen_plan(self):
        binding=ModelBinding("offline","fixed","mock",0,8192)
        async def transport(request): return Completion(json.dumps(self.output),"offline","fixed","mock",digest(request),"stop")
        predictor=LocalizedEvidencePredictor(binding,transport,predictor_id="fixture",kind="synthetic")
        result=await predictor.predict(self.task,predictor.plan())
        self.assertEqual(result["output"]["evidence"][0]["speaker_id"],"bob")
        plan=predictor.plan(); predictor.predictor_id="changed"
        with self.assertRaises(ValueError): await predictor.predict(self.task,plan)


if __name__=="__main__": unittest.main()
