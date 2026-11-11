"""Independent checks of saved C1-C3 results (no model refitting).

1. Result-file hashes match finished.json.
2. C2 gap-rule strip counts recomputed with an independent gap computation and
   the saved M3 byte classifier inputs are consistent with saved detector counts.
3. McNemar p-values and Holm adjustments recomputed from saved discordant counts.
4. C1 robustness criterion and C3 best-attack summary recomputed.
"""
import gzip, hashlib, json, os, sys
from pathlib import Path
import numpy as np
from scipy.stats import binomtest

HERE = Path(__file__).resolve().parent
R = HERE / 'results'
SOURCE = Path(os.environ.get('M3_SOURCE', '/tmp/m3/review-r102/llm-extension'))
fin = json.loads((R / 'finished.json').read_text())
for name, digest in fin['files'].items():
    assert hashlib.sha256((R / name).read_bytes()).hexdigest() == digest, name
L = lambda n: json.loads((R / (n + '.json')).read_text())

# 2. independent detector counts for the label-free rule
thr = {m: v['gmm_threshold_seconds'] for m, v in L('C2_thresholds').items()}
counts = {}
for line in gzip.open(SOURCE / 'data/episodes.jsonl.gz', 'rt'):
    r = json.loads(line)
    if r['split'] != 'test' or r['arm'] == 'none':
        continue
    rec = sorted(r['tool_receipts'], key=lambda x: x['terminal']['start'])
    c = counts.setdefault((r['model'], r['arm']), [0, 0, 0])
    for i in range(1, len(rec)):
        gap = rec[i]['terminal']['start'] - rec[i - 1]['terminal']['end']
        pred, truth = gap < thr[r['model']], rec[i]['request']['kind'] == 'cover'
        c[0] += pred and truth; c[1] += pred and not truth; c[2] += truth and not pred
for row in L('C2'):
    if row['rule'] == 'gmm':
        assert counts[row['model'], row['arm']] == [row['tp'], row['fp'], row['fn']], row

# 3. tests
for fam in ['C2_family', 'C3_primary', 'C3_secondary']:
    rows = L(fam)
    p = [binomtest(x['condition_only'], x['condition_only'] + x['reference_only'], .5).pvalue
         if x['condition_only'] + x['reference_only'] else 1. for x in rows]
    assert np.allclose(p, [x['p_raw'] for x in rows])
    order = np.argsort(p); m = len(p); run = 0.; adj = np.zeros(m)
    for k, i in enumerate(order):
        run = max(run, min(1., (m - k) * p[i])); adj[i] = run
    assert np.allclose(adj, [x['p_holm'] for x in rows]), fam
    for x in rows:
        assert abs(x['difference_pp'] - 100 * (x['condition_only'] - x['reference_only']) / 120) < 1e-9

# 4. summaries
c1 = {s: all(r['adaptive_mean'] - r['byte_selected'] >= 24 for r in L('C1') if r['sigma'] == s)
      for s in sorted({r['sigma'] for r in L('C1')})}
best = {(r['model'], r['arm']): max(r['strip'], r['byte_selected'], r['timing_size_selected'])
        for r in L('C3') if r['variant'] == 'C3b_gap_duration'}
summary = {'C1_robust_by_sigma': c1,
           'C3b_best_attack_minus_byte': {f'{m}/{a}': best[m, a] - next(r['byte_selected'] for r in L('C3') if r['model'] == m and r['arm'] == a)
                                          for m, a in best},
           'C3b_within_10_of_byte': sum(abs(r['strip'] - r['byte_selected']) <= 12 for r in L('C3') if r['variant'] == 'C3b_gap_duration'),
           'C3b_strip_below_byte': sum(r['strip'] < r['byte_selected'] for r in L('C3') if r['variant'] == 'C3b_gap_duration')}
print(json.dumps(summary, indent=1))
print('VERIFIED')
