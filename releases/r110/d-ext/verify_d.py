"""Independent arithmetic check of the saved D results (no model fitting).

Re-derives from results/*.json: validation-based attack selection and tie rules,
exact McNemar p-values from discordant counts, both Holm families, the
pre-registered interpretation rule, the R109 gate, and result-file hashes.
"""
import hashlib, json
from pathlib import Path
from scipy.stats import binomtest

R = Path(__file__).resolve().parent / 'results'
SIZE = ['byte_LR', 'byte_RF', 'frozen', 'position_last', 'position_penultimate']
ORDER = SIZE + ['timing_size', 'b1_strip', 'ctx_strip', 'joint']
load = lambda n: json.loads((R / n).read_text())
checks = []


def check(name, ok):
    checks.append((name, bool(ok)))
    assert ok, name


fin = load('finished.json')
for name, digest in fin['files'].items():
    check('hash ' + name, hashlib.sha256((R / name).read_bytes()).hexdigest() == digest)
check('gate 20/20', len(load('gate.json')) == 20 and all(g['ok'] for g in load('gate.json')))
cells = load('cells.json')
check('30 cells', len(cells) == 30)
for c in cells:
    v = c['validation_accuracy']
    s = max(SIZE, key=lambda k: (v[k], -SIZE.index(k)))
    a = max(ORDER, key=lambda k: (v[k], -ORDER.index(k)))
    check('size selection ' + c['model'] + c['arm'] + c['variant'], s == c['size_only_best'])
    check('adaptive selection ' + c['model'] + c['arm'] + c['variant'], a == c['adaptive_best'])
    check('size count', c['test_correct'][s] == c['size_only_best_correct'])
    check('adaptive count', c['test_correct'][a] == c['adaptive_best_correct'])
    check('adaptive >= size on validation', v[a] >= v[s])
for fam, var in [('primary', 'C3b_gap_duration'), ('secondary', 'C3c_position')]:
    rows = load(fam + '.json')
    check(fam + ' has 10', len(rows) == 10 and all(r['variant'] == var for r in rows))
    for r in rows:
        c = next(x for x in cells if x['model'] == r['model'] and x['arm'] == r['arm'] and x['variant'] == var)
        n = r['condition_only'] + r['reference_only']
        p = binomtest(r['condition_only'], n, .5).pvalue if n else 1.
        check('p ' + fam + r['model'] + r['arm'], abs(p - r['p_raw']) < 1e-12)
        check('diff ' + fam, abs(100 * (r['condition_only'] - r['reference_only']) / 120 - r['difference_pp']) < 1e-9)
        check('diff matches counts', round(1.2 * r['difference_pp']) == c['adaptive_best_correct'] - c['size_only_best_correct'])
    order = sorted(range(10), key=lambda i: rows[i]['p_raw'])
    run = 0.
    for k, i in enumerate(order):
        run = max(run, min(1., (10 - k) * rows[i]['p_raw']))
        check('holm ' + fam, abs(run - rows[i]['p_holm']) < 1e-12)
    met = sum(r['difference_pp'] * 1.2 >= 12 - 1e-9 and r['p_holm'] < .05 for r in rows)
    print(f'{fam}: cells meeting >=12/120 and Holm<.05: {met}/10 ->',
          'does NOT withstand' if met >= 5 else 'withstands tested adaptive attacks (rule not met)')
print(f'ALL {len(checks)} CHECKS PASS')
