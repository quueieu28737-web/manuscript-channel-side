"""Recompute original pilot agreement independently; never recode the AI votes."""
from pathlib import Path
from collections import Counter
import csv,json,hashlib
import numpy as np
P=Path(__file__).resolve().parent;H=P.parent;O=P/'original'
read=lambda p:list(csv.DictReader(p.open(encoding='utf-8-sig',newline='')))
index=lambda rows:{r['setting_id']:r for r in rows}
t=index(read(O/'author-target-evidence.csv'));m=index(read(O/'author-evidence-matrix.csv'));a=index(read(O/'author-setting-availability.csv'))
c1={}
for sid,r in m.items():
    axis=r['transfer_axis'].lower()
    c1[sid]={'access_class':a[sid]['access_class'],'protection':'Y' if r['intervention']!='none' else 'N',
      'named_transfer':'Y' if any(w in axis for w in ('leave one','topology','held-out scaffold','proprietary scaffold')) else 'N',
      'open_world':'Y' if 'open world' in axis or 'open-world' in axis else 'N',
      'failure_status':t[sid]['failure_status'],'outcome_status':t[sid]['outcome_status']}
coders=[c1,index(read(O/'coder2_ai.csv')),index(read(O/'coder3_ai.csv'))]
ids=sorted(c1);assert all(set(c)==set(ids) for c in coders) and len(ids)==44
def cohen(x,y):
    x=list(x);y=list(y);n=len(x);cx=Counter(x);cy=Counter(y)
    observed=sum(i==j for i,j in zip(x,y))/n
    expected=sum(cx[k]*cy[k] for k in cx.keys()|cy.keys())/(n*n)
    return (observed-expected)/(1-expected) if expected<1 else float('nan')
def fleiss(a):
    n=len(a);cats=set(a.ravel());expected=sum((np.sum(a==k)/(3*n))**2 for k in cats)
    agree=np.mean([(r[0]==r[1])+(r[0]==r[2])+(r[1]==r[2]) for r in a.tolist()])/3
    return (agree-expected)/(1-expected) if expected<1 else float('nan')
def ci_boot(a,stat):
    rng=np.random.default_rng(0)
    out=[stat(a[rng.integers(0,len(a),len(a))]) for _ in range(2000)]
    return [round(float(x),3) for x in np.nanpercentile(out,[2.5,97.5])]
old=json.loads((O/'kappa-three-coders.json').read_text());result={}
for field in ('access_class','protection','named_transfer','open_world','failure_status','outcome_status'):
    arr=np.array([[c[sid][field] for c in coders] for sid in ids])
    pairs={f'C{x+1}-C{y+1}':round(cohen(arr[:,x],arr[:,y]),3) for x,y in [(0,1),(0,2),(1,2)]}
    f=round(float(fleiss(arr)),3);ci=ci_boot(arr,fleiss)
    agree=sum(len(set(r))==1 for r in arr.tolist())
    assert f==old[field]['fleiss_kappa'] and ci==old[field]['fleiss_ci95'],(field,f,ci)
    assert agree==old[field]['all_three_agree']
    assert all(v==old[field]['pairwise'][k]['kappa'] for k,v in pairs.items())
    result[field]={'pairwise':pairs,'fleiss':f,'conditional_row_bootstrap':ci,'all_agree':agree}
exp=json.loads((O/'kappa-sensitivity-unexposed34.json').read_text())
remaining=[s for s in ids if s not in exp['excluded_exposed_settings']];assert len(remaining)==34
sens={f:round(cohen([c1[s][f] for s in remaining],[coders[2][s][f] for s in remaining]),3) for f in ('failure_status','outcome_status')}
assert sens=={'failure_status':.785,'outcome_status':.433}
new=index(read(H/'field-map/target-evidence.csv'));ledger=read(P/'outcome-adjudication.csv')
disputed=set(old['outcome_status']['coder1_is_minority']);assert {r['setting_id'] for r in ledger}==disputed
changes=[s for s in ids if new[s]['outcome_status']!=t[s]['outcome_status']]
assert len(changes)==13 and set(changes)<=disputed
for s in ids:
    for f in t[s]:
        if s not in disputed or f not in ('outcome_status','execution_outcome','field_locator','missing_or_scope'):
            assert new[s][f]==t[s][f],(s,f)
assert sum(r['outcome_status']=='reported' for r in new.values())==15
assert sum(r['outcome_status']!='not_applicable' for r in new.values())==42
out={'status':'PASS','agreement':result,'unexposed_34':sens,'adjudicated_rows':15,'changed_statuses':13,
     'original_inputs_preserved':True,'scope':'Arithmetic of original dependent AI/author pilot; no human reliability or validity claim.'}
assert out == json.loads((P/'verification.json').read_text(encoding='utf8'))
print(json.dumps(out,indent=2))
