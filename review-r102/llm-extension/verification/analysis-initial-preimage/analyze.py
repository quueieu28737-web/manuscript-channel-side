"""Frozen LR/RF suite, validation selection and held-out paired M3 analysis."""
import os
os.environ['OMP_NUM_THREADS']='2';os.environ['OPENBLAS_NUM_THREADS']='2'
from collections import Counter
import csv, math, time
from common import H, enc, load, save, sha, now
import numpy as np
import joblib
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score, confusion_matrix
from scipy.stats import binomtest

SERVICES=['helpdesk','crm','policy','orders','payments','billing','shipping']
LABELS=['refund','address_update','escalation','replacement','cancellation','receipt']
ARMS=['none','transport_drop','read','isolated','live_write','isolated_visible']
SEED=102

def features(r):
    # Whitelist; kind, operation, requested label and server results never enter.
    public=[(x['service'],x['bytes'][0],x['bytes'][1]) for x in r['wire_trace']]
    x=np.zeros(16*7+7+16*2+2,dtype=float);base=16*7
    for k,(s,up,dn) in enumerate(public):
        j=SERVICES.index(s);x[base+j]+=1
        if k<16:x[k*7+j]=1;x[base+7+k*2:base+7+k*2+2]=[up,dn]
    x[-2:]=[len(public),sum(u+d for _,u,d in public)]
    return x

def estimators():
    return {'LR':make_pipeline(StandardScaler(),LogisticRegression(C=1,max_iter=3000,random_state=SEED)),
            'RF':RandomForestClassifier(n_estimators=300,random_state=SEED,n_jobs=2)}

def choose(scores):
    return max(['LR','RF'],key=lambda n:(scores[n],n=='LR'))

def stratified_indices(y,n=10000):
    rng=np.random.default_rng(SEED)
    return np.concatenate([rng.choice(np.flatnonzero(y==k),(n,sum(y==k)),replace=True) for k in range(6)],axis=1)

def ci(values,idx):
    means=np.asarray(values,dtype=float)[idx].mean(axis=1)
    return np.quantile(means,[.025,.975]).tolist()

def exact_p(a,b):
    d=np.asarray(a,dtype=int)-np.asarray(b,dtype=int)
    plus=int(sum(d==1));minus=int(sum(d==-1))
    return float(binomtest(plus,plus+minus,.5).pvalue) if plus+minus else 1.

def holm(rows):
    order=sorted(range(len(rows)),key=lambda i:rows[i]['p_raw']);last=0.
    for rank,i in enumerate(order):
        last=max(last,min(1.,rows[i]['p_raw']*(len(rows)-rank)))
        rows[i]['p_holm']=last

