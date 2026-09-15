"""Authorized legacy calibration, exclusive immutable attempts; credentials memory-only."""
import argparse
import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

import httpx
from app.factorial_study import digest
from app.g5.calibration_predictor import ModelPredictor, request_for
from app.g5.model_policy import ModelBinding
from app.g5.ollama_transport import OllamaTransport

INPUT = Path('research/experiments/2026-09-12-g5-development-calibration-inputs/inputs.json')
OUTPUT = Path('research/experiments/2026-09-12-g5-development-calibration-predictions')
EXPECTED = '34d65df68c09ab21ecab04c6a088817505a3bebcdc3532def9101a7ff5e4d92d'


def save(path, value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())


def read(path):
    return json.loads(path.read_text())


def credential():
    # Only the explicitly authorized provider credential is returned over SSH.
    # Never forward stderr, arguments containing secrets, or the returned value.
    code = "from dotenv import dotenv_values; import json; from pathlib import Path; d=dotenv_values('/home/ubuntu/roommind-stanford-staging/.env'); k=d.get('OLLAMA_API_KEY') or d.get('OLLAMA_CLOUD_API_KEY'); p=Path('/home/ubuntu/roommind-stanford-staging/config/platform.json'); k=k or (json.loads(p.read_text()).get('ollama',{}).get('apiKey') if p.exists() else None); print(k or '',end='')"
    command = 'cd /home/ubuntu/roommind-stanford-staging && .venv/bin/python -c ' + shlex.quote(code)
    r = subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-i',
        '/Users/michaelwang/.ssh/roommind_tencent','ubuntu@43.162.83.232',command],capture_output=True,timeout=30)
    if r.returncode:
        raise RuntimeError('Credential SSH read failed; no secret output displayed')
    key = r.stdout.decode().strip()
    if not key or any(c.isspace() for c in key):
        raise RuntimeError('No usable authorized credential at expected source')
    return key


async def attempt(case, plan, directory, number, key, http_transport=None):
    binding = ModelBinding(**plan['model_spec']['binding'])
    prefix = directory / (case['task']['case_id'] + f'.{number}')
    started, raw_path, result_path = [Path(str(prefix)+s) for s in ('.started.json','.http.json','.result.json')]
    expected_start = {'input_sha256':EXPECTED,'request_sha256':digest(case['request']),
        'case_id':case['task']['case_id'],'attempt':number}
    if started.exists():
        if read(started)!=expected_start: raise ValueError('Attempt input drift')
    else:
        save(started,expected_start)
    if result_path.exists():
        return read(result_path)
    if raw_path.exists():
        raw=read(raw_path)
        if raw['request_sha256']!=expected_start['request_sha256']: raise ValueError('HTTP input drift')
    else:
        # Caller must not enter an old start without a response (indeterminate).
        payload={'model':binding.model,'messages':case['request']['messages'],'stream':False,
            'format':'json','options':{'temperature':binding.temperature,'num_predict':binding.max_tokens}}
        try:
            async with httpx.AsyncClient(trust_env=False,follow_redirects=False,timeout=180,transport=http_transport) as client:
                response=await client.post('https://ollama.com/api/chat',json=payload,headers={'Authorization':'Bearer '+key})
            body=response.content.decode('utf-8')
            if key in body: raise RuntimeError('Secret echoed; response withheld')
            raw={'status':response.status_code,'body':body,'request_sha256':digest(case['request']),
                 'body_sha256':hashlib.sha256(response.content).hexdigest(),'transport_error':None}
        except (httpx.TimeoutException,httpx.HTTPError) as e:
            raw={'status':None,'body':None,'request_sha256':digest(case['request']),
                 'body_sha256':None,'transport_error':'timeout' if isinstance(e,httpx.TimeoutException) else 'connection'}
        save(raw_path,raw)
    if raw['status'] in (401,403): raise RuntimeError('Authentication rejected; batch stopped')
    if raw['status']==200:
        try: remote_model=json.loads(raw['body']).get('model')
        except (ValueError,AttributeError): remote_model=None
        if remote_model is not None and remote_model!=binding.model:
            raise RuntimeError('Response model identity mismatch; batch stopped')
    async def replay(request):
        if raw['transport_error']=='timeout': raise httpx.ReadTimeout('Recorded timeout')
        if raw['transport_error']: raise httpx.ConnectError('Recorded connection failure')
        return httpx.Response(raw['status'],content=raw['body'].encode(),request=request)
    transport=OllamaTransport(binding,'https://ollama.com',timeout=180,http_transport=httpx.MockTransport(replay))
    predictor=ModelPredictor(binding,transport,predictor_id=plan['predictor']['id'],kind='ai')
    if predictor.plan()!=plan: raise ValueError('Frozen predictor mismatch')
    result=await predictor.predict(case['task'],plan,attempt_id=prefix.name)
    save(result_path,result)
    return result


async def run():
    bundle=read(INPUT)
    if bundle['sha256']!=EXPECTED or digest({k:v for k,v in bundle.items() if k!='sha256'})!=EXPECTED:
        raise ValueError('Frozen inputs changed')
    if hashlib.sha256(Path(bundle['source_path']).read_bytes()).hexdigest()!=bundle['source_file_sha256']:
        raise ValueError('Original source changed')
    for case in bundle['cases']:
        if request_for(case['task'],bundle['prediction_plan']['model_spec'])!=case['request']:
            raise ValueError('Request mismatch')
    OUTPUT.mkdir(exist_ok=True,mode=0o700)
    lock=os.open(OUTPUT/'worker.lock',os.O_CREAT|os.O_RDWR,0o600)
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    try:
        # Explicitly stop on unresolved remote calls; don't silently repeat inference.
        for p in OUTPUT.glob('*.started.json'):
            if not Path(str(p).replace('.started.json','.http.json')).exists():
                raise RuntimeError('Indeterminate prior attempt requires quiescent recovery review')
        key=None
        for case in bundle['cases']:
            for n in (1,2):
                result_path=OUTPUT/(case['task']['case_id']+f'.{n}.result.json')
                if result_path.exists(): result=read(result_path)
                else:
                    if key is None: key=credential()
                    result=await attempt(case,bundle['prediction_plan'],OUTPUT,n,key)
                outcome=result['artifact']['output']
                print(json.dumps({'case':case['task']['case_id'],'attempt':n,**outcome}),flush=True)
                if outcome['status']=='completed': break
        print('FROZEN_DEVELOPMENT_PREDICTIONS_FINISHED',flush=True)
    finally:
        os.close(lock)


if __name__=='__main__':
    try: asyncio.run(run())
    except Exception as e:
        # No exception payload from network/SSH libraries is printed.
        print('Stopped safely: '+type(e).__name__,flush=True)
        raise SystemExit(1)
