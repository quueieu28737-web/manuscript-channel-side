"""Separate saved-vector/count/statistic checks, without importing P0 fitters."""
import argparse, collections, csv, hashlib, json, math
from pathlib import Path
from datetime import datetime, timezone

LABELS=['refund','address_update','escalation','replacement','cancellation','receipt']
ARMS={'No cover':'none','Immediate':'unmatched','History, sequential':'gdm_live','History, concurrent':'concurrent','Planner shadow':'shadow'}

def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def rows(p):
    with Path(p).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def exact(a,b):
    plus=sum(x and not y for x,y in zip(a,b));minus=sum(y and not x for x,y in zip(a,b));n=plus+minus
    p=min(1.,2*sum(math.comb(n,i) for i in range(min(plus,minus)+1))/2**n) if n else 1.
    return plus,minus,p
def check_tests(rs,lookup):
    raw=[]
    for r in rs:
        a,b=lookup(r);assert len(a)==len(b)==int(r['n'])==120
        plus,minus,p=exact(a,b)
        assert (plus,minus)==(int(r['condition_only']),int(r['reference_only']))
        assert abs(p-float(r['p_raw']))<1e-12
        assert abs(100*(plus-minus)/len(a)-float(r['difference_pp']))<1e-10
        raw.append((r,p))
    last=0.
    for rank,(r,p) in enumerate(sorted(raw,key=lambda z:z[1])):
        last=max(last,min(1.,p*(len(raw)-rank)))
        assert abs(last-float(r['p_holm']))<1e-12
    return len(rs)
def group_predictions(rs,ablation):
    d=collections.defaultdict(dict)
    for r in rs:
        key=((r['variant'],) if ablation else ())+tuple(r[k] for k in ['model','arm','split','attack'])
        unit=int(r['unit']);assert unit not in d[key]
        pred,truth=int(r['prediction']),int(r['truth']);assert 0<=pred<6 and 0<=truth<6
        d[key][unit]=(pred,truth)
    return d
