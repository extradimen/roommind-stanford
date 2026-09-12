"""Verify saved development responses; no calls or reference-label inference."""
import hashlib
import json
from collections import Counter
from pathlib import Path
from app.factorial_study import digest
from app.g5.calibration_predictor import validate_receipt
from g5_run_development_calibration import INPUT, OUTPUT, EXPECTED, read, save


def main():
    bundle=read(INPUT)
    assert bundle['sha256']==EXPECTED==digest({k:v for k,v in bundle.items() if k!='sha256'})
    rows=[]; files={}; attempts=0
    for case in bundle['cases']:
        latest=None
        for n in (1,2):
            prefix=OUTPUT/(case['task']['case_id']+f'.{n}')
            start=Path(str(prefix)+'.started.json'); rawpath=Path(str(prefix)+'.http.json'); resultpath=Path(str(prefix)+'.result.json')
            if not start.exists():
                assert not rawpath.exists() and not resultpath.exists()
                continue
            attempts+=1
            assert read(start)=={'input_sha256':EXPECTED,'request_sha256':digest(case['request']),'case_id':case['task']['case_id'],'attempt':n}
            assert rawpath.exists() and resultpath.exists(), 'Incomplete attempt'
            raw,result=read(rawpath),read(resultpath)
            assert raw['request_sha256']==digest(case['request'])
            assert result['artifact']['task']==case['task']
            assert result['artifact']['predictor']==bundle['prediction_plan']['predictor']
            assert latest is None or latest['artifact']['output']['status']=='technical_failure'
            validate_receipt(result,bundle['prediction_plan'])
            if raw['body'] is not None:
                assert hashlib.sha256(raw['body'].encode()).hexdigest()==raw['body_sha256']
            if result['artifact']['output']['status']=='completed':
                response=json.loads(raw['body'])
                assert raw['status']==200 and response['model']=='gpt-oss:120b'
                assert response['message']['content']==result['artifact']['raw_record']['response']['content']
            latest=result
            for p in (start,rawpath,resultpath): files[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        rows.append({'case_id':case['task']['case_id'],'family':case['source_family'],
            'source_run_id':case['source_run_id'],'dimension':case['task']['dimension'],
            'output':latest['artifact']['output'] if latest else {'status':'missing'}})
    report={'schema':'g5-legacy-development-prediction-audit-v1','input_sha256':EXPECTED,
        'attempts':attempts,'cases':rows,'file_sha256':files,
        'status_counts':dict(Counter(r['output']['status'] for r in rows)),
        'prediction_counts':dict(Counter(r['output'].get('prediction') for r in rows if r['output']['status']=='completed')),
        'accuracy_estimable':False,'human_labels':0,'g5_effect_estimable':False,
        'interpretation':'Unlabelled legacy development prediction outputs, not validated errors or G5 qualification.'}
    report['sha256']=digest(report)
    save(OUTPUT/'audit.json',report)
    print(json.dumps({k:report[k] for k in ('attempts','status_counts','prediction_counts','sha256')}))


if __name__=='__main__': main()
