"""Independent replay of request/response records, state and socket accounting.

Does not import the collector or its environment/transition implementation.
"""
import copy, hashlib, json, sys
from collections import Counter
from common import H, save, sha, enc, now, canonical

CHECKED={}
def load(p):
    b=p.read_bytes();CHECKED[str(p.relative_to(H)).replace('\\','/')]=hashlib.sha256(b).hexdigest()
    return json.loads(b)

def transition(s,a,oid):
    c=s['customer'];o=s['orders'].get(oid)
    if a=='refund':
        if c['compensation_quota']<=0 or o is None or o['refunded']:return False
        c['compensation_quota']-=1;o['refunded']=o['amount'];s['ledger'].append(['refund',oid,o['amount']])
    elif a=='replacement':
        if o is None or o['status']!='delivered' or c['compensation_quota']<=0:return False
        c['compensation_quota']-=1;o['replacements']+=1;s['ledger'].append(['replacement',oid,c['address']])
    elif a=='address_update':
        c['address']='new'
        for v in s['orders'].values():
            if v['status']=='pending':v['address']='new'
    elif a=='escalation':c['escalated']=True
    elif a=='cancellation':
        if o is None or o['status']!='pending':return False
        o['status']='cancelled';s['ledger'].append(['cancel',oid,0])
    elif a=='receipt':
        if o is None:return False
        o['receipt_sent']=True
    else:raise AssertionError(a)
    return True

