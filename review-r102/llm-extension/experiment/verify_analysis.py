"""Recalculate held-out counts, selection, costs and exact tests from artifacts.

This checker uses a separately written feature map and combinatorial p-values.
It does not import the analysis implementation or change fitted predictors.
"""
import os
os.environ['OMP_NUM_THREADS']='2';os.environ['OPENBLAS_NUM_THREADS']='2'
import csv, math
from collections import Counter
from common import H, load, save, sha, now
import numpy as np
import joblib

SERVICES=['helpdesk','crm','policy','orders','payments','billing','shipping']
LABELS=['refund','address_update','escalation','replacement','cancellation','receipt']

def public_features(r):
    sequence=r['wire_trace'];answer=[]
    for j in range(16):
        answer.extend([int(j<len(sequence) and sequence[j]['service']==s) for s in SERVICES])
    answer.extend([sum(t['service']==s for t in sequence) for s in SERVICES])
    for j in range(16):answer.extend(sequence[j]['bytes'] if j<len(sequence) else [0,0])
    answer.extend([len(sequence),sum(sum(x['bytes']) for x in sequence)])
    return np.array(answer,float)

def exact(plus,minus):
    n=plus+minus
    return min(1.,2*sum(math.comb(n,k) for k in range(min(plus,minus)+1))/(2**n)) if n else 1.

def resampling_positions(y):
    generator=np.random.default_rng(102)
    blocks=[]
    for k in range(6):
        members=np.flatnonzero(np.asarray(y)==k)
        blocks.append(members[generator.integers(len(members),size=(10000,len(members)))])
    return np.hstack(blocks)

def interval(values,draws):
    replicates=np.asarray(values,dtype=float)[draws].sum(axis=1)/draws.shape[1]
    return np.percentile(replicates,[2.5,97.5])

