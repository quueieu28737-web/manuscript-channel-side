"""Separate arithmetic and call-boundary audit after all predictions are saved."""
from pathlib import Path
import collections,csv,hashlib,json,math,sys
import numpy as np
from scipy.optimize import linear_sum_assignment
H=Path(__file__).resolve().parents[1];sys.path.insert(0,str(H/'experiment'))
import no_call_windows as A
import protocol_record_events as P

def load(p):return json.loads(Path(p).read_text())
def rows(p):
    with Path(p).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def exact(plus,minus):
    n=plus+minus
    return min(1.,2*sum(math.comb(n,i) for i in range(min(plus,minus)+1))/2**n) if n else 1.

def main():
    checks=0
    source=load(H/'inputs/record-only-manifest.json')
    assert A.sha(H/'inputs/record-only.jsonl')==source['sha256'];checks+=1
    data=[json.loads(s) for s in (H/'inputs/record-only.jsonl').read_text().splitlines()]
    assert len(data)==3000 and sum(len(r['records']) for r in data)==710450;checks+=2
    assert {tuple(sorted(r)) for r in data}=={tuple(sorted(['unit','model','arm','split','label','records']))};checks+=1
    for r in data:
        assert all(len(x)==4 and x[0]>=0 and 0<=x[1]<7 and x[2] in [0,1] and x[3]>0 for x in r['records']);checks+=1
    pred=rows(H/'analysis/no-call-predictions.csv');res=load(H/'analysis/no-call-results.json');groups=collections.defaultdict(list)
    for r in pred:groups[r['model'],r['arm'],r['attack']].append(r)
    for a in res['attacks']:
        z=groups[a['model'],a['arm'],a['attack']];assert len(z)==120
        assert sum(r['prediction']==r['truth'] for r in z)==a['correct'];checks+=2
    for c in res['selections']:
        names=list(c['validation_correct']);score=c['validation_correct']
        for key,ns in [('baseline',[n for n in names if not n.startswith('strip_')]),('removal',[n for n in names if n.startswith('strip_')]),('suite',names)]:
            assert c[key]==max(ns,key=lambda n:(score[n],-names.index(n)));checks+=1
    original=[]
    for p in res['primary_immediate_removal']:
        a={r['unit']:r['prediction']==r['truth'] for r in groups[p['model'],'unmatched',p['removal_attack']]}
        b={r['unit']:r['prediction']==r['truth'] for r in groups[p['model'],'unmatched',p['baseline_attack']]}
        plus=sum(a[k] and not b[k] for k in a);minus=sum(b[k] and not a[k] for k in a)
        assert (plus,minus)==(p['plus'],p['minus']);assert abs(exact(plus,minus)-p['p_raw'])<1e-12;checks+=2
        original.append(p)
    last=0.
    for rank,p in enumerate(sorted(original,key=lambda x:x['p_raw'])):
        last=max(last,min(1.,p['p_raw']*(2-rank)));assert abs(last-p['p_holm'])<1e-12;checks+=1
    pr=load(H/'analysis/protocol-event-results.json');pg=collections.defaultdict(list)
    for r in rows(H/'analysis/protocol-event-predictions.csv'):pg[r['model'],r['arm'],r['attack']].append(r)
    for a in pr['attacks']:
        z=pg[a['model'],a['arm'],a['attack']];assert len(z)==120 and sum(v['prediction']==v['truth'] for v in z)==a['correct'];checks+=1
    # Independent private truth appears only below, after prediction arithmetic.
    selected={}
    for c in res['selections']:
        names=[n for n in c['validation_correct'] if n.startswith('burst_')]
        n=max(names,key=lambda n:(c['validation_correct'][n],-list(c['validation_correct']).index(n)))
        selected[c['model'],c['arm']]=float(n.split('_')[1])
    test={(r['model'],r['arm'],r['unit']):r for r in data if r['split']=='test'}
    metrics=collections.defaultdict(lambda:collections.Counter())
    for run in ['formal-none-v1','formal-cover-v1']:
        for f in (A.OLD/'private-run'/run/'episodes').glob('*/result.json'):
            # Job label/arm fields are only a join to test truth, not features.
            old=load(f)
            if old['split']!='test':continue
            k=old['model'],old['arm'],old['task_id'];r=test[k]
            # Recover raw-relative zero from a full connection, not call truth.
            times=[]
            for c in (f.parent/'connections').glob('*.json'):
                w=load(A.OLD/'private-run'/run/'wire'/c.name)
                times.extend(v[2] for seq in w['records'] for v in seq if v[0]==23)
            t0=min(times)
            truth=[[(v['start_ns']-t0)/1e9,(v['end_ns']-t0)/1e9,A.SERVICES.index(v['service'])] for v in old['wire_trace']]
            for method,events in [('idle',A.bursts(r['records'],selected[k[:2]])),('protocol',P.events(r['records']))]:
                # Endpoint IoU over the same destination, one-to-one matching.
                overlap=np.zeros((len(events),len(truth)))
                for i,e in enumerate(events):
                    for j,t in enumerate(truth):
                        if e[2]!=t[2]:continue
                        inter=max(0.,min(e[1],t[1])-max(e[0],t[0]));union=max(e[1],t[1])-min(e[0],t[0])
                        overlap[i,j]=inter/union if union>0 else 0.
                for cutoff in [.3,.5]:
                    score=(overlap>=cutoff)*(min(overlap.shape)+1)+overlap
                    ii,jj=linear_sum_assignment(-score)
                    tp=sum(overlap[i,j]>=cutoff for i,j in zip(ii,jj))
                    m=metrics[old['model'],old['arm'],method,cutoff]
                    m.update(tp=int(tp),predicted=len(events),truth=len(truth),episodes=1)
    out=[]
    for (model,arm,method,cutoff),x in metrics.items():
        tp=x['tp'];precision=tp/x['predicted'];recall=tp/x['truth']
        out.append({'model':model,'arm':arm,'method':method,'iou':cutoff,**dict(x),
                    'precision':precision,'recall':recall,'f1':2*tp/(x['predicted']+x['truth'])})
    assert len(out)==40 and all(x['episodes']==120 for x in out);checks+=41
    A.csvout(H/'analysis/boundary-diagnostic.csv',out)
    A.save(H/'verification/no-call-verified.json',{'status':'PASS','checks':checks,'episodes':3000,
        'prediction_rows':len(pred),'protocol_prediction_rows':sum(len(x) for x in pg.values()),
        'boundary_audit_rows':40,'scope':'Separate saved-vector arithmetic, exposure schema, selection and private boundary audit. Does not establish universal attacker optimality.',
        'inputs':{n:A.sha(H/n) for n in ['analysis/no-call-results.json','analysis/no-call-predictions.csv','analysis/protocol-event-results.json','analysis/protocol-event-predictions.csv','inputs/record-only.jsonl']}})
    print('PASS',checks,'checks; boundary audit40rows',flush=True)

if __name__=='__main__':main()
