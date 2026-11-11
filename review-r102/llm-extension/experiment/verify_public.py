"""Offline audit of the exported synthetic dataset, without model inference."""
import csv, gzip, hashlib, json, sys
from pathlib import Path
import numpy as np
from verify_collection import transition

ROOT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]

def canonical_bytes(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'),sort_keys=True).encode()+b'\n'
def file_hash(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))

manifest=read(ROOT/'manifest.json')
for name,entry in manifest['files'].items():
    p=(ROOT/name).resolve();assert p.is_relative_to(ROOT)
    assert file_hash(p)==entry['sha256'] and p.stat().st_size==entry['bytes'],name
planned_units={t['task_id']:t for t in read(ROOT/'experiment/cohort-plan.json')['units']}
assert len(planned_units)==300
services=['helpdesk','crm','policy','orders','payments','billing','shipping']
labels=['refund','address_update','escalation','replacement','cancellation','receipt']
f=np.load(ROOT/'analysis/features.npz',allow_pickle=False)
lookup={(str(m),str(a),int(t)):i for i,(m,a,t) in enumerate(zip(f['model'],f['arm'],f['task']))}
assert len(lookup)==3600
data={};fixtures={};requests=0;tools=0
with gzip.open(ROOT/'data/episodes.jsonl.gz','rt',encoding='utf-8') as z:
    for line in z:
        r=json.loads(line);key=(r['model'],r['arm'],r['task_id']);assert key not in data;data[key]=r
        assert r['unit']==planned_units[r['task_id']]
        assert r['unit']['action']==r['label'] and r['unit']['task_id']==r['task_id']
        common=r['model'],r['task_id'];fixture_hash=hashlib.sha256(canonical_bytes(r['unit'])).hexdigest()
        if common in fixtures:assert fixtures[common]==fixture_hash
        fixtures[common]=fixture_hash
        live=json.loads(json.dumps(r['unit']['fixture']));shadow=json.loads(json.dumps(live));checked=set();intended=False
        for call in r['calls']:
            assert call['state_before']==live and call['shadow_before']==shadow
            a=call['action'];oid=call['order_id']
            if call['kind']=='honest':
                if a in r['unit']['checks']:checked.add(a)
                elif a!='get_ticket':
                    assert set(r['unit']['checks'])<=checked
                    ok=transition(live,a,oid);assert ok==call['ok']
                    intended|=a==r['label'] and oid==r['unit']['target'] and ok
            elif r['arm'] in ['isolated','isolated_visible']:assert transition(shadow,a,oid)==call['ok']
            elif r['arm']=='live_write':assert transition(live,a,oid)==call['ok']
            else:assert r['arm'] in ['transport_drop','read']
            assert call['state_after']==live and call['shadow_after']==shadow
        ref=json.loads(json.dumps(r['unit']['fixture']));assert transition(ref,r['label'],r['unit']['target'])
        goal=intended and set(r['unit']['checks'])<=checked and live['orders'][r['unit']['target']]==ref['orders'][r['unit']['target']]
        if r['label']=='address_update':goal=goal and live['customer']['address']=='new' and all(v['address']=='new' for v in live['orders'].values() if v['status']=='pending')
        if r['label']=='escalation':goal=goal and live['customer']['escalated']
        if r['label']=='replacement':goal=goal and any(x==['replacement',r['unit']['target'],'home'] for x in live['ledger'])
        assert bool(goal)==r['goal_success'] and (live==ref)==r['state_integrity']
        assert live==r['state_after'] and ref==r['reference_state']
        seq=r['wire_trace'];x=[]
        for j in range(16):x.extend([int(j<len(seq) and seq[j]['service']==s) for s in services])
        x.extend([sum(a['service']==s for a in seq) for s in services])
        for j in range(16):x.extend(seq[j]['bytes'] if j<len(seq) else [0,0])
        x.extend([len(seq),sum(sum(a['bytes']) for a in seq)])
        idx=lookup[key];assert np.array_equal(np.asarray(x,float),f['X'][idx]);assert labels[f['y'][idx]]==r['label']
        for q in r['model_decisions']:
            assert hashlib.sha256(canonical_bytes(q['request'])).hexdigest()==q['request_sha256']
            assert hashlib.sha256(canonical_bytes(q['terminal'])).hexdigest()==q['terminal_sha256']
            assert q['terminal']['done']['done'] and q['terminal']['text']==q['text'];requests+=1
        conns={c['id']:c for c in r['connections']}
        for q in r['tool_receipts']:
            assert hashlib.sha256(canonical_bytes(q['terminal'])).hexdigest()==q['terminal_sha256']
            w=conns[q['wire_id']]
            for side in range(2):
                assert q['after']['bytes'][side]-q['before']['bytes'][side]==q['cipher_bytes'][side]
                for edge in ['before','after']:
                    count=q[edge]['records'][side]
                    assert sum(t[1] for t in w['records'][side][:count])==q[edge]['bytes'][side]
            tools+=1
        assert sum(sum(c['bytes']) for c in conns.values())==r['transport_total_bytes']
assert len(data)==3600 and len(fixtures)==600
pred=list(csv.DictReader((ROOT/'analysis/predictions.csv').open(newline='',encoding='utf-8')))
scores=read(ROOT/'analysis/recognition.json')
for s in scores:
    ps=[p for p in pred if(p['model'],p['arm'])==(s['model'],s['arm'])]
    assert len(ps)==120
    cm=[[0]*6 for _ in range(6)]
    for p in ps:
        cm[int(p['y'])][int(p[s['attack']])]+=1
        r=data[p['model'],p['arm'],int(p['task_id'])]
        assert r['split']=='test'
        for name in ['goal_success','state_integrity']:assert int(p[name])==int(r[name])
    assert cm==s['confusion'] and sum(cm[i][i] for i in range(6))==s['correct']
print(json.dumps({'status':'PASS','episodes':len(data),'unique_paired_fixtures':len(planned_units),'held_out_rows':len(pred),'model_request_receipts':requests,
                  'tool_receipts':tools,'scope':'Manifest, paired fixtures, independent business-state replay, public wire-derived features, request/response hashes, tool byte accounting and held-out confusion matrices. No network requests or inference.'}))
