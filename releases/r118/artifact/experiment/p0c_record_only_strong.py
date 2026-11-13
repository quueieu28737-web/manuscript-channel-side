"""P0-C: Context removal and joint decoding on inferred events (no call windows).

Exploratory, post-hoc. The original record-only suite (S3) only removed short-gap
events with a two-component mixture. This script adds the two stronger attack
families of the call-window study to the record-only view:

  ctx_strip  a per-event cover detector (destination, position, size, timing
             context) removes flagged events; a no-cover classifier decodes the rest
  joint      enumerate removal of 0-2 of the top-K detector candidates and decode
             the task jointly (MAP with lambda grid, or marginal), as in analyze.py

Attacker inputs per episode: relative TLS-record completion time, destination,
direction and ciphertext record length on all seven associated connections,
including setup/teardown. Episode association remains supplied (as in S3).
Private call windows label TRAIN/VALIDATION events for detector fitting and
threshold selection. TEST windows are accessed only after all task predictions
are saved and sealed. Final attack selection uses validation task accuracy.

Segmentations: the five idle-gap grids of S3 and the protocol-aware eventizer.
Selection uses validation task accuracy only; test is scored once.
Tests: selected strong attack vs selected refitted baseline, exact McNemar,
Holm across the 8 cover cells (2 models x 4 cover arms).
"""
import argparse, hashlib, importlib, itertools, json, math, sys
from pathlib import Path
import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score
from common_local import (ARM_NAMES, ARMS, LABELS, MODELS, RUNS, check_frozen, holm, load, mcnemar, sha,
                          now, save, write_csv)

SERVICES = ['helpdesk', 'crm', 'policy', 'orders', 'payments', 'billing', 'shipping']
K = 10
PRIOR = [.02, .49, .49]
DEFAULT_RO = Path(__file__).resolve().parents[2] / 'releases/r116/artifact/record-only/experiment'
PREDICTIONS_SEALED = False


def import_record_only(path):
    sys.path.insert(0, str(path))
    ro = importlib.import_module('no_call_windows')
    pe = importlib.import_module('protocol_record_events')
    return ro, pe


def extract(live_dir, cache):
    """Whitelisted observations; separate source handles never enter features."""
    assert not cache.exists(), 'Preserve existing extraction; use a reviewed new run'
    rows, sources = [], {}
    for run in RUNS:
        for p in sorted((live_dir / 'private-run' / run / 'episodes').glob('*/result.json')):
            r = load(p); recs = []
            conns=sorted((p.parent / 'connections').glob('*.json'))
            assert len(conns)==7
            for c in conns:
                w = load(live_dir / 'private-run' / run / 'wire' / c.name)
                snap=load(c)
                assert w['id']==snap['id'] and w['service']==snap['service']
                assert w['closed'] and w['trailing_bytes']==[0,0]
                for direction, seq in enumerate(w['records']):
                    for outer, size, perf, _ in seq:
                        if outer == 23:
                            recs.append([int(perf), SERVICES.index(w['service']), direction, int(size)])
            recs.sort(); t0 = recs[0][0]
            sources[r['model'],r['arm'],r['task_id']]=(p,t0)
            rows.append({'unit': r['task_id'], 'model': r['model'], 'arm': r['arm'], 'split': r['split'],
                         'label': LABELS.index(r['label']),
                         'records': [[(t - t0) / 1e9, s, d, n] for t, s, d, n in recs]})
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text('\n'.join(json.dumps(x, separators=(',', ':')) for x in rows) + '\n', encoding='utf-8')
    return rows, sources


def call_truth(row, sources):
    if row['split']=='test' and not PREDICTIONS_SEALED:
        raise RuntimeError('TEST call truth is forbidden before prediction sealing')
    path,t0=sources[row['model'],row['arm'],row['unit']]
    return [[(c['start_ns']-t0)/1e9,(c['end_ns']-t0)/1e9,SERVICES.index(c['service']),
             int(c['kind']=='cover' or c['role']=='shadow')] for c in load(path)['wire_trace']]


def boundary_audit(events,calls,cutoff=.5):
    from scipy.optimize import linear_sum_assignment
    overlap=np.zeros((len(events),len(calls)))
    mixed=pure_cover=pure_real=unmatched=0
    for i,e in enumerate(events):
        roles=set()
        for j,c in enumerate(calls):
            if e[2]!=c[2]: continue
            if e[0]<=c[1]+.002 and c[0]<=e[1]+.002: roles.add(c[3])
            inter=max(0.,min(e[1],c[1])-max(e[0],c[0])); union=max(e[1],c[1])-min(e[0],c[0])
            overlap[i,j]=inter/union if union>0 else 0.
        mixed+=roles=={0,1};pure_cover+=roles=={1};pure_real+=roles=={0};unmatched+=not roles
    score=(overlap>=cutoff)*(min(overlap.shape)+1)+overlap
    ii,jj=linear_sum_assignment(-score)
    return {'boundary_tp':int(sum(overlap[i,j]>=cutoff for i,j in zip(ii,jj))),
            'boundary_predicted':len(events),'boundary_truth':len(calls),
            'mixed_events':int(mixed),'pure_cover_events':int(pure_cover),
            'pure_real_events':int(pure_real),'unmatched_events':int(unmatched)}


