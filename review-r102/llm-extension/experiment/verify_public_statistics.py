"""Recompute published test statistics from the synthetic review bundle."""
import csv, gzip, json, math, sys
from pathlib import Path
import numpy as np
from verify_analysis import exact, interval, resampling_positions

root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
def read(name):return json.loads((root/'analysis'/name).read_text(encoding='utf-8'))
pred=list(csv.DictReader((root/'analysis/predictions.csv').open(newline='',encoding='utf-8')))
metrics=list(csv.DictReader((root/'analysis/outcomes-costs.csv').open(newline='',encoding='utf-8')))
compact={}
with gzip.open(root/'data/episodes.jsonl.gz','rt',encoding='utf-8') as f:
    for line in f:
        r=json.loads(line)
        if r['split']!='test':continue
        compact[r['model'],r['arm'],r['task_id']]={
            'goal_success':int(r['goal_success']),'state_integrity':int(r['state_integrity']),
            'transport_total_bytes':r['transport_total_bytes'],'tool_cipher_bytes':r['tool_cipher_bytes'],
            'model_calls':r['model_steps'],'wall_seconds':r['wall_seconds'],
            'prompt_tokens':sum(x['prompt_eval_count'] for x in r['model_usage']),
            'output_tokens':sum(x['eval_count'] for x in r['model_usage']),
            'honest_calls':sum(x['kind']=='honest' for x in r['calls']),
            'cover_calls':sum(x['kind']=='cover' for x in r['calls'])}
assert len(compact)==len(pred)==1440
cells={}
for p in pred:cells.setdefault((p['model'],p['arm']),[]).append(p)
for ps in cells.values():ps.sort(key=lambda p:int(p['task_id']))
for s in read('recognition.json'):
    ps=cells[s['model'],s['arm']];draws=resampling_positions([int(p['y']) for p in ps])
    v=np.array([int(p[s['attack']]==p['y']) for p in ps])
    assert v.sum()==s['correct'] and abs(v.mean()-s['balanced_accuracy'])<1e-12
    assert np.allclose(interval(v,draws),s['conditional_ci'],rtol=0,atol=1e-12)
for m in metrics:
    ps=cells[m['model'],m['arm']];ep=m['endpoint'];v=[]
    for p in ps:
        ident=int(p['task_id']);r=compact[m['model'],m['arm'],ident]
        if ep in ['transport_byte_ratio','tool_byte_ratio']:
            key='transport_total_bytes' if ep=='transport_byte_ratio' else 'tool_cipher_bytes'
            v.append(r[key]/compact[m['model'],'none',ident][key])
        else:v.append(r[ep])
    draws=resampling_positions([int(p['y']) for p in ps])
    assert np.allclose([np.mean(v),np.median(v),np.quantile(v,.25),np.quantile(v,.75)],
                       [float(m[k]) for k in ['mean','median','q25','q75']],rtol=0,atol=1e-9)
    assert np.allclose(interval(v,draws),[float(m['conditional_ci_low']),float(m['conditional_ci_high'])],rtol=0,atol=1e-9)
comparisons=read('paired-comparisons.json')
for endpoint,family in comparisons.items():
    assert len(family)==12
    for c in family:
        ps=cells[c['model'],c['condition']];bs=cells[c['model'],c['reference']]
        assert [p['task_id'] for p in ps]==[p['task_id'] for p in bs]
        if endpoint=='privacy':v=np.array([int(p['selected']==p['y'])-int(b['selected']==b['y']) for p,b in zip(ps,bs)])
        else:v=np.array([int(p[endpoint])-int(b[endpoint]) for p,b in zip(ps,bs)])
        plus=int(sum(v==1));minus=int(sum(v==-1))
        assert plus==c['condition_only'] and minus==c['reference_only']
        assert math.isclose(exact(plus,minus),c['p_raw'],rel_tol=1e-12,abs_tol=1e-300)
        assert abs(100*v.mean()-c['difference_pp'])<1e-12
        draws=resampling_positions([int(p['y']) for p in ps])
        assert np.allclose(100*interval(v,draws),c['conditional_ci_pp'],rtol=0,atol=1e-10)
    previous=0.
    for i,c in enumerate(sorted(family,key=lambda c:c['p_raw'])):
        previous=max(previous,min(1.,c['p_raw']*(12-i)))
        assert math.isclose(previous,c['p_holm'],rel_tol=1e-12,abs_tol=1e-300)
print(json.dumps({'status':'PASS','held_out_rows':len(pred),'recognition_rows':72,
 'cost_rows':len(metrics),'paired_comparisons':36,
 'scope':'All conditional intervals, held-out cost summaries, exact discordant-pair tests and three separate 12-comparison Holm families. No fitting, new hypotheses or inference requests.'}))
