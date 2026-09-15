"""Freeze v3 program-localized requests from unchanged v2 case coverage."""
import json
import os
from pathlib import Path

from app.factorial_study import digest
from app.g5.calibration_evidence_localized import LocalizedEvidencePredictor, request_for
from app.g5.model_policy import ModelBinding
from app.g5.ollama_transport import OllamaTransport

PRIOR=Path('research/experiments/2026-09-12-g5-evidence-calibration-inputs/inputs.json')
TARGET=Path('research/experiments/2026-09-12-g5-localized-evidence-calibration-inputs')
PRIOR_SHA='94fe7e104b6d489bfea56dc8f7d1ddc58bd4ec5dddd0145534cc980476dbd20f'


def main():
    prior=json.loads(PRIOR.read_text())
    if prior['sha256']!=PRIOR_SHA or digest({k:v for k,v in prior.items() if k!='sha256'})!=PRIOR_SHA:
        raise ValueError('V2 input changed')
    binding=ModelBinding('ollama','gpt-oss:120b','ollama-cloud-localized-evidence-calibration',0,8192)
    predictor=LocalizedEvidencePredictor(binding,OllamaTransport(binding,'https://ollama.com',timeout=240),
        predictor_id='g5-localized-evidence-classifier-20260912',kind='ai')
    plan=predictor.plan(); cases=[]
    for case in prior['cases']:
        item={k:v for k,v in case.items() if k!='request'}
        item['request']=request_for(item['task'],plan['model_spec']); cases.append(item)
    if len(cases)!=48 or [c['task']['case_id'] for c in cases]!=[c['task']['case_id'] for c in prior['cases']]:
        raise ValueError('Case coverage changed')
    bundle={'schema':'g5-legacy-localized-evidence-calibration-inputs-v3','prior_input_sha256':PRIOR_SHA,
        'source_path':prior['source_path'],'source_file_sha256':prior['source_file_sha256'],
        'prediction_plan':plan,'cases':cases,
        'selection':'Exact v2 cases and source messages; only response protocol and output allowance changed.',
        'change_rationale':'Model selects exact unique quote and message ID; trusted code derives speaker and Unicode offsets. 8192 output tokens addresses observed v2 length exhaustion.',
        'execution_policy':{'concurrency':1,'maximum_attempts_per_case':2,'retry':'technical failures only',
            'maximum_requests':96,'completed_results':'immutable; resume missing only','indeterminate_remote_call':'stop for quiescent review'},
        'external_execution_authorized':False,'reference_labels_available':False,'human_annotations':0,
        'real_model_calls':0,'accuracy_estimable':False,'g5_architecture_effect_estimable':False,
        'confirmation_eligible':False}
    bundle['sha256']=digest(bundle)
    TARGET.mkdir(exist_ok=True,mode=0o700)
    if {p.name for p in TARGET.iterdir()} - {'README.md'}:
        raise ValueError('Target already contains generated material')
    fd=os.open(TARGET/'inputs.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:
        json.dump(bundle,f,ensure_ascii=False,sort_keys=True); f.flush(); os.fsync(f.fileno())
    print(json.dumps({'cases':48,'sha256':bundle['sha256'],
        'largest_request_bytes':max(len(json.dumps(c['request'],ensure_ascii=False).encode()) for c in cases),
        'external_execution_authorized':False}))


if __name__=='__main__': main()
