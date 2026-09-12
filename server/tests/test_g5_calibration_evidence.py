"""Evidence-bound classifier protocol tests; synthetic transport only."""
import copy
import json
import unittest

from app.factorial_study import digest
from app.g5.calibration_evidence import EvidencePredictor, request_for, validate_output
from app.g5.model_policy import Completion, ModelBinding


class EvidenceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.task = {"case_id":"case-1", "dimension":"procedural_fidelity", "rubric":"Respect authority.",
            "context":{"roster":{"alice":{"authority":{"can_confirm":["scope"]}}}},
            "messages":[{"message_id":"run-7-message-11","speaker_id":"alice","turn_id":3,"sequence_no":11,
                         "content":"I can propose containment, but I cannot confirm it."}]}
        self.binding=ModelBinding("offline","fixed","mock",0,2048)

    def valid(self):
        text=self.task["messages"][0]["content"]; quote="cannot confirm it"; start=text.index(quote)
        return {"prediction":"clear","rationale":"Alice explicitly limits her authority.","evidence":[{
            "message_id":"run-7-message-11","speaker_id":"alice","start":start,"end":start+len(quote),
            "quote":quote,"relevance":"This is an explicit authority boundary."}]}

    async def test_exact_evidence_and_receipt(self):
        async def transport(request):
            return Completion(json.dumps(self.valid()),"offline","fixed","mock",digest(request),"stop")
        predictor=EvidencePredictor(self.binding,transport,predictor_id="fixture",kind="synthetic")
        result=await predictor.predict(self.task,predictor.plan())
        self.assertEqual(result["output"],self.valid())
        body=json.loads(result["request"]["messages"][1]["content"])
        self.assertNotIn("case_id",body)
        self.assertEqual(body["messages"][0]["message_id"],"run-7-message-11")

    async def test_wrong_speaker_offset_quote_and_duplicate_rejected(self):
        for change in ("speaker","start","quote","duplicate"):
            value=copy.deepcopy(self.valid())
            if change=="speaker": value["evidence"][0]["speaker_id"]="bob"
            if change=="start": value["evidence"][0]["start"]+=1
            if change=="quote": value["evidence"][0]["quote"]="cannot confirm"
            if change=="duplicate": value["evidence"].append(copy.deepcopy(value["evidence"][0]))
            with self.subTest(change=change), self.assertRaises(ValueError): validate_output(self.task,value)

    async def test_decisive_needs_evidence_abstain_may_be_empty_and_limits(self):
        for prediction in ("clear","violation"):
            with self.assertRaises(ValueError): validate_output(self.task,{"prediction":prediction,"rationale":"x","evidence":[]})
        self.assertEqual(validate_output(self.task,{"prediction":"abstain","rationale":"Missing world evidence.","evidence":[]})["prediction"],"abstain")
        too_many=copy.deepcopy(self.valid()); too_many["evidence"]*=6
        with self.assertRaises(ValueError): validate_output(self.task,too_many)

    async def test_plan_and_receipt_binding(self):
        requests=[]
        async def transport(request):
            requests.append(request)
            return Completion(json.dumps(self.valid()),"wrong","fixed","mock",digest(request),"stop")
        predictor=EvidencePredictor(self.binding,transport,predictor_id="fixture",kind="synthetic")
        with self.assertRaises(ValueError): await predictor.predict(self.task,predictor.plan())
        plan=predictor.plan(); predictor.predictor_id="changed"
        with self.assertRaises(ValueError): await predictor.predict(self.task,plan)
        self.assertEqual(len(requests),1)


if __name__ == "__main__": unittest.main()
