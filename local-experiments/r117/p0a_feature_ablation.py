"""P0-A: Time / position ablation of the frozen live-record attacks.

Exploratory re-analysis after test results are known. It imports the frozen
R110 analyze.py so that the attacks, seeds and selection rules are identical,
and refits every attack under three observation variants:

  full         unchanged features (must reproduce the published counts)
  no_time      all timestamps, gaps, durations and wall time set to constants;
               destinations, order and ciphertext bytes kept
  no_position  absolute/relative position, previous-destination and is-last
               features removed; the task classifier sees per-destination
               counts and byte sums instead of ordered slots; timing kept

Arms: immediate (reference), history sequential, history concurrent.
Attacks refitted per variant: size/destination LR/RF, frozen no-cover
classifier, context removal and joint decoding; timing-only attacks are
dropped in no_time because they have no input left.

Tests (exact McNemar, Holm):
  Family A (8): history arms x 2 models x {full-adaptive vs no_time-adaptive,
                no_time-adaptive vs full size-selected}
  Family B (4): history arms x 2 models, full-adaptive vs no_position-adaptive
"""
import argparse, importlib, sys
from pathlib import Path
import numpy as np
from common_local import (ARM_NAMES, LABELS, MODELS, check_frozen, holm, load, load_records,
                          mcnemar, now, save, write_csv)

VARIANTS = ['full', 'no_time', 'no_position']
CELL_ARMS = ['unmatched', 'gdm_live', 'concurrent']
HISTORY = ['gdm_live', 'concurrent']


def import_frozen(live_dir):
    sys.path.insert(0, str(Path(live_dir) / 'experiment'))
    return importlib.import_module('analyze')


def make_variant(A, variant):
    """Return observe/byte/call_features implementations for one variant."""
    base_observe, base_byte, base_calls = A.observe, A.byte, A.call_features

    def observe(r):
        o = base_observe(r)
        if variant == 'no_time':
            n = len(o['trace'])
            o['start'] = np.arange(n, dtype=float); o['end'] = o['start'] + .5
            o['timing'] = np.zeros((n, 3)); o['wall_seconds'] = 0.
        return o

    def byte(o):
        if variant != 'no_position':
            return base_byte(o)
        x = np.zeros(153)
        for w in o['trace']:
            j = A.SERVICES.index(w['service']); x[112 + j] += 1
            x[2 * j:2 * j + 2] += w['bytes']
        x[-2:] = [len(o['trace']), sum(sum(w['bytes']) for w in o['trace'])]
        return x

    def call_features(o, context=False, med=None):
        x = base_calls(o, context, med)
        if variant == 'no_position':
            x[:, 2] = 0
            if context:
                x[:, 10:18] = 0; x[:, 25:33] = 0
        return x
    return observe, byte, call_features


