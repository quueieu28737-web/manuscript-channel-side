"""Array-level replay for the explicitly post-scoring detector ablation."""
from pathlib import Path
import json,gzip,hashlib,math
import numpy as np
import joblib
import verify_b1 as v

H=Path(__file__).resolve().parent
load=v.load


def main():
    d=H/'diagnostic';finished=load(d/'finished.json');plan=load(d/'plan-freeze.json')
    assert v.sha(H/'detector_ablation.py')==plan['code_sha256']
    for name,digest in finished['files'].items():assert v.sha(d/name)==digest
    records={}
    with gzip.open(v.S/'data/episodes.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            r=json.loads(line)
            if r['split']=='test':records[r['model'],r['arm'],r['task_id']]=r
    chosen=load(d/'validation-selection.json');preds=load(d/'predictions.json');rows=load(d/'results.json')
    original=load(H/'validation/task-selection.json');c={};values=0
    for model in v.MODELS:
        old=joblib.load(H/'validation'/(model.replace(':','-')+'.joblib'))
        name=next(x['selected'] for x in original if x['model']==model and x['arm']=='none' and x['view']=='bytes')
        classifier=old['task_models']['none','bytes',name]
        for view in ['timing_only','no_clock_context']:
            selection=next(x['selected'] for x in chosen if x['model']==model and x['view']==view)
            est=joblib.load(d/(model.replace(':','-')+'-'+view+'.joblib'))
            for arm in v.ARMS:
                rr=sorted([x for x in preds if x['model']==model and x['arm']==arm and x['view']==view],key=lambda r:r['task_id'])
                xx=[];yy=[];truth=[];detpred=[];probabilities=[]
                for saved in rr:
                    r=records[model,arm,saved['task_id']];o=v.extract(r);n=len(o['cover'])
                    if view=='timing_only':x=o['call_features'][:,:3]
                    else:
                        x=np.column_stack([np.repeat(o['bytes'][None,:],n,axis=0),np.arange(n),o['call_features'][:,2],o['call_features'][:,3:],
                                           np.log1p(np.array([w['bytes'] for w in o['trace']]))])
                        assert x.shape==(n,164)
                    probability=v.probabilities(est,x)[:,1];probability[0]=0
                    p=probability>=selection['threshold'];p[0]=False
                    assert list(p.astype(int))==saved['call_prediction'] and list(o['cover'])==saved['call_truth']
                    xx.append(v.basic([w for i,w in enumerate(o['trace']) if not p[i]]));yy.append(saved['truth'])
                    truth.extend(o['cover']);detpred.extend(p);probabilities.extend(probability);values+=n
                pred=np.argmax(v.probabilities(classifier,np.stack(xx)),axis=1)
                assert list(pred)==[x['prediction'] for x in rr]
                c[model,arm,view]=pred==np.array(yy)
                row=next(x for x in rows if x['model']==model and x['arm']==arm and x['view']==view)
                assert row['task_correct']==int(sum(c[model,arm,view]))
                y=np.array(truth);p=np.array(detpred);met=row['detector_metrics']
                assert met['tp']==int(sum((y==1)&p)) and met['fp']==int(sum((y==0)&p))
                assert met['fn']==int(sum((y==1)&~p)) and met['tn']==int(sum((y==0)&~p))
                a=v.auc(y,np.array(probabilities));assert a==met['auc'] or abs(a-met['auc'])<1e-12
    comps=load(d/'comparisons.json')
    for row in comps:
        a=c[row['model'],row['arm'],'timing_only'];b=c[row['model'],row['arm'],'no_clock_context']
        plus=int(sum(a&~b));minus=int(sum(b&~a));n=plus+minus
        p=min(1.,2*sum(math.comb(n,k) for k in range(min(plus,minus)+1))/2**n) if n else 1.
        assert row['condition_only']==plus and row['reference_only']==minus and abs(row['p_raw']-p)<1e-14
    last=0
    for i,row in enumerate(sorted(comps,key=lambda z:z['p_raw'])):
        last=max(last,min(1,row['p_raw']*(len(comps)-i)));assert abs(last-row['p_holm'])<1e-14
    result={'status':'PASS','scope':'Separate feature construction and NumPy LR/RF inference for both post-scoring channels; all call masks, task predictions, exact paired tests and Holm values. Exploratory status unchanged.',
            'test_tasks':len(preds),'call_masks_checked':values,'code_sha256':v.sha(Path(__file__))}
    target=d/'verification.json';assert not target.exists();target.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