def vector(g,key):return [x==y for _,(x,y) in sorted(g[key].items())]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True,type=Path);a=ap.parse_args();o=a.out
    seal=load(o/'LOCAL-ONLY-input-manifest.json');live=Path(seal['live_root']);checks=0
    for path,digest in seal['files'].items():
        assert sha(live/path)==digest,path;checks+=1
    freeze=load(o/'freeze.json');assert sha(o/'LOCAL-ONLY-input-manifest.json')==freeze['input_seal_sha256']
    ag=group_predictions(rows(o/'LOCAL-ONLY-p0a-predictions.csv'),True)
    aa=rows(o/'p0a-attacks.csv');amap={}
    for r in aa:
        base=r['variant'],r['model'],ARMS[r['arm']]
        assert sum(vector(ag,(*base,'test',r['attack'])))==int(r['test_correct'])
        assert sum(vector(ag,(*base,'validation',r['attack'])))==int(r['validation_correct']);checks+=2
    for s in load(o/'p0a-summary.json')['selections']:
        base=s['variant'],s['model'],ARMS[s['arm']]
        ns=list(s['validation']);scores=s['validation']
        size=[n for n in ns if n in ['byte_LR','byte_RF','frozen','position_last','position_penultimate']]
        assert s['size_selected']==max(size,key=lambda n:(scores[n],-ns.index(n)))
        assert s['adaptive_selected']==max(ns,key=lambda n:(scores[n],-ns.index(n)))
        amap[base]=s;checks+=2
    def avec(v,m,ar,which):return vector(ag,(v,m,ar,'test',amap[v,m,ar][which]))
    def alookup(r):
        m,ar=r['model'],ARMS[r['arm']]
        if r['contrast']=='full_adaptive - no_time_adaptive':return avec('full',m,ar,'adaptive_selected'),avec('no_time',m,ar,'adaptive_selected')
        if r['contrast']=='no_time_adaptive - full_size_selected':return avec('no_time',m,ar,'adaptive_selected'),avec('full',m,ar,'size_selected')
        assert r['contrast']=='full_adaptive - no_position_adaptive'
        return avec('full',m,ar,'adaptive_selected'),avec('no_position',m,ar,'adaptive_selected')
    at=rows(o/'p0a-tests.csv');assert sum(r['family']=='A' for r in at)==8 and sum(r['family']=='B' for r in at)==4
    for fam in ['A','B']:checks+=check_tests([r for r in at if r['family']==fam],alookup)
    reproduction=rows(o/'p0a-reproduction.csv')
    assert len(reproduction)==60 and all(all(r[k]=='True' for k in ['count_match','prediction_match','validation_match','selection_match']) for r in reproduction)
    assert load(o/'p0a-full-gate.json')['status']=='PASS';checks+=61
    cg=group_predictions(rows(o/'LOCAL-ONLY-p0c-predictions.csv'),False)
    for r in rows(o/'p0c-attacks.csv'):
        base=r['model'],ARMS[r['arm']]
        assert sum(vector(cg,(*base,'test',r['attack'])))==int(r['test_correct'])
        assert sum(vector(cg,(*base,'validation',r['attack'])))==int(r['validation_correct']);checks+=2
    cs=load(o/'p0c-summary.json')
    for s in cs['selections']:
        ns=list(s['validation_correct']);scores=s['validation_correct']
        base=[n for n in ns if n.startswith('base_')];strong=[n for n in ns if not n.startswith('base_')]
        assert s['baseline']==max(base,key=lambda n:(scores[n],-ns.index(n)))
        assert s['strong']==max(strong,key=lambda n:(scores[n],-ns.index(n)));checks+=2
        assert s['overall']==max(ns,key=lambda n:(scores[n],-ns.index(n)));checks+=1
    ct=rows(o/'p0c-tests.csv');assert len(ct)==8
    checks+=check_tests(ct,lambda r:(vector(cg,(r['model'],ARMS[r['arm']],'test',r['strong'])),vector(cg,(r['model'],ARMS[r['arm']],'test',r['baseline']))))
    predseal=load(o/'p0c-prediction-seal.json');assert predseal['sha256']==sha(o/'LOCAL-ONLY-p0c-predictions.csv') and predseal['test_call_truth_accessed'] is False
    for r in rows(o/'p0c-event-audit.csv'):
        assert sum(int(r[k]) for k in ['mixed_events','pure_cover_events','pure_real_events','unmatched_events'])==int(r['test_events'])
        tp,bp,bt=[int(r[k]) for k in ['boundary_tp','boundary_predicted','boundary_truth']]
        assert abs(float(r['segmentation_f1_iou50'])-2*tp/(bp+bt))<1e-12;checks+=2
    # Existing saved predictions/roles independently reproduce the fast diagnostics.
    records=[]
    for path in seal['files']:
        if path.endswith('/result.json'):records.append(load(live/path))
    assert len(records)==3000
    saved=collections.defaultdict(dict)
    for r in rows(live/'analysis/predictions.csv'):saved[r['model'],r['arm'],r['attack']][int(r['task_id'])]=(int(r['prediction']),int(r['truth']))
    strata={}
    for r in records:
        if r['split']!='test':continue
        tr=sorted(r['wire_trace'],key=lambda c:(c['start_ns'],c['end_ns']))
        b=[c for c in tr if c['role']=='real' and c['kind']=='honest' and c['operation'] in LABELS]
        key=r['model'],r['arm'],r['task_id']
        if not b:strata[key]='no_business';continue
        last=b[-1]
        cover=[c for c in tr if c['role']=='shadow' and c['operation'] in LABELS] if r['arm']=='shadow' else [c for c in tr if c['kind']=='cover']
        strata[key]='covered' if any(c['start_ns']>last['start_ns'] for c in cover) else 'uncovered'
    for r in rows(o/'p0t-attack-strata.csv'):
        m,ar,att=r['model'],ARMS[r['arm']],r['attack']
        groups={k:[] for k in ['covered','uncovered','no_business']}
        for unit,(pred,truth) in saved[m,ar,att].items():groups[strata[m,ar,unit]].append(pred==truth)
        for g,x in groups.items():assert len(x)==int(r[g+'_n']) and sum(x)==int(r[g+'_correct']);checks+=1
    diag={(r['model'],r['task_id']):r for r in load(live/'analysis/results.json')['shadow_chain_diagnostics']}
    rsummary=load(o/'p0b-summary.json');rvectors={}
    for t in rsummary['R1']:
        model=t['model'];train=[r for r in records if r['model']==model and r['arm']=='shadow' and r['split']=='train']
        majority=sum(not r['shadow_schedule']['shadow_first'] for r in train)*2>=len(train)
        test=sorted([r for r in records if r['model']==model and r['arm']=='shadow' and r['split']=='test'],key=lambda r:r['task_id'])
        selector=[];baseline=[]
        for r in test:
            truth=not r['shadow_schedule']['shadow_first']
            assert (r['wire_trace'][0]['role']=='real')==truth
            selector.append((diag[model,r['task_id']]['first_chain_real_probability']>=.5)==truth);baseline.append(majority==truth)
        assert sum(selector)==t['selector_correct'] and sum(baseline)==t['baseline_correct']
        rvectors[model]=(selector,baseline)
    checks+=check_tests(rsummary['R1'],lambda r:rvectors[r['model']])
    t2=[]
    for r in rows(o/'p0b-task-labels.csv'):
        test={x['task_id']:x for x in records if x['model']==r['model'] and x['arm']=='shadow' and x['split']=='test'}
        same=[];different=[]
        for unit,x in test.items():
            real=LABELS.index(x['label']);shadow=LABELS.index(x['shadow_schedule']['decoy_action']);pred=saved[r['model'],'shadow',r['attack']][unit][0]
            (same if real==shadow else different).append((pred,real,shadow))
        hits=sum(p==q for p,q,s in different);sh=sum(p==s for p,q,s in different)
        assert hits==int(r['different_correct']) and sh==int(r['different_pred_is_shadow'])
        assert len(same)==int(r['matching_n']) and sum(p==q for p,q,s in same)==int(r['matching_correct'])
        assert len(different)==int(r['different_n']);checks+=3
        n=hits+sh;p=min(1.,2*sum(math.comb(n,i) for i in range(min(hits,sh)+1))/2**n) if n else 1.
        assert abs(p-float(r['sign_test_p_raw']))<1e-12
        if 'adaptive' in r['selected']:t2.append((r['model'],p))
    last=0.
    for rank,(model,p) in enumerate(sorted(t2,key=lambda r:r[1])):
        last=max(last,min(1.,p*(len(t2)-rank)));actual=next(r for r in rsummary['T2_selected'] if r['model']==model)
        assert abs(last-actual['p_holm'])<1e-12;checks+=1
    output={'status':'SAVED_VECTORS_ARITHMETIC_AND_INPUTS_VERIFIED','utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'unchanged_original_input_files':len(seal['files']),'full_reproduction_rows':len(reproduction),'ablation_family_tests':{'A':8,'B':4},'record_only_tests':8,'scope':'Independent saved-vector/selection/paired-statistic arithmetic and input preservation; not a second fit or external-validity guarantee','individual_data_released':False}
    (o/'verification.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8');print(json.dumps(output,indent=2),flush=True)
if __name__=='__main__':main()
