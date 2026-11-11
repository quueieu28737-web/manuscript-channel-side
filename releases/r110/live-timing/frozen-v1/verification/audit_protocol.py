"""Additional independent collection audit; no refitting or hypothesis changes."""
import collections,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
from common import H,load,save,sha,now,canonical
from collect import shadow_fixture
from environment import SERVICES,destination

def main(run):
    raw=H/'private-run'/run;start=load(raw/'started.json');assert (raw/'finished.json').exists()
    plan=load(H/'experiment/cohort-plan.json');units={u['task_id']:u for u in plan['units']}
    arms=['none'] if start['phase']=='none' else ['unmatched','gdm_live','concurrent','shadow']
    expected={(m,a,i) for m in plan['models'] for a in arms for i in units}
    actual=set();checks=0;draw_rows=[];shadow_counts=collections.Counter();models_calls=collections.Counter()
    pools=load(H/'pools/timing-pools.json') if start['phase']=='cover' else None
    for p in (raw/'episodes').glob('*/result.json'):
        r=load(p);out=p.parent;key=(r['model'],r['arm'],r['task_id']);assert key not in actual;actual.add(key)
        u=units[r['task_id']];job=load(out/'job.json');assert canonical(job['unit'])==canonical(u)
        assert r['split']==u['split'];checks+=2
        requests={load(x)['request_id']:(x,load(x)) for x in (out/'tools').glob('*/request.json')}
        assert len(requests)==len(r['wire_trace'])
        trace={c['request_id']:c for c in r['wire_trace']}
        if r['arm']=='shadow':
            su,sc=shadow_fixture(u);got=load(out/'shadow-unit.json')
            assert canonical(got)==canonical({'unit':su,'schedule':sc});checks+=1
            shadow_counts[r['model']+'/first' if sc['shadow_first'] else r['model']+'/second']+=1
            shadow_counts[r['model']+'/'+su['action']]+=1
            first=min(r['wire_trace'],key=lambda t:t['start_ns'])
            assert first['role']==('shadow' if sc['shadow_first'] else 'real');checks+=1
        for rid,(rp,req) in requests.items():
            terminal=load(rp.parent/'terminal.json');assert (rp.parent/'started.json').exists()
            assert destination(req['operation'])==req['service'];checks+=2
            if req['kind']=='cover':
                assert r['arm'] in ['unmatched','gdm_live','concurrent'] and req['role']=='real'
                sr=load(rp.parent/'server-receipt.json');assert canonical(sr['state_before'])==canonical(sr['state_after']);checks+=2
                d=next(x for x in u['decoys'] if x['index']==req['schedule']['index'])
                assert (req['operation'],req['order_id'])==(d['action'],d['order_id']);checks+=1
                if r['arm'] in ['gdm_live','concurrent']:
                    pl=pools['models'][r['model']];s=req['service'];dp=pl['duration_seconds'].get(s,[])
                    dp=dp if len(dp)>=20 else pl['all_duration_seconds']
                    gap=req['schedule']['target_gap_s'];duration=req['hold_s']
                    assert gap in pl['gap_seconds'] and duration in dp;checks+=2
                    anchor=trace[req['schedule']['anchor_request']]
                    assert req['schedule']['anchor_end_ns']==anchor['end_ns'];checks+=1
                    achieved=(terminal['record_start_ns']-anchor['end_ns'])/1e9
                    assert achieved+1e-3>=gap,(key,rid,gap,achieved);checks+=1
                    draw_rows.append({'model':r['model'],'arm':r['arm'],'task_id':r['task_id'],
                        'target_gap_s':gap,'anchor_gap_s':achieved,'target_duration_s':duration,
                        'actual_duration_s':(terminal['record_end_ns']-terminal['record_start_ns'])/1e9})
        for role in ['real','shadow'] if r['arm']=='shadow' else ['real']:
            chain_unit=load(out/'shadow-unit.json')['unit'] if role=='shadow' else u
            for rp in (out/'chains'/role/'model').glob('*/request.json'):
                mr=load(rp);mt=load(rp.parent/'terminal.json')
                assert mr['model']==r['model'] and mr['options']=={**plan['options'],'seed':chain_unit['seed']}
                assert mt['done'].get('done') is True;models_calls[r['model']]+=1;checks+=2
                assert mr['options']['num_ctx']==4096 and mr['options']['num_predict']==96
        # Unique wire accounting, including setup and teardown.
        wires=[load(x) for x in (out/'connections').glob('*.json')]
        assert len(wires)==7 and {w['service'] for w in wires}==set(SERVICES)
        complete=[load(raw/'wire'/f'{w["id"]}.json') for w in wires]
        assert sum(sum(w['bytes']) for w in complete)==r['transport_total_bytes'];checks+=2
    assert actual==expected,(len(actual),len(expected),list(expected-actual)[:3])
    assert not list(raw.rglob('unknown.json'))
    result={'status':'PASS','utc':now(),'run':run,'episodes':len(actual),'checks':checks,
            'model_requests':dict(models_calls),'shadow_sampling':dict(shadow_counts),'draw_rows':draw_rows,
            'scope':'Exact original fixture identity, fixed options, all expected terminal cells, isolated cover writes, train-pool membership, causal timing anchors and unique whole-connection bytes.'}
    dst=H/'verification'/f'{run}-protocol-audit.json';assert not dst.exists();save(dst,result)
    print(json.dumps({k:v for k,v in result.items() if k!='draw_rows'}))

if __name__=='__main__':main(sys.argv[1])
