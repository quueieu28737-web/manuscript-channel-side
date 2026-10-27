"""Validate published aggregate outcomes and their stated evidence scope."""
from collections import Counter
from pathlib import Path
import hashlib, json

M=Path(__file__).resolve().parents[1]
P=M.parent
load=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
d=load(M/'data/r40-wra-glm-summary.json')
assert (d['topics'],d['decoys_per_topic'],d['search_queries'])==(20,5,120)
assert d['new_model_requests_this_revision']==0 and not d['adaptation_gain_estimated']
rounds=[]
for v,clean,defended,missing in zip(d['rounds'],(19,18),(17,15),({'001-defended','010-defended'},{'010-defended','018-defended'})):
    rows=v['rows'];assert len(rows)==40 and len({r['id'] for r in rows})==40
    assert Counter(r['condition'] for r in rows)=={'clean':20,'defended':20}
    assert Counter(r['status'] for r in rows)=={'completed':38,'protocol_error':2}
    assert {r['id'] for r in rows if r['status']!='completed'}==missing
    for r in rows:
        assert r['returned_model']=='glm-5.3-flash'
        if r['status']=='completed':
            assert isinstance(r['guess'],int) and 1<=r['guess']<=20
            assert r['finish_reason']!='length'
        else:
            assert r['guess'] is None and r['finish_reason']=='length'
            assert r['usage']['completion_tokens']==v['max_tokens']
        assert all(len(r[k])==64 for k in ('request_sha256','result_sha256'))
    correct={c:sum(r['status']=='completed' and r['guess']==r['topic'] for r in rows if r['condition']==c) for c in ('clean','defended')}
    assert correct=={'clean':clean,'defended':defended}
    rounds.append({'budget':v['max_tokens'],'correct':correct,'valid':{'clean':20,'defended':18},'failures':2})

sources=d['transport_source_sha256']
has_transport=(P/'experiments/revision-m1-m8/m5_e3_tls_adaptive.json').exists()
if has_transport:
    for rel,h in sources.items():assert sha(P/rel)==h,rel
    buffered=load(P/'experiments/revision-m1-m8/m5_e3_tls_adaptive.json')
    b=next(r for r in buffered if r['policy_code']=='bucket_1024')
    assert b['clean_D0_acc']==0.5 and abs(b['adapted_D2_k12_pairs_acc']-17/24)<1e-12
    assert b['paired_gain_ci95']==[2/24,8/24]
    streaming=load(P/'experiments/sp2027-r2/e5_streaming_results.json')
    for policy,adapted in [('batch8_const',1.0),('tok_const_cap',0.5)]:
        s=next(r for r in streaming if r['tls']=='1.3' and r['target']=='T1' and r['policy']==policy)
        assert s['binary_accuracy']['D0_total_threshold'][0]==0.5
        assert s['best_D2_binary_accuracy']==adapted
section=(M/'sections/77-attacker-boundary.tex').read_text(encoding='utf8')
assert all(x in section for x in ('19/20','17/18','18/20','15/18','85--95','75--85','not an adaptation gain'))
assert '50.0\\% versus 100.0\\%' in (M/'sections/11-discussion.tex').read_text(encoding='utf8')
print(json.dumps({'status':'R40_AGGREGATES_AND_CLAIM_SCOPE_PASS','rounds':rounds,
                  'matched_transport_source_check':has_transport,'new_model_requests':0,
                  'limitation':'Aggregate checks do not independently attest original search execution or online WRA efficacy.'}))