def main():
    out=H/'analysis';rec=load(out/'analysis-receipt.json');raw=H/'private-run/formal-v1'
    for p,v in rec['files'].items():assert sha(out/p)==v,p
    rows={}
    for p,digest in rec['raw_results'].items():
        assert sha(raw/p)==digest
        r=load(raw/p);rows[r['model'],r['arm'],r['task_id']]=r
    assert len(rows)==3600
    f=np.load(out/'features.npz',allow_pickle=False)
    for i in range(len(f['y'])):
        r=rows[str(f['model'][i]),str(f['arm'][i]),int(f['task'][i])]
        assert np.array_equal(public_features(r),f['X'][i])
        assert LABELS[int(f['y'][i])]==r['label']
    selections={(x['model'],x['arm']):x for x in load(out/'validation-selection.json')}
    scores={(x['model'],x['arm'],x['attack']):x for x in load(out/'recognition.json')}
    pred=list(csv.DictReader((out/'predictions.csv').open(newline='',encoding='utf-8')))
    cost=list(csv.DictReader((out/'outcomes-costs.csv').open(newline='',encoding='utf-8')))
    planned=load(H/'experiment/cohort-plan.json');per_task={}
    for model in planned['models']:
        for arm in planned['arms']:
            chosen=selections[model,arm];estimators={}
            for alg in ['LR','RF']:
                est=joblib.load(out/'predictors'/f'{model.replace(":","-")}-{arm}-{alg}.joblib');estimators[alg]=est
                mask=(f['model']==model)&(f['arm']==arm)&(f['split']=='validation')
                y=f['y'][mask];yhat=est.predict(f['X'][mask])
                ba=sum(float(np.mean(yhat[y==k]==k)) for k in range(6))/6
                assert abs(ba-chosen['validation_BA'][alg])<1e-12
            winner='LR' if chosen['validation_BA']['LR']>=chosen['validation_BA']['RF'] else 'RF'
            assert winner==chosen['selected']
            ps=sorted([p for p in pred if(p['model'],p['arm'])==(model,arm)],key=lambda p:int(p['task_id']))
            assert len(ps)==120 and Counter(int(p['y']) for p in ps)=={i:20 for i in range(6)}
            rs=[rows[model,arm,int(p['task_id'])] for p in ps];X=np.stack([public_features(r) for r in rs])
            draws=resampling_positions([int(p['y']) for p in ps])
            frozen_name=selections[model,'none']['selected']
            frozen=joblib.load(out/'predictors'/f'{model.replace(":","-")}-none-{frozen_name}.joblib')
            checks={'LR':estimators['LR'].predict(X),'RF':estimators['RF'].predict(X),
                    'selected':estimators[winner].predict(X),'frozen':frozen.predict(X)}
            for alg in ['LR','RF','selected','frozen','position_last','position_penultimate']:
                cm=np.zeros((6,6),dtype=int)
                for j,p in enumerate(ps):
                    y=int(p['y']);z=int(p[alg]);cm[y,z]+=1
                    if alg in checks:assert z==checks[alg][j]
                    else:
                        offset=-1 if alg=='position_last' else -2
                        sequence=rs[j]['wire_trace']
                        services_to_labels={'payments':0,'crm':1,'helpdesk':2,'shipping':3,'orders':4,'billing':5}
                        expected=services_to_labels.get(sequence[offset]['service'],0) if len(sequence)>=abs(offset) else 0
                        assert z==expected
                score=scores[model,arm,alg]
                assert cm.tolist()==score['confusion'] and int(cm.trace())==score['correct']
                assert abs(float(cm.trace()/120)-score['balanced_accuracy'])<1e-12
                correctness=[int(p[alg]==p['y']) for p in ps]
                assert np.allclose(interval(correctness,draws),score['conditional_ci'],rtol=0,atol=1e-12)
            for p,r in zip(ps,rs):
                for flag in ['goal_success','state_integrity']:assert int(p[flag])==int(r[flag])
                per_task[model,arm,int(p['task_id'])]=p
            for c in [c for c in cost if(c['model'],c['arm'])==(model,arm)]:
                ep=c['endpoint']
                if ep in ['goal_success','state_integrity']:v=[int(r[ep]) for r in rs]
                elif ep in ['transport_byte_ratio','tool_byte_ratio']:
                    key='transport_total_bytes' if ep=='transport_byte_ratio' else 'tool_cipher_bytes'
                    v=[r[key]/rows[model,'none',r['task_id']][key] for r in rs]
                elif ep=='model_calls':v=[r['model_steps'] for r in rs]
                elif ep=='wall_seconds':v=[r['end']-r['start'] for r in rs]
                elif ep in ['prompt_tokens','output_tokens']:
                    key='prompt_eval_count' if ep=='prompt_tokens' else 'eval_count';v=[sum(x[key] for x in r['model_usage']) for r in rs]
                else:v=[sum(x['kind']==('honest' if ep=='honest_calls' else 'cover') for x in r['calls']) for r in rs]
                assert abs(np.mean(v)-float(c['mean']))<1e-9
                assert abs(np.median(v)-float(c['median']))<1e-9
                assert np.allclose(np.quantile(v,[.25,.75]),[float(c['q25']),float(c['q75'])],rtol=0,atol=1e-9)
                assert np.allclose(interval(v,draws),[float(c['conditional_ci_low']),float(c['conditional_ci_high'])],rtol=0,atol=1e-9)
    comparisons=load(out/'paired-comparisons.json')
    for endpoint,family in comparisons.items():
        assert len(family)==12
        for r in family:
            ids=sorted(t for m,a,t in per_task if m==r['model'] and a==r['condition'])
            pairs=[(per_task[r['model'],r['condition'],i],per_task[r['model'],r['reference'],i]) for i in ids]
            if endpoint=='privacy':diff=[int(a['selected']==a['y'])-int(b['selected']==b['y']) for a,b in pairs]
            else:diff=[int(a[endpoint])-int(b[endpoint]) for a,b in pairs]
            plus=diff.count(1);minus=diff.count(-1)
            assert r['condition_only']==plus and r['reference_only']==minus
            assert math.isclose(exact(plus,minus),r['p_raw'],rel_tol=1e-12,abs_tol=1e-300)
            assert abs(100*sum(diff)/120-r['difference_pp'])<1e-12
            draws=resampling_positions([int(a['y']) for a,b in pairs])
            assert np.allclose(100*interval(diff,draws),r['conditional_ci_pp'],rtol=0,atol=1e-10)
        running=0.
        for i,r in enumerate(sorted(family,key=lambda r:r['p_raw'])):
            running=max(running,min(1.,r['p_raw']*(12-i)))
            assert math.isclose(running,r['p_holm'],rel_tol=1e-12,abs_tol=1e-300)
    receipt={'utc':now(),'status':'PASS','episodes':len(rows),'test_rows':len(pred),
             'scope':'Independent feature reconstruction, frozen predictor and position-rule replay, validation-only selection, confusion matrices, paired counts, exact tests, Holm families, stratified conditional intervals and cost arithmetic.',
             'verifier_sha256':sha(__file__),
             'analysis_receipt_sha256':sha(out/'analysis-receipt.json')}
    path=H/'verification/formal-analysis-verified.json';assert not path.exists();save(path,receipt)
    print(receipt)

if __name__=='__main__':main()
