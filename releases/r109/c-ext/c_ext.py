"""R109 C1-C3: offline robustness analyses of the B1 cover-removal attack.

Stages:  python c_ext.py freeze   (hash plan, code and inputs; no data fitting)
         python c_ext.py run      (reproduction gate, then C1-C3 on train/val/test)
Set M3_SOURCE to the public M3 llm-extension directory (commit 21f136e).
No LLM, API or capture is used. Existing outputs are never overwritten.
"""
import os
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['OPENBLAS_NUM_THREADS'] = '2'
import datetime, gzip, hashlib, json, math, sys, time
from pathlib import Path
import numpy as np
import scipy, sklearn
from scipy.stats import binomtest
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.mixture import GaussianMixture
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HERE = Path(__file__).resolve().parent
SOURCE = Path(os.environ.get('M3_SOURCE', '/tmp/m3/review-r102/llm-extension'))
sys.path.insert(0, str(SOURCE / 'experiment'))
import analyze as original  # noqa: E402

MODELS = ['qwen3:8b', 'llama3.1:8b']
ARMS = original.ARMS
COVER_ARMS = [a for a in ARMS if a != 'none']
LABELS, SERVICES = original.LABELS, original.SERVICES
BOOT_SEED = 1071111
B1_STRIP = {'qwen3:8b': [118, 114, 114, 112, 111, 111], 'llama3.1:8b': [113, 115, 112, 112, 112, 107]}
PLAN = json.loads((HERE / 'analysis-plan.json').read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    assert not path.exists(), 'refusing to overwrite ' + str(path)
    path.write_text(json.dumps(value, indent=2, default=float) + '\n')


# ---------------------------------------------------------------- observation (as B1)
def observe(r):
    receipts = {x['request']['request_id']: x for x in r['tool_receipts']}
    assert len(receipts) == len(r['wire_trace'])
    trace, starts, ends, cover = [], [], [], []
    for w in r['wire_trace']:
        t = receipts[w['request_id']]['terminal']
        s, e = float(t['start']), float(t['end'])
        assert math.isfinite(s) and math.isfinite(e) and e > s
        trace.append({'service': w['service'], 'bytes': list(w['bytes'])})
        starts.append(s); ends.append(e)
        cover.append(int(receipts[w['request_id']]['request']['kind'] == 'cover'))
    o = {'trace': trace, 'start': np.array(starts), 'end': np.array(ends), 'cover': np.array(cover),
         'wall_seconds': float(r['wall_seconds'])}
    return retime(o)


def retime(o):
    s, e = o['start'], o['end']
    dur = np.maximum(e - s, 0.)
    gap = np.zeros(len(s))
    gap[1:] = np.maximum(s[1:] - e[:-1], 0.)
    o['timing'] = np.stack([s - s[0], dur, gap], axis=1)
    return o


def copy_obs(o):
    return {**o, 'start': o['start'].copy(), 'end': o['end'].copy()}


def views(o):
    base = original.features({'wire_trace': o['trace']})
    t = np.zeros(49)
    n = min(16, len(o['timing']))
    t[:3 * n] = o['timing'][:n].ravel()
    t[-1] = o['wall_seconds']
    return {'bytes': base, 'timing_size': np.concatenate([base, t])}


def call_features(o):
    x = np.zeros((len(o['trace']), 10))
    x[:, :2] = np.log1p(o['timing'][:, [2, 1]] * 1000)
    x[0, 2] = 1
    for i, w in enumerate(o['trace']):
        x[i, 3 + SERVICES.index(w['service'])] = 1
    return x


def stripped(o, mask):
    return original.features({'wire_trace': [w for w, m in zip(o['trace'], mask) if not m]})


# ---------------------------------------------------------------- detector (as B1)
def detector_models():
    return {'LR': make_pipeline(StandardScaler(), LogisticRegression(C=1, max_iter=3000, random_state=102,
                                                                     class_weight='balanced')),
            'RF': RandomForestClassifier(n_estimators=300, n_jobs=2, random_state=102, class_weight='balanced')}


def metrics(truth, pred, prob=None):
    tp = int(np.sum((truth == 1) & (pred == 1))); fp = int(np.sum((truth == 0) & (pred == 1)))
    fn = int(np.sum((truth == 1) & (pred == 0))); tn = int(np.sum((truth == 0) & (pred == 0)))
    return {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
            'precision': tp / (tp + fp) if tp + fp else 0., 'recall': tp / (tp + fn) if tp + fn else 0.,
            'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.,
            'auc': float(roc_auc_score(truth, prob)) if prob is not None and len(set(truth)) == 2 else None}


def fit_detector(train, val):
    xt = np.concatenate([call_features(o) for o in train]); yt = np.concatenate([o['cover'] for o in train])
    xv = np.concatenate([call_features(o) for o in val]); yv = np.concatenate([o['cover'] for o in val])
    first = xv[:, 2] == 1
    cands, fitted = [], {}
    for name, est in detector_models().items():
        est.fit(xt, yt); fitted[name] = est
        p = est.predict_proba(xv)[:, 1]
        for th in np.arange(.05, .951, .05):
            pr = (p >= th).astype(int); pr[first] = 0
            cands.append({'name': name, 'threshold': float(th), 'metric': metrics(yv, pr)})
    gap = np.concatenate([o['timing'][:, 2] for o in val])
    for th in [.025, .05, .10, .20, .35, .50, 1.0]:
        cands.append({'name': 'gap_rule', 'threshold': th, 'metric': metrics(yv, ((gap < th) & ~first).astype(int))})
    sel = max(cands, key=lambda c: (c['metric']['f1'], c['metric']['precision'],
                                    {'LR': 2, 'gap_rule': 1, 'RF': 0}[c['name']], c['threshold']))
    return fitted, {'name': sel['name'], 'threshold': sel['threshold'], 'validation': sel['metric']}


def predict_cover(o, fitted, sel):
    if sel['name'] == 'gap_rule':
        prob = 1 / (1 + o['timing'][:, 2]); pred = o['timing'][:, 2] < sel['threshold']
    else:
        prob = fitted[sel['name']].predict_proba(call_features(o))[:, 1]; pred = prob >= sel['threshold']
    pred = np.asarray(pred, int); pred[0] = 0
    prob = np.asarray(prob, float).copy(); prob[0] = 0.
    return pred, prob


# ---------------------------------------------------------------- transforms
def jitter(o, sigma, rng):
    o = copy_obs(o)
    es = np.abs(rng.normal(0, sigma, len(o['start']))); ee = np.abs(rng.normal(0, sigma, len(o['end'])))
    o['start'] = o['start'] + es; o['end'] = o['end'] + ee
    o['wall_seconds'] = o['wall_seconds'] + float(ee[-1])
    return retime(o)


def matched(o, honest_gaps, honest_dur, rng, with_duration):
    o = copy_obs(o)
    added = 0.
    for i in range(1, len(o['start'])):
        if not o['cover'][i]:
            continue
        old_gap = o['start'][i] - o['end'][i - 1]
        d = max(float(rng.choice(honest_gaps)) - old_gap, 0.)
        o['start'][i:] += d; o['end'][i:] += d; added += d
        if with_duration:
            pool = honest_dur.get(o['trace'][i]['service']) or honest_dur['__all__']
            extra = max(float(rng.choice(pool)) - (o['end'][i] - o['start'][i]), 0.)
            o['end'][i:] += extra; o['start'][i + 1:] += extra; added += extra
    o['wall_seconds'] = o['wall_seconds'] + added
    o['added_latency'] = added
    return retime(o)


def gmm_threshold(gaps):
    lg = np.log10(np.maximum(np.asarray(gaps), 1e-4)).reshape(-1, 1)
    g = GaussianMixture(2, covariance_type='full', random_state=102, n_init=5).fit(lg)
    lo, hi = sorted(g.means_.ravel())
    low_comp = int(np.argmin(g.means_.ravel()))
    for _ in range(100):
        mid = (lo + hi) / 2
        if g.predict_proba([[mid]])[0, low_comp] > .5:
            lo = mid
        else:
            hi = mid
    return float(10 ** ((lo + hi) / 2)), {'means_log10': g.means_.ravel().tolist(), 'weights': g.weights_.tolist()}


# ---------------------------------------------------------------- statistics
def boot(y):
    rng = np.random.default_rng(BOOT_SEED)
    return np.concatenate([rng.choice(np.flatnonzero(y == k), size=(10000, int(np.sum(y == k))), replace=True)
                           for k in range(6)], axis=1)


def ci(v, idx):
    return np.quantile(np.asarray(v, float)[idx].mean(axis=1), [.025, .975]).tolist()


def contrast(a, b, model, arm, name, idx):
    plus, minus = int(np.sum(a & ~b)), int(np.sum(b & ~a))
    d = a.astype(int) - b.astype(int)
    return {'model': model, 'arm': arm, 'comparison': name, 'condition_only': plus, 'reference_only': minus,
            'difference_pp': float(d.mean() * 100), 'conditional_ci_pp': (100 * np.array(ci(d, idx))).tolist(),
            'p_raw': float(binomtest(plus, plus + minus, .5).pvalue) if plus + minus else 1.}


def holm(rows):
    order = sorted(range(len(rows)), key=lambda i: rows[i]['p_raw'])
    m, running = len(rows), 0.
    for k, i in enumerate(order):
        running = max(running, min(1., (m - k) * rows[i]['p_raw']))
        rows[i]['p_holm'] = running
    return rows


# ---------------------------------------------------------------- stages
INPUTS = ['data/episodes.jsonl.gz', 'experiment/analyze.py', 'experiment/common.py',
          'analysis/predictions.csv', 'analysis/validation-selection.json']


def freeze():
    assert not (HERE / 'freeze.json').exists()
    manifest = json.loads((SOURCE / 'manifest.json').read_text())['files']
    for p in INPUTS:
        assert sha(SOURCE / p) == manifest[p]['sha256'], p
    save(HERE / 'freeze.json', {'utc': now(), 'status': 'FROZEN_BEFORE_C1_C3_EVALUATION',
                                'plan_sha256': sha(HERE / 'analysis-plan.json'), 'code_sha256': sha(__file__),
                                'inputs': {p: sha(SOURCE / p) for p in INPUTS},
                                'environment': {'python': sys.version, 'numpy': np.__version__,
                                                'scipy': scipy.__version__, 'sklearn': sklearn.__version__}})
    print('FROZEN')


def run():
    f = json.loads((HERE / 'freeze.json').read_text())
    assert sha(HERE / 'analysis-plan.json') == f['plan_sha256'] and sha(__file__) == f['code_sha256']
    for p, d in f['inputs'].items():
        assert sha(SOURCE / p) == d, p
    out = HERE / 'results'
    assert not out.exists()
    t0 = time.time()
    recs = [json.loads(l) for l in gzip.open(SOURCE / 'data/episodes.jsonl.gz', 'rt')]
    obs = {(r['model'], r['arm'], r['split'], r['task_id']): observe(r) for r in recs}
    lab = {(r['model'], r['arm'], r['split'], r['task_id']): LABELS.index(r['label']) for r in recs}
    import csv
    saved = {(z['model'], z['arm'], int(z['task_id'])): (int(z['LR']), int(z['RF']))
             for z in csv.DictReader((SOURCE / 'analysis/predictions.csv').open())}
    res = {'gate': [], 'C1': [], 'C2': [], 'C3': [], 'C2_family': [], 'C3_primary': [], 'C3_secondary': [],
           'C2_thresholds': {}, 'C3_latency': []}

    def ids(model, arm, split):
        return sorted(k[3] for k in obs if k[0] == model and k[1] == arm and k[2] == split)

    for model in MODELS:
        print('model', model, flush=True)
        tr = {a: [obs[model, a, 'train', i] for i in ids(model, a, 'train')] for a in ARMS}
        va = {a: [obs[model, a, 'validation', i] for i in ids(model, a, 'validation')] for a in ARMS}
        te_ids = ids(model, 'none', 'test')
        te = {a: [obs[model, a, 'test', i] for i in te_ids] for a in ARMS}
        y = {s: np.array([lab[model, 'none', s, i] for i in ids(model, 'none', s)]) for s in ['train', 'validation', 'test']}
        assert all(ids(model, a, 'test') == te_ids for a in ARMS)
        idx = boot(y['test'])

        def fit_view(train, val, view):
            xtr = np.stack([views(o)[view] for o in train]); xv = np.stack([views(o)[view] for o in val])
            fitted, scores = {}, {}
            for n, est in original.estimators().items():
                est.fit(xtr, y['train']); fitted[n] = est
                scores[n] = float(np.mean(est.predict(xv) == y['validation']))
            return fitted[original.choose(scores)], fitted, original.choose(scores)

        # ---- reproduction gate
        none_clf, none_all, _ = fit_view(tr['none'], va['none'], 'bytes')
        byte_correct = {}
        for a in ARMS:
            sel, allf, name = fit_view(tr[a], va[a], 'bytes')
            X = np.stack([views(o)['bytes'] for o in te[a]])
            for n in ['LR', 'RF']:
                pred = allf[n].predict(X)
                assert all(int(pred[k]) == saved[model, a, te_ids[k]][0 if n == 'LR' else 1] for k in range(len(te_ids))), (model, a, n)
            byte_correct[a] = sel.predict(X) == y['test']
        dtr = [o for a in ARMS for o in tr[a]]; dva = [o for a in ARMS for o in va[a]]
        det, det_sel = fit_detector(dtr, dva)
        clean_strip = {}
        for k, a in enumerate(ARMS):
            masks = [predict_cover(o, det, det_sel)[0] for o in te[a]]
            clean_strip[a] = none_clf.predict(np.stack([stripped(o, m) for o, m in zip(te[a], masks)])) == y['test']
            res['gate'].append({'model': model, 'arm': a, 'byte_selected': int(byte_correct[a].sum()),
                                'strip': int(clean_strip[a].sum()), 'b1_strip': B1_STRIP[model][k]})
            assert int(clean_strip[a].sum()) == B1_STRIP[model][k], ('gate', model, a)
        print('gate passed', model, flush=True)

        def strip_eval(test_obs, d, s):
            masks, probs = zip(*(predict_cover(o, d, s) for o in test_obs))
            correct = none_clf.predict(np.stack([stripped(o, m) for o, m in zip(test_obs, masks)])) == y['test']
            truth = np.concatenate([o['cover'] for o in test_obs])
            return correct, metrics(truth, np.concatenate(masks), np.concatenate(probs))

        # ---- C1 jitter
        C1 = PLAN['C1_jitter']
        for sigma in C1['sigmas_seconds']:
            per = {a: {'frozen': [], 'adaptive': [], 'adaptive_recall': [], 'adaptive_precision': []} for a in COVER_ARMS}
            for draw in range(C1['draws']):
                rng = np.random.default_rng([C1['seed'], int(sigma * 1000), draw, MODELS.index(model)])
                jtr = [jitter(o, sigma, rng) for o in dtr]; jva = [jitter(o, sigma, rng) for o in dva]
                jte = {a: [jitter(o, sigma, rng) for o in te[a]] for a in COVER_ARMS}
                jdet, jsel = fit_detector(jtr, jva)
                for a in COVER_ARMS:
                    c_f, _ = strip_eval(jte[a], det, det_sel)
                    c_a, m_a = strip_eval(jte[a], jdet, jsel)
                    per[a]['frozen'].append(int(c_f.sum())); per[a]['adaptive'].append(int(c_a.sum()))
                    per[a]['adaptive_recall'].append(m_a['recall']); per[a]['adaptive_precision'].append(m_a['precision'])
            for a in COVER_ARMS:
                res['C1'].append({'model': model, 'arm': a, 'sigma': sigma, 'byte_selected': int(byte_correct[a].sum()),
                                  **{k + '_mean': float(np.mean(v)) for k, v in per[a].items()},
                                  'frozen_range': [min(per[a]['frozen']), max(per[a]['frozen'])],
                                  'adaptive_range': [min(per[a]['adaptive']), max(per[a]['adaptive'])]})
            print('C1', model, sigma, flush=True)

        # ---- C2 label-free
        gaps = np.concatenate([o['timing'][1:, 2] for a in COVER_ARMS for o in tr[a]])
        th, gm = gmm_threshold(gaps)
        res['C2_thresholds'][model] = {'gmm_threshold_seconds': th, **gm}
        for rule, thr in [('gmm', th), ('fixed_0.1', .1), ('fixed_0.2', .2)]:
            s = {'name': 'gap_rule', 'threshold': thr}
            for a in COVER_ARMS:
                c, m = strip_eval(te[a], None, s)
                res['C2'].append({'model': model, 'arm': a, 'rule': rule, 'threshold': thr, 'strip': int(c.sum()),
                                  'byte_selected': int(byte_correct[a].sum()), **m})
                if rule == 'gmm':
                    res['C2_family'].append(contrast(c, byte_correct[a], model, a, 'gmm strip minus byte', idx))

        # ---- C3 timing-matched dispatch
        hg = np.concatenate([o['timing'][1:, 2] for o in tr['none']])
        hd = {'__all__': list(np.concatenate([o['timing'][1:, 1] for o in tr['none']]))}
        for o in tr['none']:
            for i in range(1, len(o['trace'])):
                hd.setdefault(o['trace'][i]['service'], []).append(float(o['timing'][i, 1]))
        mean_wall_none = float(np.mean([o['wall_seconds'] for o in te['none']]))
        for variant, with_dur in [('C3a_gap', False), ('C3b_gap_duration', True)]:
            rng = np.random.default_rng([PLAN['C3_timing_matched']['seed'], int(with_dur), MODELS.index(model)])
            mtr = {a: [matched(o, hg, hd, rng, with_dur) for o in tr[a]] for a in ARMS}
            mva = {a: [matched(o, hg, hd, rng, with_dur) for o in va[a]] for a in ARMS}
            mte = {a: [matched(o, hg, hd, rng, with_dur) for o in te[a]] for a in ARMS}
            mdet, msel = fit_detector([o for a in ARMS for o in mtr[a]], [o for a in ARMS for o in mva[a]])
            for a in COVER_ARMS:
                c, m = strip_eval(mte[a], mdet, msel)
                sel, _, name = fit_view(mtr[a], mva[a], 'timing_size')
                ts = sel.predict(np.stack([views(o)['timing_size'] for o in mte[a]])) == y['test']
                lat = float(np.mean([o['added_latency'] for o in mte[a]]))
                res['C3'].append({'model': model, 'arm': a, 'variant': variant, 'detector': msel,
                                  'strip': int(c.sum()), 'strip_ci': [120 * v for v in ci(c, idx)],
                                  'timing_size_selected': int(ts.sum()), 'timing_size_learner': name,
                                  'byte_selected': int(byte_correct[a].sum()), 'b1_strip': int(clean_strip[a].sum()),
                                  'added_latency_mean_s': lat, 'added_latency_pct_of_none_wall': 100 * lat / mean_wall_none,
                                  **{'det_' + k: v for k, v in m.items()}})
                if with_dur:
                    res['C3_primary'].append(contrast(c, clean_strip[a], model, a, 'C3b strip minus B1 strip', idx))
                    res['C3_secondary'].append(contrast(c, byte_correct[a], model, a, 'C3b strip minus byte', idx))
            print('C3', model, variant, flush=True)
    for fam in ['C2_family', 'C3_primary', 'C3_secondary']:
        holm(res[fam])
    out.mkdir()
    for k, v in res.items():
        save(out / (k + '.json'), v)
    save(out / 'finished.json', {'utc': now(), 'seconds': time.time() - t0, 'freeze_sha256': sha(HERE / 'freeze.json'),
                                 'files': {p.name: sha(p) for p in sorted(out.iterdir()) if p.name != 'finished.json'}})
    print('DONE', time.time() - t0)


if __name__ == '__main__':
    {'freeze': freeze, 'run': run}[sys.argv[1]]()
