"""R110 D: adaptive attacks against timing-matched dispatch, best-attack definition, context-matched dispatch.

Stages:  python d_ext.py freeze   (hash plan, code and inputs; no data fitting)
         python d_ext.py run      (reproduction gate, then D1-D4; refuses to overwrite results)
Requires M3_SOURCE (default /tmp/m3/review-r102/llm-extension) and the R109 c-ext package.
"""
import os
os.environ.setdefault('OMP_NUM_THREADS', '2'); os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
import itertools, json, sys, time, warnings
warnings.filterwarnings('ignore', category=UserWarning)
from pathlib import Path
import numpy as np
import scipy, sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HERE = Path(__file__).resolve().parent
C_EXT = HERE.parent.parent / 'r109' / 'c-ext'
sys.path.insert(0, str(C_EXT))
import c_ext as C  # noqa: E402  (imports the original M3 analyze module through M3_SOURCE)

PLAN = json.loads((HERE / 'analysis-plan.json').read_text())
MODELS, ARMS, COVER_ARMS, SERVICES = C.MODELS, C.ARMS, C.COVER_ARMS, C.SERVICES
POSITION_MAP = {'payments': 0, 'crm': 1, 'helpdesk': 2, 'shipping': 3, 'orders': 4, 'billing': 5}  # M3 analyze.py
C3C_SEED = 1101113
LAMBDAS = [0, .5, 1, 2, 4]
EPS = 1e-4


# ---------------------------------------------------------------- position rules (M3, unchanged)
def position_rule(o, offset):
    t = o['trace']
    return POSITION_MAP.get(t[offset]['service'], 0) if len(t) >= abs(offset) else 0


# ---------------------------------------------------------------- context-conditioned detector (D2a)
def honest_duration_medians(train):
    pool = {}
    for o in train:
        for i in range(1, len(o['trace'])):
            if not o['cover'][i]:
                pool.setdefault(o['trace'][i]['service'], []).append(float(o['timing'][i, 1]))
    allv = [v for vs in pool.values() for v in vs]
    med = {s: float(np.median(v)) for s, v in pool.items()}
    med['__all__'] = float(np.median(allv))
    return med


def ctx_features(o, med):
    base = C.call_features(o)
    n = len(o['trace'])
    gap, dur, rel = o['timing'][:, 2], o['timing'][:, 1], o['timing'][:, 0]
    egap = float(np.median(gap[1:])) if n > 1 else 1.
    lg = np.log(np.maximum(gap, 1e-3))
    x = np.zeros((n, 34))
    x[:, :10] = base
    for i in range(n):
        x[i, 10 + min(i, 7)] = 1
        x[i, 18] = np.log1p(rel[i] * 1000)
        x[i, 19] = np.log(max(gap[i], 1e-3) / max(egap, 1e-3)) if i else 0.
        x[i, 20] = lg[i - 1] if i > 1 else 0.
        x[i, 21] = lg[i + 1] if i + 1 < n else 0.
        m = med.get(o['trace'][i]['service'], med['__all__'])
        x[i, 22] = np.log(max(dur[i], 1e-3) / max(m, 1e-3))
        up, dn = o['trace'][i]['bytes']
        x[i, 23], x[i, 24] = np.log1p(up), np.log1p(dn)
        if i:
            x[i, 25 + SERVICES.index(o['trace'][i - 1]['service'])] = 1
        x[i, 32] = float(i == n - 1)
        x[i, 33] = n
    return x


def ctx_models():
    return {'LR': make_pipeline(StandardScaler(), LogisticRegression(C=1, max_iter=3000, random_state=102,
                                                                     class_weight='balanced')),
            'RF': RandomForestClassifier(n_estimators=300, n_jobs=2, random_state=102, class_weight='balanced')}


