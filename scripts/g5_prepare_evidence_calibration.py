"""Freeze v2 evidence-bound requests from the same unfiltered development batch."""
import hashlib
import json
import os
from pathlib import Path

from app.factorial_study import digest
from app.g5.calibration_evidence import EvidencePredictor, request_for
from app.g5.model_policy import ModelBinding
from app.g5.ollama_transport import OllamaTransport
from app.research_protocol import transcript_provenance
from g5_prepare_development_calibration import RUBRICS, SOURCE

PRIOR = Path('research/experiments/2026-09-12-g5-development-calibration-inputs/inputs.json')
TARGET = Path('research/experiments/2026-09-12-g5-evidence-calibration-inputs')
PRIOR_SHA = '34d65df68c09ab21ecab04c6a088817505a3bebcdc3532def9101a7ff5e4d92d'


def main():
    prior=json.loads(PRIOR.read_text())
    if prior['sha256']!=PRIOR_SHA or digest({k:v for k,v in prior.items() if k!='sha256'})!=PRIOR_SHA:
        raise ValueError('Prior frozen input changed')
    raw=SOURCE.read_bytes(); source_sha=hashlib.sha256(raw).hexdigest()
    if source_sha!=prior['source_file_sha256']: raise ValueError('Source changed')
    data=json.loads(raw)
    binding=ModelBinding('ollama','gpt-oss:120b','ollama-cloud-evidence-calibration',0,4096)
    predictor=EvidencePredictor(binding,OllamaTransport(binding,'https://ollama.com',timeout=180),
        predictor_id='g5-evidence-classifier-20260912',kind='ai')
    plan=predictor.plan(); cases=[]
    for run in sorted(data['runs'],key=lambda r:r['run_id']):
        session=run['session']; transcript_sha=transcript_provenance(session)['transcript_sha256']
        if transcript_sha!=run['run_result']['transcript_sha256']: raise ValueError('Transcript mismatch')
        roster={k:{field:v[field] for field in ('character_name','job_title','authority') if field in v}
                for k,v in session['speaker_directory'].items()}
        messages=[{'message_id':f"run-{run['run_id']}-message-{m['id']}",
            **{k:m[k] for k in ('speaker_id','turn_id','sequence_no','content')}} for m in session['messages']]
        if len({m['message_id'] for m in messages})!=len(messages): raise ValueError('Duplicate message ID')
        for dimension,rubric in RUBRICS.items():
            task={'case_id':f"legacy-{run['run_id']}-{dimension}",'dimension':dimension,'rubric':rubric,
                'context':{'roster':roster,'evidence_scope':'Full public dialogue and declared authority only. Private role cards and authoritative world/receipt ledger are absent. Cite exact public text; abstain when absent evidence is decisive.'},
                'messages':messages}
            cases.append({'task':task,'request':request_for(task,plan['model_spec']),
                'source_run_id':run['run_id'],'source_condition':run['condition'],
                'source_family':session['scenario']['slug'],'source_transcript_sha256':transcript_sha,
                'reference_label':None,'reference_kind':'unannotated'})
    prior_cases={(c['source_run_id'],c['task']['dimension']) for c in prior['cases']}
    if len(cases)!=48 or {(c['source_run_id'],c['task']['dimension']) for c in cases}!=prior_cases:
        raise ValueError('V1/v2 coverage differs')
    bundle={'schema':'g5-legacy-evidence-calibration-inputs-v2','prior_input_sha256':PRIOR_SHA,
        'source_path':str(SOURCE),'source_file_sha256':source_sha,'prediction_plan':plan,'cases':cases,
        'selection':'Exact same eight unfiltered G4.4 public dialogues and six dimensions as v1; new protocol only.',
        'execution_policy':{'concurrency':1,'maximum_attempts_per_case':2,
            'retry':'technical failures only','maximum_requests':96,
            'completed_results':'immutable; resume missing only','indeterminate_remote_call':'stop for quiescent review'},
        'authorization':'User authorized starting evidence-bound development calibration on 2026-09-12; no deployment, push, human review or confirmation study.',
        'reference_labels_available':False,'human_annotations':0,'real_model_calls':0,
        'accuracy_estimable':False,'g5_architecture_effect_estimable':False,'confirmation_eligible':False}
    bundle['sha256']=digest(bundle)
    TARGET.mkdir(exist_ok=False,mode=0o700)
    fd=os.open(TARGET/'inputs.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:
        json.dump(bundle,f,ensure_ascii=False,sort_keys=True); f.flush(); os.fsync(f.fileno())
    print(json.dumps({'cases':len(cases),'dialogues':len({c['source_run_id'] for c in cases}),
        'sha256':bundle['sha256'],'largest_request_bytes':max(len(json.dumps(c['request'],ensure_ascii=False).encode()) for c in cases)}))


if __name__=='__main__': main()
