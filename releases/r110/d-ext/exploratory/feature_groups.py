"""POST-HOC EXPLORATORY (run after the frozen D results were saved): which context-detector
inputs carry call-level separability of timing-matched decoys (C3b, C3c)? Refits the D2a
detector with feature groups removed and reports test AUROC only. Not a test of any claim."""
import json, sys
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import d_ext as D
C = D.C
GROUPS = {'all': [], 'no_timing': [0, 1, 18, 19, 20, 21, 22], 'no_size': [23, 24],
          'no_position_context': list(range(10, 18)) + list(range(25, 34)) + [2],
          'timing_only': [i for i in range(34) if i not in (0, 1, 18, 19, 20, 21, 22)]}
import gzip
recs = [json.loads(l) for l in gzip.open(C.SOURCE / 'data/episodes.jsonl.gz', 'rt')]
obs = {(r['model'], r['arm'], r['split'], r['task_id']): C.observe(r) for r in recs}
out = []
for model in D.MODELS:
    ids = lambda a, s: sorted(k[3] for k in obs if k[0] == model and k[1] == a and k[2] == s)
    parts = {s: {a: [obs[model, a, s, i] for i in ids(a, s)] for a in D.ARMS} for s in ('train', 'validation', 'test')}
    tr = parts['train']
    hg = np.concatenate([o['timing'][1:, 2] for o in tr['none']])
    hd = {'__all__': list(np.concatenate([o['timing'][1:, 1] for o in tr['none']]))}
    for o in tr['none']:
        for i in range(1, len(o['trace'])): hd.setdefault(o['trace'][i]['service'], []).append(float(o['timing'][i, 1]))
    gpos = {}
    for o in tr['none']:
        for i in range(1, len(o['trace'])): gpos.setdefault(i, []).append(float(o['timing'][i, 2]))
    gpos = {k: np.array(v) for k, v in gpos.items()}
    coh = {}
    for variant, wd in [('C3a_gap', False), ('C3b_gap_duration', True)]:
        rng = np.random.default_rng([C.PLAN['C3_timing_matched']['seed'], int(wd), D.MODELS.index(model)])
        coh[variant] = [{a: [C.matched(o, hg, hd, rng, wd) for o in parts[s][a]] for a in D.ARMS} for s in ('train', 'validation', 'test')]
    rng = np.random.default_rng([D.C3C_SEED, D.MODELS.index(model)])
    coh['C3c_position'] = [{a: [D.matched_pos(o, gpos, hg, hd, rng) for o in parts[s][a]] for a in D.ARMS} for s in ('train', 'validation', 'test')]
    for variant in ('C3b_gap_duration', 'C3c_position'):
        mtr, _, mte = coh[variant]
        trl = [o for a in D.ARMS for o in mtr[a]]; tel = [o for a in D.COVER_ARMS for o in mte[a]]
        med = D.honest_duration_medians(trl)
        Xt = np.concatenate([D.ctx_features(o, med) for o in trl]); yt = np.concatenate([o['cover'] for o in trl])
        Xe = np.concatenate([D.ctx_features(o, med) for o in tel]); ye = np.concatenate([o['cover'] for o in tel])
        keep_e = Xe[:, 2] == 0; keep_t = Xt[:, 2] == 0
        for g, drop in GROUPS.items():
            cols = [i for i in range(34) if i not in drop]
            est = D.ctx_models()['RF'].fit(Xt[keep_t][:, cols], yt[keep_t])
            auc = roc_auc_score(ye[keep_e], est.predict_proba(Xe[keep_e][:, cols])[:, 1])
            out.append({'model': model, 'variant': variant, 'group': g, 'test_auroc_non_first_calls': float(auc)})
            print(model, variant, g, round(auc, 3), flush=True)
Path(__file__).with_name('feature-groups.json').write_text(json.dumps(out, indent=2) + '\n')
