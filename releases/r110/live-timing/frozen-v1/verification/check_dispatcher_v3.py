"""Exercise timing-anchor and persistent-dispatch invariants on dev data only."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
from common import H,load,save,sha,now

def main():
    raw=H/'private-run/development-cover-v3';assert (raw/'finished.json').exists()
    verified=load(H/'verification/development-cover-v3-verified.json');assert verified['status']=='PASS'
    checks=0;second_at_same_trigger=0;cover_n=0
    for p in (raw/'episodes').glob('*/result.json'):
        r=load(p);tr=r['wire_trace'];byid={v['request_id']:v for v in tr};covers=[];counts={}
        for v in tr:
            if v['kind']!='cover':continue
            req=load(p.parent/v['folder']/'request.json');sc=req['schedule']
            anchor=byid[sc['anchor_request']]
            assert anchor['end_ns']==sc['anchor_end_ns']
            assert (v['start_ns']-anchor['end_ns'])/1e9+.001>=sc['target_gap_s']
            counts[sc['trigger_request']]=counts.get(sc['trigger_request'],0)+1
            if counts[sc['trigger_request']]>1:
                second_at_same_trigger+=1
                assert sc['anchor_request']!=sc['trigger_request'],'second cover retained the stale trigger anchor'
            covers.append(v);checks+=3;cover_n+=1
        assert all(a['end_ns']<=b['start_ns'] for a,b in zip(covers,covers[1:]));checks+=1
    assert verified['episodes']==4 and cover_n==8 and second_at_same_trigger==4
    save(H/'verification/cover-v3-readiness.json',{'status':'PASS','utc':now(),'development_episodes':4,'checks':checks,
        'second_covers_with_updated_anchor':second_at_same_trigger,'cover_calls':cover_n,
        'collector_sha256':sha(H/'experiment/collect_cover_v3.py'),
        'capture_audit_sha256':sha(H/'verification/development-cover-v3-verified.json'),
        'scope':'Two models, one original two-decoy development fixture, sequential and persistent concurrent matching. No formal fixture or formal GPU overlap.'})
    print('COVER_V3_READINESS_PASS')

if __name__=='__main__':main()