def write_csv(p,rows):
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    start=time.time();out=H/'analysis'
    assert load(H/'verification/formal-v1-verified.json')['status']=='PASS'
    for name,digest in load(H/'experiment/analysis-freeze.json')['files'].items():assert sha(H/name)==digest,name
    out.mkdir(exist_ok=False)
    raw=H/'private-run/formal-v1';results=[load(p) for p in sorted((raw/'episodes').glob('*/result.json'))]
    assert len(results)==3600
    (out/'predictors').mkdir()
    data={};rows=[];prediction_rows=[];selection=[];metric_rows=[];comparisons={x:[] for x in ['privacy','goal_success','state_integrity']}
    for r in results:data[r['model'],r['arm'],r['task_id']]=r
    models=load(H/'experiment/cohort-plan.json')['models']
    for model in models:
        sets={s:sorted({r['task_id'] for r in results if r['model']==model and r['split']==s}) for s in ['train','validation','test']}
        train_y=np.array([LABELS.index(data[model,'none',i]['label']) for i in sets['train']])
        val_y=np.array([LABELS.index(data[model,'none',i]['label']) for i in sets['validation']])
        test_y=np.array([LABELS.index(data[model,'none',i]['label']) for i in sets['test']])
        assert Counter(test_y)=={k:20 for k in range(6)}
        idx=stratified_indices(test_y); fitted={};selected={};preds={};test_metrics={}
        # Select with validation before asking any model for held-out predictions.
        for arm in ARMS:
            Xtr=np.stack([features(data[model,arm,i]) for i in sets['train']])
            Xv=np.stack([features(data[model,arm,i]) for i in sets['validation']])
            scores={}
            for name,est in estimators().items():
                est.fit(Xtr,train_y);score=float(balanced_accuracy_score(val_y,est.predict(Xv)))
                scores[name]=score;fitted[arm,name]=est
                joblib.dump(est,out/'predictors'/f'{model.replace(":","-")}-{arm}-{name}.joblib')
            selected[arm]=choose(scores)
            selection.append({'model':model,'arm':arm,'selected':selected[arm],'validation_BA':scores})
        frozen=fitted['none',selected['none']]
        for arm in ARMS:
            rs=[data[model,arm,i] for i in sets['test']];X=np.stack([features(r) for r in rs])
            pred={n:fitted[arm,n].predict(X) for n in ['LR','RF']}
            pred['selected']=pred[selected[arm]];pred['frozen']=frozen.predict(X)
            mapping={'payments':0,'crm':1,'helpdesk':2,'shipping':3,'orders':4,'billing':5}
            for name,offset in [('position_last',-1),('position_penultimate',-2)]:
                pred[name]=np.array([mapping.get(r['wire_trace'][offset]['service'],0) for r in rs])
            preds[arm]=pred; test_metrics[arm]={}
            baseline_bytes=np.array([data[model,'none',i]['transport_total_bytes'] for i in sets['test']],float)
            baseline_tool=np.array([data[model,'none',i]['tool_cipher_bytes'] for i in sets['test']],float)
            metrics={'goal_success':np.array([r['goal_success'] for r in rs],int),
                     'state_integrity':np.array([r['state_integrity'] for r in rs],int),
                     'transport_byte_ratio':np.array([r['transport_total_bytes'] for r in rs])/baseline_bytes,
                     'tool_byte_ratio':np.array([r['tool_cipher_bytes'] for r in rs])/baseline_tool,
                     'model_calls':np.array([r['model_steps'] for r in rs]),
                     'prompt_tokens':np.array([sum(m['prompt_eval_count'] for m in r['model_usage']) for r in rs]),
                     'output_tokens':np.array([sum(m['eval_count'] for m in r['model_usage']) for r in rs]),
                     'wall_seconds':np.array([r['end']-r['start'] for r in rs]),
                     'honest_calls':np.array([sum(c['kind']=='honest' for c in r['calls']) for r in rs]),
                     'cover_calls':np.array([sum(c['kind']=='cover' for c in r['calls']) for r in rs])}
            for endpoint,v in metrics.items():
                test_metrics[arm][endpoint]=v
                metric_rows.append({'model':model,'arm':arm,'endpoint':endpoint,'n':len(v),
                                   'mean':float(v.mean()),'median':float(np.median(v)),
                                   'q25':float(np.quantile(v,.25)),'q75':float(np.quantile(v,.75)),
                                   'conditional_ci_low':ci(v,idx)[0],'conditional_ci_high':ci(v,idx)[1]})
            for name,v in pred.items():
                correct=v==test_y
                rows.append({'model':model,'arm':arm,'attack':name,'selected_algorithm':selected[arm] if name=='selected' else selected['none'] if name=='frozen' else name,
                   'n':len(v),'correct':int(correct.sum()),'balanced_accuracy':float(balanced_accuracy_score(test_y,v)),
                   'conditional_ci':ci(correct,idx),'confusion':confusion_matrix(test_y,v,labels=list(range(6))).tolist()})
            for j,r in enumerate(rs):
                prediction_rows.append({'model':model,'arm':arm,'task_id':r['task_id'],'label':r['label'],'y':int(test_y[j]),
                  **{name:int(v[j]) for name,v in pred.items()},'goal_success':int(r['goal_success']),
                  'state_integrity':int(r['state_integrity']),'status':r['status'],'model_calls':r['model_steps']})
        pairs=[(arm,'none') for arm in ARMS if arm!='none']+[('isolated_visible','isolated')]
        for endpoint in comparisons:
            for arm,base in pairs:
                a=(preds[arm]['selected']==test_y).astype(int) if endpoint=='privacy' else test_metrics[arm][endpoint]
                b=(preds[base]['selected']==test_y).astype(int) if endpoint=='privacy' else test_metrics[base][endpoint]
                comparisons[endpoint].append({'model':model,'condition':arm,'reference':base,'n_pairs':len(a),
                  'difference_pp':float(100*(a-b).mean()),'conditional_ci_pp':(100*np.array(ci(a-b,idx))).tolist(),
                  'condition_only':int(sum((a==1)&(b==0))),'reference_only':int(sum((a==0)&(b==1))),
                  'p_raw':exact_p(a,b)})
    for v in comparisons.values():assert len(v)==12;holm(v)
    save(out/'validation-selection.json',selection)
    save(out/'recognition.json',rows);save(out/'paired-comparisons.json',comparisons)
    write_csv(out/'predictions.csv',prediction_rows);write_csv(out/'outcomes-costs.csv',metric_rows)
    # Portable feature/outcome data, including all training and validation rows.
    ordered=sorted(results,key=lambda r:(r['model'],r['arm'],r['task_id']))
    np.savez_compressed(out/'features.npz',X=np.stack([features(r) for r in ordered]),
        y=np.array([LABELS.index(r['label']) for r in ordered]),
        model=np.array([r['model'] for r in ordered]),arm=np.array([r['arm'] for r in ordered]),
        split=np.array([r['split'] for r in ordered]),task=np.array([r['task_id'] for r in ordered]))
    save(out/'episode-outcomes.json',[{k:r[k] for k in ['job_id','model','arm','task_id','split','label','status','goal_success','state_integrity','intended_action_succeeded','checks_satisfied','model_steps','model_usage','start','end','transport_total_bytes','tool_cipher_bytes','executed_decoys','planned_decoys']} for r in ordered])
    save(out/'analysis-receipt.json',{'utc':now(),'status':'COMPLETE','seconds':time.time()-start,'episodes':len(results),
       'test_predictions':len(prediction_rows),'features':153,'analysis_plan_sha256':sha(H/'experiment/analysis-plan.json'),
       'raw_results':{str(p.relative_to(raw)):sha(p) for p in sorted((raw/'episodes').glob('*/result.json'))},
       'files':{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()},
       'interpretation':'Attack accuracies are attained lower bounds for this observer, not Bayes upper bounds. Validation-selected attack is primary; strongest test point is not a selected primary. Intervals condition on fitted attacks and synthetic workload.'})
    print('M3 formal analysis complete: 3600 episodes, 1440 held-out decisions')

if __name__=='__main__':main()
