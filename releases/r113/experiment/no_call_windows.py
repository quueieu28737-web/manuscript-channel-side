"""Record-only reanalysis: associated episode connections, no supplied call windows.

Source records are immutable R110 observations. Ground-truth calls are never read
by extraction/fitting; they are reserved for a separately run boundary audit.
"""
import os
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['OPENBLAS_NUM_THREADS'] = '2'
import argparse, collections, csv, hashlib, json, math, sys, time
from pathlib import Path
import numpy as np
from scipy.stats import binomtest
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.mixture import GaussianMixture
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

H = Path(__file__).resolve().parents[1]
OLD = H.parent / 'r110-live-timing'
SERVICES = ['helpdesk', 'crm', 'policy', 'orders', 'payments', 'billing', 'shipping']
LABELS = ['refund', 'address_update', 'escalation', 'replacement', 'cancellation', 'receipt']
MODELS = ['qwen3:8b', 'llama3.1:8b']
ARMS = ['none', 'unmatched', 'gdm_live', 'concurrent', 'shadow']
DELTAS = [.005, .02, .05, .1, .25]
SEED = 111121


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def save(p, value):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def csvout(p, rows):
    with Path(p).open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def extract():
    target = H / 'inputs/record-only.jsonl'
    assert not target.exists(), 'Preserve previous extraction; investigate instead of overwriting.'
    manifest = {}; counts = collections.Counter(); records = 0
    with target.open('w', encoding='utf-8') as out:
        for run in ['formal-none-v1', 'formal-cover-v1']:
            for p in sorted((OLD / 'private-run' / run / 'episodes').glob('*/result.json')):
                # Only the declared population fields are taken from this file.
                r = load(p); manifest[str(p.relative_to(OLD))] = sha(p)
                events = []
                conns = sorted((p.parent / 'connections').glob('*.json'))
                assert len(conns) == 7
                seen = set()
                for c in conns:
                    snapshot = load(c)
                    final_wire = OLD / 'private-run' / run / 'wire' / c.name
                    w = load(final_wire); seen.add(w['service'])
                    assert w['id'] == snapshot['id'] and w['service'] == snapshot['service']
                    manifest[str(c.relative_to(OLD))] = sha(c)
                    manifest[str(final_wire.relative_to(OLD))] = sha(final_wire)
                    assert w['closed'] and w['trailing_bytes'] == [0, 0]
                    assert w['record_schema'] == ['outer_type', 'wire_length', 'completion_perf_ns', 'completion_epoch_ns']
                    for direction, sequence in enumerate(w['records']):
                        for outer, size, perf, epoch in sequence:
                            if outer == 23:
                                events.append([int(perf), SERVICES.index(w['service']), direction, int(size)])
                assert seen == set(SERVICES) and events
                events.sort()
                start = min(v[0] for v in events)
                # Entire connections, including initialization/closing records.
                obs = {'unit': r['task_id'], 'model': r['model'], 'arm': r['arm'],
                       'split': r['split'], 'label': LABELS.index(r['label']),
                       'records': [[(t-start)/1e9, s, d, n] for t,s,d,n in events]}
                out.write(json.dumps(obs, separators=(',', ':')) + '\n')
                counts[r['model'] + '/' + r['arm'] + '/' + r['split']] += 1
                records += len(events)
    assert sum(counts.values()) == 3000
    assert all(counts[m+'/'+a+'/'+s] == n for m in MODELS for a in ARMS
               for s,n in [('train',120),('validation',60),('test',120)])
    save(H / 'inputs/record-only-manifest.json', {
        'sha256': sha(target), 'source_files': manifest, 'episodes': 3000,
        'encrypted_records': records, 'connections': 21000, 'counts': dict(counts),
        'whitelist': ['relative record time', 'public destination class', 'direction', 'ciphertext record size'],
        'not_features': ['unit', 'model', 'arm', 'split', 'label'],
        'scope': 'Associated whole-episode connections retained; no call/operation/role/payload/HTTP stream ground truth in observations.'})
    print('Extracted', 3000, 'episodes;', records, 'encrypted records', flush=True)


def bursts(records, delta):
    result = []
    for service in range(7):
        stream = [r for r in records if r[1] == service]
        group = []
        for rec in stream:
            if group and rec[0] - group[-1][0] > delta:
                result.append(pack(group)); group = []
            group.append(rec)
        if group: result.append(pack(group))
    return sorted(result, key=lambda r:(r[0], r[2], r[1]))