def fit_ctx(train, val):
    med = honest_duration_medians(train)
    xt = np.concatenate([ctx_features(o, med) for o in train]); yt = np.concatenate([o['cover'] for o in train])
    xv = np.concatenate([ctx_features(o, med) for o in val]); yv = np.concatenate([o['cover'] for o in val])
    first = xv[:, 2] == 1
    fitted, cands = {}, []
    for name, est in ctx_models().items():
        est.fit(xt, yt); fitted[name] = est
        p = est.predict_proba(xv)[:, 1]
        for th in np.arange(.05, .951, .05):
            pr = (p >= th).astype(int); pr[first] = 0
            cands.append({'name': name, 'threshold': float(th), 'metric': C.metrics(yv, pr)})
    sel = max(cands, key=lambda c: (c['metric']['f1'], c['metric']['precision'], {'LR': 1, 'RF': 0}[c['name']],
                                    c['threshold']))
    return {'models': fitted, 'med': med, 'sel': {'name': sel['name'], 'threshold': sel['threshold'],
                                                   'validation': sel['metric']}}


def ctx_probs(objs, ctx, name):
    xs = [ctx_features(o, ctx['med']) for o in objs]
    p = ctx['models'][name].predict_proba(np.concatenate(xs))[:, 1]
    out, k = [], 0
    for x in xs:
        q = p[k:k + len(x)].copy(); q[0] = 0.; out.append(q); k += len(x)
    return out


# ---------------------------------------------------------------- joint decoding (D2b)
def masks_for(n):
    cand = list(range(1, min(6, n - 1) + 1))
    out = [()]
    for k in (1, 2):
        out += list(itertools.combinations(cand, k))
    return cand, out


def joint_batch(objs, probs, clf, prior_k):
    scores, feats, sizes = [], [], []
    for o, p in zip(objs, probs):
        cand, masks = masks_for(len(o['trace']))
        pc = np.clip(p, EPS, 1 - EPS)
        sc = []
        for m in masks:
            v = np.log(prior_k[len(m)])
            for i in cand:
                v += np.log(pc[i]) if i in m else np.log(1 - pc[i])
            sc.append(v)
            feats.append(C.original.features({'wire_trace': [w for j, w in enumerate(o['trace']) if j not in m]}))
        scores.append(np.array(sc)); sizes.append(len(masks))
    post = clf.predict_proba(np.stack(feats))
    out, k = [], 0
    for sc, n in zip(scores, sizes):
        out.append((sc, post[k:k + n])); k += n
    return out


def joint_predict(score, post, classes, variant, lam):
    if variant == 'MAP':
        tot = score + lam * np.log(np.maximum(post.max(axis=1), EPS))
        return int(classes[int(np.argmax(post[int(np.argmax(tot))]))])
    w = np.exp(score - score.max()); w /= w.sum()
    return int(classes[int(np.argmax(w @ post))])


JOINT_GRID = [(d, 'MAP', lam) for d in ('LR', 'RF') for lam in LAMBDAS] + [(d, 'marginal', 1) for d in ('LR', 'RF')]


# ---------------------------------------------------------------- context-matched dispatch (D4, C3c)
def matched_pos(o, gaps_by_pos, pooled, honest_dur, rng):
    o = C.copy_obs(o)
    added = 0.
    for i in range(1, len(o['start'])):
        if not o['cover'][i]:
            continue
        pool = gaps_by_pos.get(i)
        pool = pool if pool is not None and len(pool) >= 20 else pooled
        old_gap = o['start'][i] - o['end'][i - 1]
        d = max(float(rng.choice(pool)) - old_gap, 0.)
        o['start'][i:] += d; o['end'][i:] += d; added += d
        dpool = honest_dur.get(o['trace'][i]['service']) or honest_dur['__all__']
        extra = max(float(rng.choice(dpool)) - (o['end'][i] - o['start'][i]), 0.)
        o['end'][i:] += extra; o['start'][i + 1:] += extra; added += extra
    o['wall_seconds'] = o['wall_seconds'] + added
    o['added_latency'] = added
    return C.retime(o)


# ---------------------------------------------------------------- stages
SIZE_ATTACKS = ['byte_LR', 'byte_RF', 'frozen', 'position_last', 'position_penultimate']
TIMING_ATTACKS = ['timing_size', 'b1_strip', 'ctx_strip', 'joint']