def event_truth(events, calls, slack=.002):
    """1 if the event overlaps a cover/shadow call on its destination, else 0 (audit/training only)."""
    y = []
    for e in events:
        hit = [c for c in calls if c[2] == e[2] and e[0] <= c[1] + slack and c[0] <= e[1] + slack]
        y.append(int(any(c[3] for c in hit)))
    return np.array(y)


def event_features(events):
    n = len(events); x = np.zeros((n, 32))
    last_by_service = {}
    for i, e in enumerate(events):
        prev = events[i - 1] if i else None
        x[i, 0] = np.log1p(max(0., e[1] - e[0]) * 1000)
        x[i, 1] = np.log1p(max(0., e[0] - prev[1]) * 1000) if prev else 0.
        x[i, 2] = np.log1p(max(0., e[0] - last_by_service[e[2]]) * 1000) if e[2] in last_by_service else 0.
        x[i, 3 + e[2]] = 1
        if prev:
            x[i, 10 + prev[2]] = 1
        x[i, 17] = i / max(1, n - 1); x[i, 18] = i == 0; x[i, 19] = i == n - 1
        x[i, 20:23] = np.log1p(e[3:6])
        x[i, 23] = np.log1p(e[0] * 1000); x[i, 24] = np.log1p(n)
        nxt = events[i + 1] if i + 1 < n else None
        x[i, 25] = np.log1p(max(0., nxt[0] - e[1]) * 1000) if nxt else 0.
        if nxt:
            x[i, 26] = nxt[2] == e[2]
        x[i, 27 + min(4, sum(1 for z in events[:i] if z[2] == e[2]))] = 1
        last_by_service[e[2]] = e[1]
    return x


def fit_detector(ro, ev, y, split_tr='train', split_va='validation'):
    Xt = np.concatenate([event_features(z) for z in ev[split_tr]]); Yt = np.concatenate(y[split_tr])
    Xv = np.concatenate([event_features(z) for z in ev[split_va]]); Yv = np.concatenate(y[split_va])
    best = None; fitted = {}
    for kind in ['LR', 'RF']:
        est = ro.make_estimator(kind)
        if kind == 'LR':
            est.set_params(logisticregression__class_weight='balanced')
        else:
            est.set_params(class_weight='balanced')
        if Yt.sum() == 0 or Yt.sum() == len(Yt):
            continue
        est.fit(Xt, Yt); fitted[kind] = est
        p = est.predict_proba(Xv)[:, 1]
        firsts = np.concatenate([np.r_[1, np.zeros(len(z) - 1)] for z in ev[split_va]]).astype(bool)
        for th in np.arange(.05, .951, .05):
            pred = (p >= th) & ~firsts
            cand = (f1_score(Yv, pred, zero_division=0), precision_score(Yv, pred, zero_division=0), kind == 'LR', float(th), kind)
            best = cand if best is None or cand > best else best
    return fitted, best


def probs(fitted, kind, events):
    p = fitted[kind].predict_proba(event_features(events))[:, 1]; p[0] = 0.
    return p


def joint_scores(ro, clean, timing, events, p):
    cand = [int(i) for i in np.argsort(-p)[:K] if i != 0]
    masks = [()] + [m for k in (1, 2) for m in itertools.combinations(sorted(cand), k)]
    X = np.stack([ro.vector([e for i, e in enumerate(events) if i not in m], timing) for m in masks])
    post = clean.predict_proba(X); pc = np.clip(p, 1e-4, 1 - 1e-4)
    s = np.array([math.log(PRIOR[len(m)]) + sum(math.log(pc[i] if i in m else 1 - pc[i]) for i in cand) for m in masks])
    return s, post


def joint_pred(cache, classes, variant, lam):
    out = []
    for s, post in cache:
        if variant == 'MAP':
            q = post[np.argmax(s + lam * np.log(np.maximum(post.max(axis=1), 1e-4)))]
        else:
            w = np.exp(s - s.max()); w /= w.sum(); q = w @ post
        out.append(classes[np.argmax(q)])
    return np.array(out)