def pack(group):
    return [group[0][0], group[-1][0], group[0][1],
            sum(v[3] for v in group if v[2] == 0),
            sum(v[3] for v in group if v[2] == 1), len(group)]


def vector(events, timing):
    # Seven destination summaries plus first four and last sixteen events.
    dest_width = 8 if timing else 5
    width = 11 if timing else 9
    x = np.zeros(7 * dest_width + 20 * width + 4)
    for j in range(7):
        z = [v for v in events if v[2] == j]
        if not z: continue
        u = [len(z), sum(v[3] for v in z), sum(v[4] for v in z),
             sum(v[5] for v in z), max(v[3]+v[4] for v in z)]
        if timing: u += [z[0][0], z[-1][1], sum(v[1]-v[0] for v in z)]
        x[j*dest_width:(j+1)*dest_width] = np.log1p(u)
    ids = list(range(min(4,len(events))))
    tail = list(range(max(4,len(events)-16),len(events)))
    # Distinct first/tail slots; no label-dependent truncation.
    for slot,i in [(k,i) for k,i in enumerate(ids)] + [(4+k,i) for k,i in enumerate(tail)]:
        v = events[i]; b = 7 * dest_width + slot * width
        x[b+v[2]] = 1; x[b+7:b+9] = np.log1p(v[3:5])
        if timing:
            gap = max(0., v[0]-events[i-1][1]) if i else 0.
            x[b+9:b+11] = np.log1p([max(0.,v[1]-v[0]),gap])
    x[-4:] = np.log1p([len(events),sum(v[3] for v in events),sum(v[4] for v in events),sum(v[5] for v in events)])
    return x


def make_estimator(kind):
    if kind == 'LR':
        return make_pipeline(StandardScaler(), LogisticRegression(C=1,max_iter=3000,random_state=SEED))
    return RandomForestClassifier(n_estimators=300,n_jobs=2,random_state=SEED)


def fit_gmm(event_lists):
    gaps = [max(1e-4,z[i][0]-z[i-1][1]) for z in event_lists for i in range(1,len(z))]
    g = GaussianMixture(2,random_state=SEED,n_init=5).fit(np.log10(gaps).reshape(-1,1))
    lo,hi = sorted(g.means_.ravel()); small = int(np.argmin(g.means_))
    for _ in range(80):
        mid = (lo+hi)/2
        if g.predict_proba([[mid]])[0,small] > .5: lo = mid
        else: hi = mid
    return 10**((lo+hi)/2)


def strip(events, threshold):
    return [v for i,v in enumerate(events)
            if i == 0 or max(0.,v[0]-events[i-1][1]) >= threshold]