def freeze():
    assert not (HERE / 'freeze.json').exists()
    c_freeze = json.loads((C_EXT / 'freeze.json').read_text())
    for p, d in c_freeze['inputs'].items():
        assert C.sha(C.SOURCE / p) == d, p
    C.save(HERE / 'freeze.json', {'utc': C.now(), 'status': 'FROZEN_BEFORE_D_EVALUATION',
                                  'plan_sha256': C.sha(HERE / 'analysis-plan.json'), 'code_sha256': C.sha(__file__),
                                  'c_ext_code_sha256': C.sha(C_EXT / 'c_ext.py'),
                                  'c_ext_plan_sha256': C.sha(C_EXT / 'analysis-plan.json'),
                                  'inputs': c_freeze['inputs'],
                                  'environment': {'python': sys.version, 'numpy': np.__version__,
                                                  'scipy': scipy.__version__, 'sklearn': sklearn.__version__}})
    print('FROZEN')


def run():
    import gzip
    smoke = os.environ.get('D_SMOKE') == '1'  # validation-as-test dry run; no gate, no tests, no output
    f = None if smoke else json.loads((HERE / 'freeze.json').read_text())
    if not smoke:
        assert C.sha(HERE / 'analysis-plan.json') == f['plan_sha256'] and C.sha(__file__) == f['code_sha256']
        assert C.sha(C_EXT / 'c_ext.py') == f['c_ext_code_sha256']
        for p, d in f['inputs'].items():
            assert C.sha(C.SOURCE / p) == d, p
    out = HERE / 'results'
    assert smoke or not out.exists()
    r109 = {(r['model'], r['arm'], r['variant']): r for r in json.loads((C_EXT / 'results' / 'C3.json').read_text())}
    t0 = time.time()
    recs = [json.loads(l) for l in gzip.open(C.SOURCE / 'data/episodes.jsonl.gz', 'rt')]
    obs = {(r['model'], r['arm'], r['split'], r['task_id']): C.observe(r) for r in recs}
    lab = {(r['model'], r['arm'], r['split'], r['task_id']): C.LABELS.index(r['label']) for r in recs}
    res = {'gate': [], 'cells': [], 'selection': [], 'joint_selection': [], 'ctx_selection': [],
           'primary': [], 'secondary': [], 'descriptive': []}

    def ids(model, arm, split):
        return sorted(k[3] for k in obs if k[0] == model and k[1] == arm and k[2] == split)

    for model in MODELS:
        print('model', model, flush=True)
        tr = {a: [obs[model, a, 'train', i] for i in ids(model, a, 'train')] for a in ARMS}
        va = {a: [obs[model, a, 'validation', i] for i in ids(model, a, 'validation')] for a in ARMS}
        tsplit = 'validation' if smoke else 'test'
        te_ids = ids(model, 'none', tsplit)
        te = {a: [obs[model, a, tsplit, i] for i in te_ids] for a in ARMS}
        y = {s: np.array([lab[model, 'none', s, i] for i in ids(model, 'none', s)]) for s in ['train', 'validation']}
        y['test'] = np.array([lab[model, 'none', tsplit, i] for i in te_ids])
        idx = None if smoke else C.boot(y['test'])

        def fit_view(train, val, view):
            xtr = np.stack([C.views(o)[view] for o in train]); xv = np.stack([C.views(o)[view] for o in val])
            fitted, scores = {}, {}
            for n, est in C.original.estimators().items():
                est.fit(xtr, y['train']); fitted[n] = est
                scores[n] = float(np.mean(est.predict(xv) == y['validation']))
            return fitted[C.original.choose(scores)], fitted, C.original.choose(scores)

        none_clf, _, _ = fit_view(tr['none'], va['none'], 'bytes')
        classes = none_clf.classes_
        byte_fits = {a: fit_view(tr[a], va[a], 'bytes') for a in ARMS}
        dtr = [o for a in ARMS for o in tr[a]]; dva = [o for a in ARMS for o in va[a]]
        det, det_sel = C.fit_detector(dtr, dva)
        clean_strip = {}
        for a in ARMS:
            masks = [C.predict_cover(o, det, det_sel)[0] for o in te[a]]
            clean_strip[a] = int((none_clf.predict(np.stack([C.stripped(o, m) for o, m in zip(te[a], masks)])) == y['test']).sum())

        # ---- regenerate C3a/C3b exactly as R109, then C3c
        hg = np.concatenate([o['timing'][1:, 2] for o in tr['none']])
        hd = {'__all__': list(np.concatenate([o['timing'][1:, 1] for o in tr['none']]))}
        for o in tr['none']:
            for i in range(1, len(o['trace'])):
                hd.setdefault(o['trace'][i]['service'], []).append(float(o['timing'][i, 1]))
        gpos = {}
        for o in tr['none']:
            for i in range(1, len(o['trace'])):
                gpos.setdefault(i, []).append(float(o['timing'][i, 2]))
        gpos = {k: np.array(v) for k, v in gpos.items()}
        mean_wall_none = float(np.mean([o['wall_seconds'] for o in te['none']]))
        cohorts = {}
        for variant, with_dur in [('C3a_gap', False), ('C3b_gap_duration', True)]:
            rng = np.random.default_rng([C.PLAN['C3_timing_matched']['seed'], int(with_dur), MODELS.index(model)])
            cohorts[variant] = tuple({a: [C.matched(o, hg, hd, rng, with_dur) for o in part[a]] for a in ARMS}
                                     for part in (tr, va, te))
        rng = np.random.default_rng([C3C_SEED, MODELS.index(model)])
        cohorts['C3c_position'] = tuple({a: [matched_pos(o, gpos, hg, hd, rng) for o in part[a]] for a in ARMS}
                                        for part in (tr, va, te))

        prior = np.bincount([int(o['cover'].sum()) for o in dtr], minlength=3).astype(float)
        prior = (prior + 1) / (prior + 1).sum()

        for variant, (mtr, mva, mte) in cohorts.items():
            mdet, msel = C.fit_detector([o for a in ARMS for o in mtr[a]], [o for a in ARMS for o in mva[a]])
            ctx = fit_ctx([o for a in ARMS for o in mtr[a]], [o for a in ARMS for o in mva[a]])
            res['ctx_selection'].append({'model': model, 'variant': variant, 'b1_detector': msel, 'ctx_detector': ctx['sel']})
            # joint-decoding selection on pooled validation over cover arms
            jv = {}
            for a in COVER_ARMS:
                sp = {d: joint_batch(mva[a], ctx_probs(mva[a], ctx, d), none_clf, prior) for d in ('LR', 'RF')}
                for k in range(len(mva[a])):
                    for g in JOINT_GRID:
                        jv.setdefault(g, []).append(joint_predict(*sp[g[0]][k], classes, g[1], g[2]) == y['validation'][k])
            jacc = {g: float(np.mean(v)) for g, v in jv.items()}
            jsel = max(JOINT_GRID, key=lambda g: (jacc[g], g[0] == 'LR', g[1] == 'MAP', -g[2]))
            res['joint_selection'].append({'model': model, 'variant': variant, 'selected': list(jsel),
                                           'validation_accuracy': {f'{g[0]}-{g[1]}-{g[2]}': v for g, v in jacc.items()}})

            def all_attacks(split_obs, ylab, arm):
                bf = byte_fits[arm][1]
                Xb = np.stack([C.views(o)['bytes'] for o in split_obs])
                ts_sel = ts_fit[arm]
                masks = [C.predict_cover(o, mdet, msel)[0] for o in split_obs]
                sp_sel = ctx_probs(split_obs, ctx, ctx['sel']['name'])
                cmask = []
                for q in sp_sel:
                    m = (q >= ctx['sel']['threshold']).astype(int); m[0] = 0; cmask.append(m)
                jp = [joint_predict(sc, post, classes, jsel[1], jsel[2])
                      for sc, post in joint_batch(split_obs, ctx_probs(split_obs, ctx, jsel[0]), none_clf, prior)]
                pred = {'byte_LR': bf['LR'].predict(Xb), 'byte_RF': bf['RF'].predict(Xb), 'frozen': none_clf.predict(Xb),
                        'position_last': np.array([position_rule(o, -1) for o in split_obs]),
                        'position_penultimate': np.array([position_rule(o, -2) for o in split_obs]),
                        'timing_size': ts_sel.predict(np.stack([C.views(o)['timing_size'] for o in split_obs])),
                        'b1_strip': none_clf.predict(np.stack([C.stripped(o, m) for o, m in zip(split_obs, masks)])),
                        'ctx_strip': none_clf.predict(np.stack([C.stripped(o, m) for o, m in zip(split_obs, cmask)])),
                        'joint': np.array(jp)}
                return {k: v == ylab for k, v in pred.items()}, masks, cmask

            ts_fit = {a: fit_view(mtr[a], mva[a], 'timing_size')[0] for a in COVER_ARMS}
            for a in COVER_ARMS:
                vc, _, _ = all_attacks(mva[a], y['validation'], a)
                tc, masks, cmask = all_attacks(mte[a], y['test'], a)
                vacc = {k: float(v.mean()) for k, v in vc.items()}
                size_best = max(SIZE_ATTACKS, key=lambda k: (vacc[k], -SIZE_ATTACKS.index(k)))
                order = SIZE_ATTACKS + TIMING_ATTACKS
                adapt_best = max(order, key=lambda k: (vacc[k], -order.index(k)))
                truth = np.concatenate([o['cover'] for o in mte[a]])
                cell = {'model': model, 'arm': a, 'variant': variant,
                        'test_correct': {k: int(v.sum()) for k, v in tc.items()},
                        'validation_accuracy': vacc, 'size_only_best': size_best, 'adaptive_best': adapt_best,
                        'size_only_best_correct': int(tc[size_best].sum()), 'adaptive_best_correct': int(tc[adapt_best].sum()),
                        'descriptive_test_max': int(max(v.sum() for v in tc.values())),
                        'descriptive_test_argmax': max(tc, key=lambda k: tc[k].sum()),
                        'b1_strip_detector': C.metrics(truth, np.concatenate(masks)),
                        'ctx_strip_detector': C.metrics(truth, np.concatenate(cmask),
                                                        np.concatenate(ctx_probs(mte[a], ctx, ctx['sel']['name']))),
                        'added_latency_mean_s': float(np.mean([o['added_latency'] for o in mte[a]])),
                        'original_byte_selected': int((byte_fits[a][0].predict(np.stack([C.views(o)['bytes'] for o in te[a]])) == y['test']).sum()),
                        'b1_clean_strip': clean_strip[a]}
                cell['added_latency_pct_of_none_wall'] = 100 * cell['added_latency_mean_s'] / mean_wall_none
                res['cells'].append(cell)
                if smoke:
                    print(variant, a, cell['test_correct'], flush=True)
                    continue
                if variant in ('C3a_gap', 'C3b_gap_duration'):
                    ref = r109[model, a, variant]
                    ok = (ref['strip'] == cell['test_correct']['b1_strip'] and
                          ref['timing_size_selected'] == cell['test_correct']['timing_size'])
                    res['gate'].append({'model': model, 'arm': a, 'variant': variant, 'ok': ok,
                                        'r109_strip': ref['strip'], 'strip': cell['test_correct']['b1_strip'],
                                        'r109_ts': ref['timing_size_selected'], 'ts': cell['test_correct']['timing_size']})
                    assert ok, ('gate', model, a, variant)
                fam = {'C3b_gap_duration': 'primary', 'C3c_position': 'secondary'}.get(variant)
                if fam:
                    res[fam].append({**C.contrast(tc[adapt_best], tc[size_best], model, a,
                                                  f'{variant}: adaptive_best ({adapt_best}) minus size_only_best ({size_best})', idx),
                                     'variant': variant})
                for k in TIMING_ATTACKS:
                    res['descriptive'].append({**C.contrast(tc[k], tc[size_best], model, a,
                                                            f'{variant}: {k} minus size_only_best ({size_best})', idx),
                                               'variant': variant})
            print(variant, model, 'done', round(time.time() - t0), flush=True)
        if smoke:
            return
    C.holm(res['primary']); C.holm(res['secondary'])
    out.mkdir()
    for k, v in res.items():
        C.save(out / (k + '.json'), v)
    C.save(out / 'finished.json', {'utc': C.now(), 'seconds': time.time() - t0, 'freeze_sha256': C.sha(HERE / 'freeze.json'),
                                   'files': {p.name: C.sha(p) for p in sorted(out.iterdir()) if p.name != 'finished.json'}})
    print('DONE', time.time() - t0)


if __name__ == '__main__':
    {'freeze': freeze, 'run': run}[sys.argv[1]]()