def main():
    global PREDICTIONS_SEALED
    ap = argparse.ArgumentParser()
    ap.add_argument('--live-dir', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--record-only-dir', type=Path, default=DEFAULT_RO)
    ap.add_argument('--expect', type=int, default=3000)
    ap.add_argument('--models', nargs='+', default=MODELS, help='subset only for smoke tests')
    a = ap.parse_args()
    check_frozen(a.out, __file__)
    ro, pe = import_record_only(a.record_only_dir)
    rows,sources = extract(a.live_dir, a.out / 'LOCAL-ONLY-p0c-inputs.jsonl')
    expected=load(a.record_only_dir.parent/'verification/no-call-verified.json')['inputs']['inputs/record-only.jsonl']
    actual=sha(a.out/'LOCAL-ONLY-p0c-inputs.jsonl')
    save(a.out/'p0c-input-identity.json',{'expected':expected,'actual':actual,'same_original_record_observations':expected==actual})
    assert actual==expected,'Observation extraction differs; stop before fitting'
    if len(rows) != a.expect:
        sys.exit(f'Expected {a.expect} episodes, found {len(rows)}')
    segs = {f'idle_{d:g}': (lambda rec, d=d: ro.bursts(rec, d)) for d in ro.DELTAS}
    segs['protocol'] = pe.events
    attacks, tests, audit, selections, private_predictions, pending_audit = [], [], [], [], [], []
    for model in a.models:
        data = {ar: {s: sorted([r for r in rows if r['model'] == model and r['arm'] == ar and r['split'] == s], key=lambda r: r['unit'])
                     for s in ['train', 'validation', 'test']} for ar in ARMS}
        yy = {s: np.array([r['label'] for r in data['none'][s]]) for s in data['none']}
        for ar in ARMS:
            for s in yy:
                assert [r['unit'] for r in data[ar][s]]==[r['unit'] for r in data['none'][s]]
                assert [r['label'] for r in data[ar][s]]==yy[s].tolist()
        ev = {seg: {ar: {s: [f(r['records']) for r in data[ar][s]] for s in yy} for ar in ARMS} for seg, f in segs.items()}
        clean = {}
        for seg in segs:
            for timing in [False, True]:
                for kind in ['LR', 'RF']:
                    est = ro.make_estimator(kind)
                    est.fit(np.stack([ro.vector(z, timing) for z in ev[seg]['none']['train']]), yy['train']); clean[seg, timing, kind] = est
        for arm in ARMS[1:]:
            val, tst, kinds = {}, {}, {}
            for seg in segs:
                E = ev[seg][arm]
                truth = {s: [event_truth(z,call_truth(r,sources)) for z,r in zip(E[s],data[arm][s])]
                         for s in ['train','validation']}
                for timing in [False, True]:
                    vv = 'time' if timing else 'size'
                    X = {s: np.stack([ro.vector(z, timing) for z in E[s]]) for s in yy}
                    for kind in ['LR', 'RF']:
                        est = ro.make_estimator(kind); est.fit(X['train'], yy['train'])
                        n = f'base_{seg}_{vv}_{kind}'; val[n] = est.predict(X['validation']); tst[n] = est.predict(X['test']); kinds[n] = 'baseline'
                fitted, best = fit_detector(ro, E, truth)
                if best is None:
                    continue
                f1, prec, _, th, dk = best
                P = {s: [probs(fitted, dk, z) for z in E[s]] for s in ['validation', 'test']}
                pending_audit.append((model,arm,seg,dk,th,f1,E['test'],P['test'],data[arm]['test']))
                for timing in [False, True]:
                    vv = 'time' if timing else 'size'
                    for kind in ['LR', 'RF']:
                        c = clean[seg, timing, kind]
                        for s, store in [('validation', val), ('test', tst)]:
                            kept = [[e for i, e in enumerate(z) if not p[i] >= th] for z, p in zip(E[s], P[s])]
                            store[f'ctx_{seg}_{vv}_{kind}'] = c.predict(np.stack([ro.vector(z, timing) for z in kept]))
                        kinds[f'ctx_{seg}_{vv}_{kind}'] = 'strong'
                        caches = {s: [joint_scores(ro, c, timing, z, p) for z, p in zip(E[s], P[s])] for s in ['validation', 'test']}
                        grid = [('MAP', lam) for lam in [0, .5, 1, 2, 4]] + [('marginal', 1)]
                        js = max(grid, key=lambda g: (sum(joint_pred(caches['validation'], c.classes_, *g) == yy['validation']), -grid.index(g)))
                        n = f'joint_{seg}_{vv}_{kind}'
                        val[n] = joint_pred(caches['validation'], c.classes_, *js); tst[n] = joint_pred(caches['test'], c.classes_, *js); kinds[n] = 'strong'
            # Preserve the existing raw-record baseline, which won some original cells.
            raw={s:[[[v[0],v[0],v[1],v[3] if v[2]==0 else 0,v[3] if v[2]==1 else 0,1]
                      for v in r['records']] for r in data[arm][s]] for s in yy}
            for timing in [False,True]:
                X={s:np.stack([ro.vector(z,timing) for z in raw[s]]) for s in yy}
                for kind in ['LR','RF']:
                    est=ro.make_estimator(kind);est.fit(X['train'],yy['train'])
                    n=f'base_raw_{"time" if timing else "size"}_{kind}'
                    val[n]=est.predict(X['validation']);tst[n]=est.predict(X['test']);kinds[n]='baseline'
            names = list(val); score = {n: int(sum(val[n] == yy['validation'])) for n in names}
            pick = lambda ns: max(ns, key=lambda n: (score[n], -names.index(n)))
            b = pick([n for n in names if kinds[n] == 'baseline']); s_ = pick([n for n in names if kinds[n] == 'strong'])
            selections.append({'model': model, 'arm': ARM_NAMES[arm], 'baseline': b, 'strong': s_, 'overall':pick(names), 'validation_correct': score})
            for n in names:
                attacks.append({'model': model, 'arm': ARM_NAMES[arm], 'attack': n, 'family': kinds[n],
                                'validation_correct': score[n], 'test_correct': int(sum(tst[n] == yy['test'])), 'n': len(yy['test']),
                                'selected': 'baseline' if n == b else ('strong' if n == s_ else '')})
                for split,vectors in [('validation',val),('test',tst)]:
                    for row,pred,truth in zip(data[arm][split],vectors[n],yy[split]):
                        private_predictions.append({'model':model,'arm':arm,'split':split,'unit':row['unit'],'attack':n,'prediction':int(pred),'truth':int(truth)})
            tests.append({'model': model, 'arm': ARM_NAMES[arm], 'strong': s_, 'baseline': b,
                          'strong_correct': int(sum(tst[s_] == yy['test'])), 'baseline_correct': int(sum(tst[b] == yy['test'])),
                          **mcnemar(tst[s_] == yy['test'], tst[b] == yy['test'])})
            print(model, arm, 'baseline', b, tests[-1]['baseline_correct'], 'strong', s_, tests[-1]['strong_correct'], flush=True)
    holm(tests)
    predfile=a.out/'LOCAL-ONLY-p0c-predictions.csv'
    write_csv(predfile,private_predictions)
    save(a.out/'p0c-prediction-seal.json',{'utc':now(),'sha256':hashlib.sha256(predfile.read_bytes()).hexdigest(),
                                        'rows':len(private_predictions),'test_call_truth_accessed':False})
    PREDICTIONS_SEALED=True
    for model,arm,seg,dk,th,f1,events,probabilities,test_rows in pending_audit:
        calls=[call_truth(r,sources) for r in test_rows]
        tt=np.concatenate([event_truth(z,c) for z,c in zip(events,calls)])
        tp=np.concatenate([p>=th for p in probabilities])
        counts={}
        for z,c in zip(events,calls):
            for k,v in boundary_audit(z,c).items(): counts[k]=counts.get(k,0)+v
        bt,bp,br=counts['boundary_tp'],counts['boundary_predicted'],counts['boundary_truth']
        audit.append({'model':model,'arm':ARM_NAMES[arm],'segmentation':seg,'detector':dk,'threshold':th,
                      'validation_cover_label_f1':f1,'test_cover_label_precision':precision_score(tt,tp,zero_division=0),
                      'test_cover_label_recall':recall_score(tt,tp,zero_division=0),'test_cover_label_f1':f1_score(tt,tp,zero_division=0),
                      'test_true_cover_events':int(tt.sum()),'test_events':len(tt),**counts,
                      'segmentation_precision_iou50':bt/bp if bp else 0.,'segmentation_recall_iou50':bt/br if br else 0.,
                      'segmentation_f1_iou50':2*bt/(bp+br) if bp+br else 0.})
    write_csv(a.out / 'p0c-attacks.csv', attacks); write_csv(a.out / 'p0c-tests.csv', tests)
    write_csv(a.out / 'p0c-event-audit.csv', audit)
    save(a.out / 'p0c-summary.json', {'utc': now(), 'role': 'exploratory post-hoc; episode association supplied; '
                                      'call truth used for train/validation detector labels and sealed-prediction test audit; maximum two removed EVENTS, not calls',
                                      'K': K, 'prior': PRIOR, 'tests': tests, 'selections': selections})


if __name__ == '__main__':
    main()