def main():
    assert load(H/'experiment/freeze.json')['files']['experiment/no_call_windows.py'] == sha(__file__)
    assert not (H/'analysis/no-call-results.json').exists()
    if not (H/'inputs/record-only.jsonl').exists(): extract()
    manifest = load(H/'inputs/record-only-manifest.json')
    assert manifest['sha256'] == sha(H/'inputs/record-only.jsonl')
    rows = [json.loads(s) for s in (H/'inputs/record-only.jsonl').read_text().splitlines()]
    all_attacks=[]; predictions=[]; selections=[]; primary=[]; timings=[]
    for model in MODELS:
        data = {a:{s:sorted([r for r in rows if r['model']==model and r['arm']==a and r['split']==s],
                           key=lambda r:r['unit']) for s in ['train','validation','test']} for a in ARMS}
        y = {s:np.array([r['label'] for r in data['none'][s]]) for s in data['none']}
        assert all([r['unit'] for r in data[a][s]] == [r['unit'] for r in data['none'][s]] for a in ARMS for s in y)
        event_data={a:{s:{str(d):[bursts(r['records'],d) for r in data[a][s]] for d in DELTAS}
                       for s in y} for a in ARMS}
        clean={}
        for d in DELTAS:
            for timing in [False,True]:
                for kind in ['LR','RF']:
                    est=make_estimator(kind)
                    est.fit(np.stack([vector(z,timing) for z in event_data['none']['train'][str(d)]]),y['train'])
                    clean[d,timing,kind]=est
        for arm in ARMS:
            start=time.perf_counter(); val={}; test_matrices={}; estimators={}; thresholds={}
            for d in DELTAS:
                z = {s:event_data[arm][s][str(d)] for s in y}
                thresholds[str(d)] = fit_gmm(z['train'])
                for timing in [False,True]:
                    vv='time' if timing else 'size'
                    X={s:np.stack([vector(v,timing) for v in z[s]]) for s in y}
                    SX={s:np.stack([vector(strip(v,thresholds[str(d)]),timing) for v in z[s]]) for s in ['validation','test']}
                    for kind in ['LR','RF']:
                        name=f'burst_{d:g}_{vv}_{kind}'
                        est=make_estimator(kind);est.fit(X['train'],y['train'])
                        val[name]=est.predict(X['validation']);test_matrices[name]=X['test'];estimators[name]=est
                        name=f'strip_{d:g}_{vv}_{kind}'
                        est=clean[d,timing,kind]
                        val[name]=est.predict(SX['validation']);test_matrices[name]=SX['test'];estimators[name]=est
            # Raw-record baseline bypasses any event segmentation.
            raw={s:[[ [v[0],v[0],v[1],v[3] if v[2]==0 else 0,v[3] if v[2]==1 else 0,1]
                       for v in r['records']] for r in data[arm][s]] for s in y}
            for timing in [False,True]:
                X={s:np.stack([vector(z,timing) for z in raw[s]]) for s in y}
                for kind in ['LR','RF']:
                    name=f'raw_{"time" if timing else "size"}_{kind}'
                    est=make_estimator(kind);est.fit(X['train'],y['train'])
                    val[name]=est.predict(X['validation']);test_matrices[name]=X['test'];estimators[name]=est
            names=list(val);baseline=[n for n in names if not n.startswith('strip_')];removed=[n for n in names if n.startswith('strip_')]
            score={n:int(sum(v==y['validation'])) for n,v in val.items()}
            pick=lambda ns:max(ns,key=lambda n:(score[n],-names.index(n)))
            choice={'model':model,'arm':arm,'baseline':pick(baseline),'removal':pick(removed),'suite':pick(names),
                    'validation_correct':score,'thresholds':thresholds}
            # Commit validation selections before predicting this cell's test data.
            save(H/f'analysis/selection-{model.replace(":","-")}-{arm}.json',choice)
            pp={n:estimators[n].predict(test_matrices[n]) for n in names}
            selections.append(choice)
            boot=np.random.default_rng(SEED).integers(0,120,size=(10000,120))
            for n,pred in pp.items():
                correct=pred==y['test']
                all_attacks.append({'model':model,'arm':arm,'attack':n,'n':120,'validation_correct':score[n],
                                   'correct':int(sum(correct)),'conditional_ci':np.quantile(correct[boot].mean(axis=1),[.025,.975]).tolist()})
                for unit,prediction,truth in zip(data[arm]['test'],pred,y['test']):
                    predictions.append({'model':model,'arm':arm,'unit':unit['unit'],'attack':n,'prediction':int(prediction),'truth':int(truth)})
            if arm=='unmatched':
                aa=pp[choice['removal']]==y['test'];bb=pp[choice['baseline']]==y['test']
                plus=int(sum(aa & ~bb));minus=int(sum(bb & ~aa));diff=aa.astype(int)-bb.astype(int)
                primary.append({'model':model,'arm':arm,'removal_attack':choice['removal'],'baseline_attack':choice['baseline'],
                                'removal_correct':int(aa.sum()),'baseline_correct':int(bb.sum()),'plus':plus,'minus':minus,
                                'difference_pp':float(diff.mean()*100),'conditional_ci_pp':np.quantile(diff[boot].mean(axis=1)*100,[.025,.975]).tolist(),
                                'p_raw':float(binomtest(plus,plus+minus,.5).pvalue) if plus+minus else 1.})
            timings.append({'model':model,'arm':arm,'fit_predict_s':time.perf_counter()-start})
            print(model,arm,'baseline',sum(pp[choice['baseline']]==y['test']), 'removal',sum(pp[choice['removal']]==y['test']),
                  'suite',sum(pp[choice['suite']]==y['test']),'max',max(sum(v==y['test']) for v in pp.values()),flush=True)
    last=0
    for rank,i in enumerate(sorted(range(2),key=lambda i:primary[i]['p_raw'])):
        last=max(last,min(1.,primary[i]['p_raw']*(2-rank)));primary[i]['p_holm']=last
    save(H/'analysis/no-call-results.json',{'scope':'Associated episode connections supplied; no call boundaries, operation or cover roles. Retrospective reused-workload analysis.',
                                          'input_sha256':manifest['sha256'],'attacks':all_attacks,'selections':selections,
                                          'primary_immediate_removal':primary,'timings':timings})
    csvout(H/'analysis/no-call-predictions.csv',predictions)


if __name__=='__main__': main()
