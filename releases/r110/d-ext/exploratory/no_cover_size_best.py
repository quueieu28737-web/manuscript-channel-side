"""Descriptive (after D results): validation-selected size-only best for the no-cover arm, for Table 7."""
import json, gzip, sys, warnings
from pathlib import Path
import numpy as np
warnings.filterwarnings('ignore')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import d_ext as D
C = D.C
recs = [json.loads(l) for l in gzip.open(C.SOURCE / 'data/episodes.jsonl.gz', 'rt')]
obs = {(r['model'], r['arm'], r['split'], r['task_id']): C.observe(r) for r in recs}
lab = {(r['model'], r['arm'], r['split'], r['task_id']): C.LABELS.index(r['label']) for r in recs}
out = []
for m in D.MODELS:
    ids = lambda s: sorted(k[3] for k in obs if k[0] == m and k[1] == 'none' and k[2] == s)
    P = {s: [obs[m, 'none', s, i] for i in ids(s)] for s in ['train', 'validation', 'test']}
    y = {s: np.array([lab[m, 'none', s, i] for i in ids(s)]) for s in P}
    X = {s: np.stack([C.views(o)['bytes'] for o in P[s]]) for s in P}
    fit = {n: e.fit(X['train'], y['train']) for n, e in C.original.estimators().items()}
    sel = C.original.choose({n: float(np.mean(fit[n].predict(X['validation']) == y['validation'])) for n in fit})
    def pr(s):
        d = {'byte_LR': fit['LR'].predict(X[s]), 'byte_RF': fit['RF'].predict(X[s]), 'frozen': fit[sel].predict(X[s]),
             'position_last': np.array([D.position_rule(o, -1) for o in P[s]]),
             'position_penultimate': np.array([D.position_rule(o, -2) for o in P[s]])}
        return {k: v == y[s] for k, v in d.items()}
    v = {k: float(x.mean()) for k, x in pr('validation').items()}
    t = {k: int(x.sum()) for k, x in pr('test').items()}
    best = max(D.SIZE_ATTACKS, key=lambda k: (v[k], -D.SIZE_ATTACKS.index(k)))
    out.append({'model': m, 'arm': 'none', 'validation_accuracy': v, 'test_correct': t,
                'size_only_best': best, 'size_only_best_correct': t[best]})
    print(m, best, t, flush=True)
Path(__file__).with_name('no-cover-size-best.json').write_text(json.dumps(out, indent=2) + '\n')
