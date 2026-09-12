"""Audit frozen v2 attempts and offset-free recoverability; no model calls."""
import hashlib
import json
from collections import Counter
from pathlib import Path

from app.factorial_study import digest
from app.g5.calibration_evidence import validate_output
from g5_run_development_calibration import read, save

INPUT=Path('research/experiments/2026-09-12-g5-evidence-calibration-inputs/inputs.json')
OUTPUT=Path('research/experiments/2026-09-12-g5-evidence-calibration-predictions')


def diagnose(task,raw):
    if raw['transport_error']: return raw['transport_error'],None
    if raw['status']!=200: return 'http_status',None
    try: envelope=json.loads(raw['body'])
    except ValueError: return 'invalid_http_json',None
    if envelope.get('model')!='gpt-oss:120b': return 'model_mismatch',None
    if envelope.get('done') is not True or envelope.get('done_reason')!='stop': return 'incomplete_response',None
    try: parsed=json.loads(envelope.get('message',{}).get('content',''))
    except (ValueError,TypeError): return 'invalid_content_json',None
    if not isinstance(parsed,dict) or set(parsed)!={'prediction','rationale','evidence'}: return 'output_shape',parsed
    if parsed['prediction'] not in {'clear','violation','abstain'} or not isinstance(parsed['rationale'],str) or not parsed['rationale'].strip():
        return 'invalid_decision',parsed
    if not isinstance(parsed['evidence'],list) or len(parsed['evidence'])>5 or (parsed['prediction']!='abstain' and not parsed['evidence']):
        return 'evidence_count',parsed
    messages={m['message_id']:m for m in task['messages']}
    seen=set()
    for evidence in parsed['evidence']:
        if not isinstance(evidence,dict) or set(evidence)!={'message_id','speaker_id','start','end','quote','relevance'}:
            return 'citation_shape',parsed
        message=messages.get(evidence['message_id'])
        if message is None: return 'unknown_message',parsed
        if evidence['speaker_id']!=message['speaker_id']: return 'speaker_mismatch',parsed
        if not isinstance(evidence['quote'],str) or not evidence['quote'] or not isinstance(evidence['relevance'],str) or not evidence['relevance'].strip():
            return 'citation_text',parsed
        start,end=evidence['start'],evidence['end']
        if type(start) is not int or type(end) is not int or not 0<=start<end<=len(message['content']):
            return 'offset_range',parsed
        if message['content'][start:end]!=evidence['quote']: return 'offset_quote_mismatch',parsed
        key=(evidence['message_id'],start,end)
        if key in seen: return 'duplicate_citation',parsed
        seen.add(key)
    validate_output(task,parsed)
    return 'valid',parsed


def derive_unique(task,parsed):
    if not isinstance(parsed,dict) or set(parsed)!={'prediction','rationale','evidence'}: return None
    if parsed['prediction'] not in {'clear','violation','abstain'} or not isinstance(parsed['rationale'],str) or not parsed['rationale'].strip() or not isinstance(parsed['evidence'],list) or len(parsed['evidence'])>5:
        return None
    if parsed['prediction']!='abstain' and not parsed['evidence']: return None
    messages={m['message_id']:m for m in task['messages']}; evidence=[]; seen=set()
    for item in parsed['evidence']:
        if not isinstance(item,dict) or set(item)!={'message_id','speaker_id','start','end','quote','relevance'}: return None
        message=messages.get(item['message_id'])
        if message is None or item['speaker_id']!=message['speaker_id'] or not isinstance(item['quote'],str) or not item['quote'] or not isinstance(item['relevance'],str) or not item['relevance'].strip(): return None
        positions=[]; start=0
        while True:
            found=message['content'].find(item['quote'],start)
            if found<0: break
            positions.append(found); start=found+1
        if len(positions)!=1: return None
        key=(item['message_id'],positions[0],positions[0]+len(item['quote']))
        if key in seen: return None
        seen.add(key)
        evidence.append({**item,'start':key[1],'end':key[2]})
    derived={'prediction':parsed['prediction'],'rationale':parsed['rationale'],'evidence':evidence}
    validate_output(task,derived)
    return derived


def main():
    bundle=read(INPUT); assert bundle['sha256']==digest({k:v for k,v in bundle.items() if k!='sha256'})
    attempts=[]; final=[]; files={}; reason_counts=Counter(); recoverable=0
    for case in bundle['cases']:
        latest=None
        for n in (1,2):
            prefix=OUTPUT/(case['task']['case_id']+f'.{n}')
            paths=[Path(str(prefix)+suffix) for suffix in ('.started.json','.http.json','.result.json')]
            if not paths[0].exists():
                assert not paths[1].exists() and not paths[2].exists(); continue
            assert all(p.exists() for p in paths)
            marker,raw,result=map(read,paths)
            assert marker['input_sha256']==bundle['sha256'] and marker['request_sha256']==digest(case['request'])
            assert raw['request_sha256']==digest(case['request'])
            if raw['body'] is not None: assert hashlib.sha256(raw['body'].encode()).hexdigest()==raw['body_sha256']
            reason,parsed=diagnose(case['task'],raw)
            assert (reason=='valid')==(result['status']=='completed')
            derived=derive_unique(case['task'],parsed) if reason!='valid' else None
            recoverable += derived is not None
            reason_counts[reason]+=1
            attempts.append({'case_id':case['task']['case_id'],'attempt':n,'status':result['status'],
                'reason':reason,'uniquely_localizable_without_model_offsets':derived is not None,
                'derived_evidence_sha256':digest(derived['evidence']) if derived else None})
            latest=result
            for p in paths: files[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        assert latest is not None
        final.append({'case_id':case['task']['case_id'],'status':latest['status'],
            'prediction':latest['protocol']['output']['prediction'] if latest['protocol'] else None})
    report={'schema':'g5-evidence-calibration-audit-v1','input_sha256':bundle['sha256'],
        'attempts':attempts,'final_cases':final,'file_sha256':files,
        'attempt_count':len(attempts),'attempt_reason_counts':dict(sorted(reason_counts.items())),
        'failed_attempts_uniquely_localizable_without_model_offsets':recoverable,
        'final_status_counts':dict(Counter(r['status'] for r in final)),
        'final_prediction_counts':dict(Counter(r['prediction'] for r in final if r['status']=='completed')),
        'human_reference_labels':0,'accuracy_estimable':False,'g5_effect_estimable':False,
        'derived_outputs_are_counterfactual_parser_diagnostics_not_frozen_results':True}
    report['sha256']=digest(report); save(OUTPUT/'audit.json',report)
    print(json.dumps({k:report[k] for k in ('attempt_count','attempt_reason_counts','failed_attempts_uniquely_localizable_without_model_offsets','final_status_counts','final_prediction_counts','sha256')}))


if __name__=='__main__': main()
