"""Separate extraction, array inference and exact arithmetic audit of B1.

No calls into b1.py and no model/API requests. Serialized predictors are ones
just trained locally from the original public synthetic data, not remote input.
"""
from pathlib import Path
from collections import Counter
import csv
import gzip
import hashlib
import json
import math
import sys
import datetime
import os
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['OPENBLAS_NUM_THREADS'] = '2'
import numpy as np
import joblib

H = Path(__file__).resolve().parent
ROOT = H.parent.parent
S = ROOT / 'revision-preview/r102-llm-executed-cover/review-export'
MODELS = ['qwen3:8b','llama3.1:8b']
ARMS = ['none','transport_drop','read','isolated','live_write','isolated_visible']
SERVICES = ['helpdesk','crm','policy','orders','payments','billing','shipping']
LABELS = ['refund','address_update','escalation','replacement','cancellation','receipt']
load = lambda p: json.loads(p.read_text(encoding='utf-8'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def basic(trace):
    z = [0.]*153
    for k,w in enumerate(trace):
        j = SERVICES.index(w['service'])
        z[112+j] += 1
        if k < 16:
            z[7*k+j] = 1
            z[119+2*k:121+2*k] = w['bytes']
    z[151] = len(trace)
    z[152] = sum(sum(w['bytes']) for w in trace)
    return np.array(z)


def extract(r):
    byid = {t['request']['request_id']:t for t in r['tool_receipts']}
    events = [byid[w['request_id']] for w in r['wire_trace']]
    times = [(t['terminal']['start'],t['terminal']['end']) for t in events]
    relative = []
    for i,(a,b) in enumerate(times):
        gap = 0 if i == 0 else a-times[i-1][1]
        assert b>a and gap>=0
        relative.append([a-times[0][0],b-a,gap])
    t = np.array(relative)
    a = np.zeros(49)
    a[:3*min(16,len(t))] = np.array(relative[:16]).reshape(-1)
    a[48] = r['wall_seconds']
    f = np.zeros((len(times),10))
    f[:,0] = np.log1p(1000*t[:,2]);f[:,1] = np.log1p(1000*t[:,1]);f[0,2] = 1
    for i,w in enumerate(r['wire_trace']): f[i,3+SERVICES.index(w['service'])] = 1
    kinds = np.array([int(x['request']['kind']=='cover') for x in events])
    assert list(kinds)==[int(w['kind']=='cover') for w in r['wire_trace']]
    return {'bytes':basic(r['wire_trace']), 'timing_only':a, 'timing_size':np.r_[basic(r['wire_trace']),a],
            'call_features':f,'cover':kinds,'trace':r['wire_trace'],'times':t}


def probabilities(est,x):
    if hasattr(est,'steps'):
        scaler,lr = est.steps[0][1],est.steps[1][1]
        z = ((x-scaler.mean_)/scaler.scale_)@lr.coef_.T+lr.intercept_
        if z.shape[1]==1:
            p=1/(1+np.exp(-z[:,0]));return np.column_stack([1-p,p])
        z-=z.max(axis=1)[:,None];p=np.exp(z);return p/p.sum(axis=1)[:,None]
    assert len(est.estimators_)==300
    xx=np.asarray(x,dtype=np.float32);answer=np.zeros((len(xx),len(est.classes_)))
    for e in est.estimators_:
        tree=e.tree_;nodes=np.zeros(len(xx),dtype=int)
        active=np.flatnonzero(tree.children_left[nodes]!=-1)
        while len(active):
            at=nodes[active];left=xx[active,tree.feature[at]]<=tree.threshold[at]
            nodes[active]=np.where(left,tree.children_left[at],tree.children_right[at])
            active=active[tree.children_left[nodes[active]]!=-1]
        value=tree.value[nodes,0,:];answer+=value/value.sum(axis=1)[:,None]
    return answer/len(est.estimators_)


def auc(y,score):
    positive=int(sum(y));negative=len(y)-positive
    if not positive or not negative:return None
    ordered=sorted(zip(score,y));rank=0.;i=0
    while i<len(ordered):
        j=i+1
        while j<len(ordered) and ordered[j][0]==ordered[i][0]:j+=1
        rank+=(i+1+j)/2*sum(int(v[1]) for v in ordered[i:j]);i=j
    return (rank-positive*(positive+1)/2)/(positive*negative)


def audit():
    freeze=load(H/'freeze.json')
    assert sha(H/'b1.py')==freeze['code_sha256'] and sha(H/'analysis-plan.json')==freeze['plan_sha256']
    for name,digest in freeze['inputs'].items():assert sha(ROOT/name)==digest
    done=load(H/'results/finished.json')
    for n,digest in done['files'].items():assert sha(H/'results'/n)==digest
    vd=load(H/'validation/finished.json')
    for n,digest in vd['files'].items():assert sha(H/'validation'/n)==digest
    task_selections=load(H/'validation/task-selection.json')
    detector_selections=load(H/'validation/detector-selection.json')
    task_predictions=load(H/'results/predictions.json')
    recognition=load(H/'results/recognition.json')
    detection=load(H/'results/cover-detection.json')
    families=load(H/'results/comparisons.json')
    exported=np.load(H/'results/test-arrays.npz',allow_pickle=False)
    tests={};counts=Counter();feature_rows=[];call_rows=[]
    with gzip.open(S/'data/episodes.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            r=json.loads(line);counts[r['split']]+=1
            if r['split']=='test':tests[r['model'],r['arm'],r['task_id']]=r
    assert counts=={'train':1440,'validation':720,'test':1440}
    original=list(csv.DictReader((S/'analysis/predictions.csv').open(encoding='utf8',newline='')))
    correct={};array_index=0;call_index=0;checked_predictions=0;checked_detector_calls=0
    for model in MODELS:
        fits=joblib.load(H/'validation'/(model.replace(':','-')+'.joblib'))
        ds=next(x['selected'] for x in detector_selections if x['model']==model)
        ids=sorted(k[2] for k in tests if k[:2]==(model,'none'))
        y=np.array([LABELS.index(tests[model,'none',i]['label']) for i in ids]);assert Counter(y)=={k:20 for k in range(6)}
        no_choice=next(x['selected'] for x in task_selections if x['model']==model and x['arm']=='none' and x['view']=='bytes')
        for arm in ARMS:
            xs=[extract(tests[model,arm,i]) for i in ids]
            predictions={}
            for view in ['bytes','timing_size','timing_only']:
                x=np.stack([z[view] for z in xs])
                chosen=next(z['selected'] for z in task_selections if z['model']==model and z['arm']==arm and z['view']==view)
                for name in ['LR','RF']:
                    predictions[view+'/'+name]=np.argmax(probabilities(fits['task_models'][arm,view,name],x),axis=1)
                predictions[view+'/selected']=predictions[view+'/'+chosen]
            pp=[];cc=[];yy=[];stripped=[];privileged=[]
            for i,x in enumerate(xs):
                assert np.array_equal(x['timing_size'],exported['features'][array_index])
                assert int(exported['truth'][array_index])==y[i] and int(exported['task'][array_index])==ids[i]
                assert exported['model'][array_index]==model and exported['arm'][array_index]==arm
                n=len(x['cover']);s=slice(call_index,call_index+n)
                assert np.array_equal(x['call_features'],exported['call_features'][s])
                assert np.array_equal(x['cover'],exported['call_truth'][s])
                if ds['name']=='gap_rule':
                    prob=1/(1+x['times'][:,2]);pred=x['times'][:,2]<ds['threshold']
                else:
                    prob=probabilities(fits['detector_models'][ds['name']],x['call_features'])[:,1]
                    pred=prob>=ds['threshold']
                prob[0]=0.;pred[0]=False
                assert np.array_equal(pred.astype(int),exported['call_prediction'][s])
                assert np.allclose(prob,exported['call_probability'][s],rtol=0,atol=1e-13)
                stripped.append(basic([w for j,w in enumerate(x['trace']) if not pred[j]]))
                privileged.append(basic([w for j,w in enumerate(x['trace']) if not x['cover'][j]]))
                pp.extend(prob);cc.extend(pred);yy.extend(x['cover'])
                array_index+=1;call_index+=n;checked_detector_calls+=n
            est=fits['task_models']['none','bytes',no_choice]
            predictions['stripped/frozen_none']=np.argmax(probabilities(est,np.stack(stripped)),axis=1)
            predictions['privileged_cover_labels/frozen_none']=np.argmax(probabilities(est,np.stack(privileged)),axis=1)
            saved=[next(z for z in task_predictions if z['model']==model and z['arm']==arm and z['task_id']==i) for i in ids]
            for name,pred in predictions.items():
                assert list(pred)==[z[name] for z in saved],(model,arm,name)
                metric=next(z for z in recognition if z['model']==model and z['arm']==arm and z['attack']==name)
                assert metric['correct']==int(sum(pred==y))
                correct[model,arm,name]=pred==y;checked_predictions+=len(pred)
            for i,task in enumerate(ids):
                old=next(z for z in original if z['model']==model and z['arm']==arm and int(z['task_id'])==task)
                for name in ['LR','RF']:assert int(old[name])==predictions['bytes/'+name][i]
            actual=np.array(yy);pred=np.array(cc);p=np.array(pp)
            d=next(z for z in detection if z['model']==model and z['arm']==arm)
            assert d['tp']==int(sum((actual==1)&pred)) and d['fp']==int(sum((actual==0)&pred))
            assert d['fn']==int(sum((actual==1)&~pred)) and d['tn']==int(sum((actual==0)&~pred))
            v=auc(actual,p)
            assert v==d['auc'] or (v is not None and abs(v-d['auc'])<1e-12)
    assert array_index==len(exported['features'])==1440 and call_index==len(exported['call_truth'])
    for family,rows in families.items():
        for row in rows:
            model,arm=row['model'],row['arm']
            if family=='primary_timing_size_vs_bytes':a,b=correct[model,arm,'timing_size/selected'],correct[model,arm,'bytes/selected']
            elif family=='secondary_stripping_vs_bytes':a,b=correct[model,arm,'stripped/frozen_none'],correct[model,arm,'bytes/selected']
            else:
                other=row['comparison'].split(' minus ')[1];a,b=correct[model,arm,'timing_size/selected'],correct[model,other,'timing_size/selected']
            plus=int(sum(a&~b));minus=int(sum(b&~a));n=plus+minus
            p=min(1.,2*sum(math.comb(n,k) for k in range(min(plus,minus)+1))/2**n) if n else 1.
            assert plus==row['condition_only'] and minus==row['reference_only']
            assert abs(p-row['p_raw'])<1e-14
            assert abs((int(sum(a))-int(sum(b)))/120*100-row['difference_pp'])<1e-12
        ranked=sorted(rows,key=lambda r:r['p_raw']);last=0
        for j,row in enumerate(ranked):
            last=max(last,min(1,row['p_raw']*(len(rows)-j)))
            assert abs(last-row['p_holm'])<1e-14
    result={'status':'PASS','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'scope':'Separate receipt extraction, original baseline prediction replay, NumPy LR/RF inference, detector masks/AUC, every paired discordance/exact McNemar p-value and Holm family. Not independent human review, new collection or packet-timing validation.',
            'test_episodes':1440,'task_prediction_values_checked':checked_predictions,'detector_call_values_checked':checked_detector_calls,
            'paired_comparisons_checked':sum(len(v) for v in families.values()),'verifier_sha256':sha(Path(__file__))}
    target=H/'verification.json';assert not target.exists();target.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':audit()
