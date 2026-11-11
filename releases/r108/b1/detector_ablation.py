"""Explicitly post-scoring detector-input diagnostic; keep frozen B1 untouched."""
import os
os.environ['OMP_NUM_THREADS']='2';os.environ['OPENBLAS_NUM_THREADS']='2'
import b1 as b
import numpy as np
import json,time
from pathlib import Path

H=Path(__file__).resolve().parent
OUT=H/'diagnostic'


def design(o,view):
    x=b.call_features(o)
    if view=='timing_only':return x[:,:3]
    # Stronger no-clock control: complete original observer vector + current
    # public call position, first flag, destination and log byte counts.
    n=len(o['trace']);base=np.repeat(b.views(o)['bytes'][None,:],n,axis=0)
    pos=np.arange(n,dtype=float)[:,None]
    first=x[:,2:3]
    byte=np.log1p(np.array([w['bytes'] for w in o['trace']],float))
    z=np.column_stack([base,pos,first,x[:,3:],byte])
    assert z.shape[1]==164
    return z


def main():
    b.check_freeze();assert (H/'verification.json').exists() and not OUT.exists()
    OUT.mkdir()
    plan={'utc':b.now(),'status':'POST_SCORING_DIAGNOSTIC_FIXED_BEFORE_ITS_NEW_FITS',
          'code_sha256':b.sha(Path(__file__)),
          'purpose':'Check whether the stripping procedure needs clock inputs; original B1 test outcomes are already known. This is an additional exploratory ablation, not an amended primary or new independent confirmation.',
          'channels':{'timing_only':'3 original log gap/duration/first features; no destination or bytes',
                      'no_clock_context':'164 original observer/context features: full 153-byte/destination episode representation, current call index, first flag, current destination, log ciphertext up/down counts; no clocks'},
          'fit':'Same balanced LR/RF, validation F1 then precision then LR then higher threshold. Threshold grid .05:.05:.95. First call retained. One detector per model/channel pooled over training arms.',
          'downstream':'Same already fitted validation-selected no-cover 153-feature task classifier; no re-fitting on test.',
          'comparisons':'Ten exploratory timing-only-stripping minus no-clock-context-stripping paired exact McNemar values, Holm .05; retain raw and corrected values and all per-channel scores.'}
    b.save(OUT/'plan-freeze.json',plan)
    records=list(b.iter_records({'train','validation','test'}))
    data={(r['model'],r['arm'],r['task_id']):r for r in records}
    obs={key:b.observe(r) for key,r in data.items()}
    task_selection=b.load(H/'validation/task-selection.json')
    rows=[];predictions=[];choices=[];contrasts=[];correct={}
    import joblib
    for model in b.MODELS:
        old=joblib.load(H/'validation'/(model.replace(':','-')+'.joblib'))
        none=next(x['selected'] for x in task_selection if x['model']==model and x['arm']=='none' and x['view']=='bytes')
        classifier=old['task_models']['none','bytes',none]
        ids=sorted(r['task_id'] for r in records if r['model']==model and r['arm']=='none' and r['split']=='test')
        y=np.array([b.LABELS.index(data[model,'none',i]['label']) for i in ids]);indices=b.stratified_bootstrap(y)
        for view in ['timing_only','no_clock_context']:
            tr=[obs[m,a,i] for (m,a,i),r in data.items() if m==model and r['split']=='train']
            va=[obs[m,a,i] for (m,a,i),r in data.items() if m==model and r['split']=='validation']
            xt=np.concatenate([design(o,view) for o in tr]);yt=np.concatenate([o['cover'] for o in tr])
            xv=np.concatenate([design(o,view) for o in va]);yv=np.concatenate([o['cover'] for o in va]);first=np.concatenate([np.arange(len(o['trace']))==0 for o in va])
            candidates=[];models={}
            for name,est in b.detector_models().items():
                est.fit(xt,yt);models[name]=est;prob=est.predict_proba(xv)[:,1]
                for threshold in np.arange(.05,.951,.05):
                    p=(prob>=threshold).astype(int);p[first]=0
                    candidates.append({'name':name,'threshold':float(threshold),'metric':b.detector_metrics(yv,p)})
            chosen=max(candidates,key=lambda z:(z['metric']['f1'],z['metric']['precision'],z['name']=='LR',z['threshold']))
            choices.append({'model':model,'view':view,'selected':chosen,'candidates':candidates})
            estimator=models[chosen['name']]
            joblib.dump(estimator,OUT/(model.replace(':','-')+'-'+view+'.joblib'))
            for arm in b.ARMS:
                os=[obs[model,arm,i] for i in ids];masks=[];probs=[]
                for o in os:
                    prob=estimator.predict_proba(design(o,view))[:,1];prob[0]=0
                    pred=(prob>=chosen['threshold']).astype(int);pred[0]=0
                    masks.append(pred);probs.append(prob)
                prediction=classifier.predict(np.stack([b.stripped(o,p) for o,p in zip(os,masks)]))
                good=prediction==y;correct[model,arm,view]=good
                truth=np.concatenate([o['cover'] for o in os]);p=np.concatenate(masks);prob=np.concatenate(probs)
                rows.append({'model':model,'arm':arm,'view':view,'detector':chosen['name'],'threshold':chosen['threshold'],
                             'task_correct':int(good.sum()),'task_n':len(y),'task_conditional_ci':b.interval(good,indices),
                             'detector_metrics':b.detector_metrics(truth,p,prob)})
                for j,task in enumerate(ids):predictions.append({'model':model,'arm':arm,'view':view,'task_id':task,'truth':int(y[j]),'prediction':int(prediction[j]),'call_truth':os[j]['cover'].tolist(),'call_prediction':masks[j].tolist()})
            print(json.dumps({'diagnostic_model':model,'view':view,'selected':chosen['name']}),flush=True)
        for arm in b.ARMS[1:]:
            contrasts.append(b.contrast(correct[model,arm,'timing_only'],correct[model,arm,'no_clock_context'],model,arm,'timing_only stripping minus no_clock_context stripping',indices))
    b.original.holm(contrasts)
    b.save(OUT/'validation-selection.json',choices);b.save(OUT/'results.json',rows)
    b.save(OUT/'predictions.json',predictions);b.save(OUT/'comparisons.json',contrasts)
    b.save(OUT/'finished.json',{'utc':b.now(),'status':'COMPLETE_POST_SCORING_DIAGNOSTIC','files':{p.name:b.sha(p) for p in OUT.iterdir() if p.is_file()}})
    print('DETECTOR_INPUT_DIAGNOSTIC_COMPLETE',flush=True)


if __name__=='__main__':main()