def run_cell(A, model, arm, obs, yy, ids, variant):
    """Fit and score one model/arm under the currently patched variant."""
    clean, _, _ = A.fit_task(obs['none']['train'], obs['none']['validation'], yy['train'], yy['validation'])
    med = A.medians(obs['none']['train'])
    tr, va, te = [obs[arm][s] for s in ['train', 'validation', 'test']]
    _, bs, _ = A.fit_task(tr, va, yy['train'], yy['validation'])
    pp = {'validation': {}, 'test': {}}
    for split, oset in [('validation', va), ('test', te)]:
        X = np.stack([A.byte(o) for o in oset])
        pp[split]['byte_LR'] = bs['LR'].predict(X); pp[split]['byte_RF'] = bs['RF'].predict(X)
        pp[split]['frozen'] = clean.predict(X)
        if variant != 'no_position':
            for name, off in [('position_last', -1), ('position_penultimate', -2)]:
                pp[split][name] = np.array([A.POSITION.get(o['trace'][off]['service'], 0) if len(o['trace']) >= abs(off) else 0 for o in oset])
    if variant != 'no_time':
        tclf, _, _ = A.fit_task(tr, va, yy['train'], yy['validation'], True)
        fd, ds = A.fit_detector(tr, va, False, med); gth, _ = A.gmm_threshold(tr)
        for split, oset in [('validation', va), ('test', te)]:
            pp[split]['timing_size'] = tclf.predict(np.stack([A.view(o, True) for o in oset]))
            pp[split]['gap_detector_strip'] = A.strip_prediction(oset, [A.probs(o, fd, ds, med) >= ds['threshold'] for o in oset], clean)
            masks = []
            for o in oset:
                m = o['timing'][:, 2] < gth; m[0] = False; masks.append(m)
            pp[split]['label_free_gmm_strip'] = A.strip_prediction(oset, masks, clean)
    ctx, cs = A.fit_detector(tr, va, True, med)
    vc = A.joint_cache(va, ctx, cs, med, clean, [.02, .49, .49]); tc = A.joint_cache(te, ctx, cs, med, clean, [.02, .49, .49])
    grid = [(n, 'MAP', lam) for n in ['LR', 'RF'] for lam in [0, .5, 1, 2, 4]] + [(n, 'marginal', 1) for n in ['LR', 'RF']]
    js = max(grid, key=lambda sp: (sum(A.joint_pred(vc, clean.classes_, sp) == yy['validation']), -grid.index(sp)))
    for split, oset, cache in [('validation', va, vc), ('test', te, tc)]:
        pp[split]['context_strip'] = A.strip_prediction(oset, [A.probs(o, ctx, cs, med) >= cs['threshold'] for o in oset], clean)
        pp[split]['joint_decoding'] = A.joint_pred(cache, clean.classes_, js)
    size = [n for n in A.SIZE if n in pp['validation']]
    names = size + [n for n in A.TIMING if n in pp['validation']]
    sn = max(size, key=lambda n: (sum(pp['validation'][n] == yy['validation']), -size.index(n)))
    an = max(names, key=lambda n: (sum(pp['validation'][n] == yy['validation']), -names.index(n)))
    correct = {n: pp['test'][n] == yy['test'] for n in names}
    return {'size_selected': sn, 'adaptive_selected': an, 'correct': correct,
            'validation': {n: int(sum(pp['validation'][n] == yy['validation'])) for n in names},
            'test': {n: int(sum(v)) for n, v in correct.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--live-dir', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--expect', type=int, default=3000)
    ap.add_argument('--models', nargs='+', default=MODELS, help='subset only for smoke tests')
    ap.add_argument('--published', type=Path, help='attacks-and-tests.json to check the full variant against')
    a = ap.parse_args()
    check_frozen(a.out, __file__)
    A = import_frozen(a.live_dir)
    orig = (A.observe, A.byte, A.call_features)
    records, data = load_records(a.live_dir, expect=a.expect)
    results = {}; rows = []
    for variant in VARIANTS:
        A.observe, A.byte, A.call_features = make_variant(A, variant)
        for model in a.models:
            ids = {s: sorted(r['task_id'] for r in records if r['model'] == model and r['arm'] == 'none' and r['split'] == s)
                   for s in ['train', 'validation', 'test']}
            yy = {s: np.array([LABELS.index(data[model, 'none', i]['label']) for i in ids[s]]) for s in ids}
            obs = {ar: {s: [A.observe(data[model, ar, i]) for i in ids[s]] for s in ids} for ar in ['none'] + CELL_ARMS}
            for arm in CELL_ARMS:
                res = run_cell(A, model, arm, obs, yy, ids, variant); results[variant, model, arm] = res
                for n, c in res['test'].items():
                    rows.append({'variant': variant, 'model': model, 'arm': ARM_NAMES[arm], 'attack': n,
                                 'validation_correct': res['validation'][n], 'test_correct': c,
                                 'selected': 'size' if n == res['size_selected'] else ('adaptive' if n == res['adaptive_selected'] else '')})
                print(variant, model, arm, res['size_selected'], res['test'][res['size_selected']],
                      res['adaptive_selected'], res['test'][res['adaptive_selected']], flush=True)
        A.observe, A.byte, A.call_features = orig

    reproduction = []
    if a.published:
        pub = {(x['model'], x['arm'], x['attack']): x['correct'] for x in load(a.published)['attacks']}
        for model in a.models:
            for arm in CELL_ARMS:
                for n, c in results['full', model, arm]['test'].items():
                    reproduction.append({'model': model, 'arm': arm, 'attack': n, 'published': pub.get((model, arm, n)), 'refit': c,
                                         'match': pub.get((model, arm, n)) == c})
        if not all(r['match'] for r in reproduction):
            print('WARNING: full variant does not reproduce every published count; inspect p0a-reproduction.csv before reading ablations.')

    fam_a, fam_b = [], []
    for model in a.models:
        for arm in HISTORY:
            f, t, p = results['full', model, arm], results['no_time', model, arm], results['no_position', model, arm]
            fa, ta, pa = f['correct'][f['adaptive_selected']], t['correct'][t['adaptive_selected']], p['correct'][p['adaptive_selected']]
            fs = f['correct'][f['size_selected']]
            fam_a.append({'model': model, 'arm': ARM_NAMES[arm], 'contrast': 'full_adaptive - no_time_adaptive', **mcnemar(fa, ta)})
            fam_a.append({'model': model, 'arm': ARM_NAMES[arm], 'contrast': 'no_time_adaptive - full_size_selected', **mcnemar(ta, fs)})
            fam_b.append({'model': model, 'arm': ARM_NAMES[arm], 'contrast': 'full_adaptive - no_position_adaptive', **mcnemar(fa, pa)})
    holm(fam_a); holm(fam_b)
    write_csv(a.out / 'p0a-attacks.csv', rows)
    write_csv(a.out / 'p0a-tests.csv', [dict(family='A', **r) for r in fam_a] + [dict(family='B', **r) for r in fam_b])
    if reproduction:
        write_csv(a.out / 'p0a-reproduction.csv', reproduction)
    save(a.out / 'p0a-summary.json', {'utc': now(), 'role': 'exploratory post-hoc ablation; not confirmatory',
                                      'reproduces_published': all(r['match'] for r in reproduction) if reproduction else None,
                                      'family_A': fam_a, 'family_B': fam_b})


if __name__ == '__main__':
    main()