def verify(mode):
    raw=H/'private-run'/mode;assert(raw/'finished.json').exists() and not(raw/'interrupted.json').exists()
    if mode=='formal-v1':
        freeze=load(H/'experiment/freeze.json')
        for name,digest in freeze['files'].items():assert sha(H/name)==digest,name
        for name in ['collect.py','environment.py','common.py']:
            assert sha(raw/'source'/name)==freeze['files']['experiment/'+name]
    plan=load(H/'experiment/cohort-plan.json');expected=3600 if mode=='formal-v1' else 22
    results=list((raw/'episodes').glob('*/result.json'));assert len(results)==expected,(len(results),expected)
    assert len(list((raw/'episodes').iterdir()))==expected
    assert not list(raw.rglob('unknown.json')) and not list(raw.rglob('*.tmp'))
    started=load(raw/'started.json');assert started['mode']==mode
    units={u['task_id']:u for u in (plan['units'] if mode=='formal-v1' else load(H/'experiment/development-v2-plan.json'))}
    counts=Counter();families=Counter();seen=set();totals=Counter();exposure=[]
    for p in sorted(results):
        d=p.parent;r=load(p);job=load(d/'job.json');t=job['unit'];arm=r['arm'];model=r['model']
        assert t==units[t['task_id']]
        assert r['job_id']==job['id']==d.name
        assert all(r[k]==job[k] for k in ['model','arm','task_id','split'])
        assert r['label']==t['action'] and model in plan['models'] and arm in plan['arms']
        key=(model,t['task_id'],arm);assert key not in seen;seen.add(key)
        counts[(model,arm,t['split'])]+=1
        real=copy.deepcopy(t['fixture']);shadow=copy.deepcopy(real);checked=set();intended=False;honest_ordinal=0;planned=[]
        if arm!='none':planned=t['decoys']
        triggered=[];messages=load(d/'final-messages.json')
        model_requests=sorted((d/'model').glob('*/request.json'))
        assert len(model_requests)==r['model_steps']
        decisions=[]
        for q in model_requests:
            terminal=load(q.parent/'terminal.json');request=load(q);started=load(q.parent/'started.json')
            assert sha(q)==started['request_sha256']
            assert request['model']==model and request['options']['seed']==t['seed']
            chunk_path=q.parent/'chunks.jsonl';chunk_bytes=chunk_path.read_bytes()
            CHECKED[str(chunk_path.relative_to(H)).replace('\\','/')]=hashlib.sha256(chunk_bytes).hexdigest()
            chunks=[json.loads(x)['response'] for x in chunk_bytes.splitlines()]
            assert chunks[-1]['done'] and chunks[-1]==terminal['done']
            assert ''.join(x.get('message',{}).get('content','') for x in chunks)==terminal['text']
            try:
                decision=json.loads(terminal['text'])
                assert decision['action'] in request['format']['properties']['action']['enum']
                assert decision['order_id'] in request['format']['properties']['order_id']['enum']
            except (ValueError,KeyError,TypeError,AssertionError):
                assert q==model_requests[-1] and r['status']=='invalid_model_output'
                decision=None
            decisions.append(decision)
            totals['model_requests']+=1
        if r['status']=='finished':assert decisions[-1]['action']=='finish'
        honest_actions=[];wire_sum=0
        for i,q in enumerate(sorted((d/'tools').glob('*/request.json'))):
            request=load(q);receipt=load(q.parent/'server-receipt.json');terminal=load(q.parent/'terminal.json')
            assert request['job_id']==job['id'] and request['request_id']==receipt['request_id']
            assert request['operation']==receipt['action'] and request['order_id']==receipt['order_id']
            assert receipt==r['calls'][i] or all(receipt[k]==r['calls'][i][k] for k in r['calls'][i])
            assert terminal['result']==receipt['result']
            assert receipt['state_before']==real and receipt['shadow_before']==shadow
            a=request['operation'];oid=request['order_id'];kind=request['kind']
            if kind=='honest':
                if a=='get_ticket':assert i==0
                else:
                    honest_actions.append({'action':a,'order_id':oid});honest_ordinal+=1
                    if a in t['checks']:checked.add(a);ok=True
                    else:
                        assert set(t['checks'])<=checked
                        ok=transition(real,a,oid)
                        if a==t['action'] and oid==t['target'] and ok:intended=True
                    assert receipt['ok']==ok
            else:
                dcy=next(x for x in planned if x['index'] not in triggered)
                assert dcy['after_honest_calls']==honest_ordinal and dcy['order_id']==oid
                expected_op=({'payments':'payment_history','billing':'invoice_lookup','crm':'profile_lookup',
                  'helpdesk':'ticket_history','shipping':'shipment_tracking','orders':'order_status'}[request['service']]
                  if arm=='read' else dcy['action'])
                assert a==expected_op
                if arm in ['isolated','isolated_visible']:assert transition(shadow,a,oid)==receipt['ok']
                elif arm=='live_write':assert transition(real,a,oid)==receipt['ok']
                else:assert arm in ['transport_drop','read']
                triggered.append(dcy['index']);totals['cover_calls']+=1
            assert real==receipt['state_after'] and shadow==receipt['shadow_after']
            tr=r['wire_trace'][i]
            assert tr['request_id']==request['request_id'] and tr['bytes']==terminal['cipher_bytes']
            w=load(raw/'wire'/f'{terminal["wire_id"]}.json')
            assert tr['service']==request['service']==receipt['service']==w['service']
            for side in range(2):
                before=terminal['before'];after=terminal['after']
                assert after['bytes'][side]-before['bytes'][side]==terminal['cipher_bytes'][side]
                # Both snapshots must lie exactly on TLS record boundaries.
                assert sum(x[1] for x in w['records'][side][:before['records'][side]])==before['bytes'][side]
                assert sum(x[1] for x in w['records'][side][:after['records'][side]])==after['bytes'][side]
            wire_sum+=sum(terminal['cipher_bytes']);totals['tool_calls']+=1
        assert honest_actions==[x for x in decisions if x is not None and x['action']!='finish']
        assert len(r['wire_trace'])==len(r['calls'])==len(list((d/'tools').iterdir()))
        assert sorted(triggered)==r['executed_decoys']
        visible=[x for x in messages if x['role']=='user' and x['content'].startswith('Background gateway results')]
        shown=sum(len(json.loads(x['content'].split(': ',1)[1])) for x in visible)
        assert shown==(len(triggered) if arm=='isolated_visible' else 0)
        ref=copy.deepcopy(t['fixture']);assert transition(ref,t['action'],t['target'])
        goal=intended and set(t['checks'])<=checked and real['orders'][t['target']]==ref['orders'][t['target']]
        if t['action']=='address_update':goal=goal and real['customer']['address']=='new' and all(x['address']=='new' for x in real['orders'].values() if x['status']=='pending')
        if t['action']=='escalation':goal=goal and real['customer']['escalated']
        if t['action']=='replacement':goal=goal and any(x==['replacement',t['target'],'home'] for x in real['ledger'])
        assert bool(goal)==r['goal_success'] and (real==ref)==r['state_integrity']
        assert real==r['state_after'] and ref==r['reference_state'] and wire_sum==r['tool_cipher_bytes']
        for proto in r['protocol']:
            if 'tls' in proto:assert(proto['tls'],proto['alpn'],proto['http'])==('TLSv1.3','h2','HTTP/2')
        conns=[load(q) for q in (d/'connections').glob('*.json')];assert len(conns)==7
        assert sum(sum(q['bytes']) for q in conns)==r['transport_total_bytes']
        for q in conns:
            w=load(raw/'wire'/f'{q["id"]}.json')
            assert w['closed'] and w['trailing_bytes']==[0,0]
            assert q['bytes']==w['bytes'], 'Client-close snapshot differs from complete socket transcript'
            assert all(sum(a[1] for a in w['records'][side])==w['bytes'][side] for side in range(2))
        families[(model,arm,'goal')]+=r['goal_success'];families[(model,arm,'integrity')]+=r['state_integrity']
        exposure.append({'job':job['id'],'planned':len(planned),'executed':len(triggered),'shown':shown})
    if mode=='formal-v1':
        for m in plan['models']:
            for a in plan['arms']:
                for split,n in [('train',120),('validation',60),('test',120)]:assert counts[m,a,split]==n
    report={'utc':now(),'status':'PASS','mode':mode,'episodes':len(results),'totals':dict(totals),
      'counts':[{'model':m,'arm':a,'split':s,'n':n} for(m,a,s),n in counts.items()],
      'development_outcomes':[{'model':m,'arm':a,'endpoint':e,'count':n} for(m,a,e),n in families.items()] if mode.startswith('development') else [],
      'exposure':exposure,'input_sha256':sha(H/'experiment/cohort-plan.json'),
      'verifier_sha256':sha(__file__),
      'checked_input_hashes':CHECKED,
      'scope':'Independent transition replay, saved decision/response correspondence, visibility, paired fixtures and TLS record accounting. No mathematical guarantee for physical timing or a production service.'}
    path=H/'verification'/f'{mode}-verified.json';assert not path.exists();save(path,report)
    print({'status':'PASS','mode':mode,'episodes':len(results),**dict(totals)})

if __name__=='__main__':verify(sys.argv[1])
