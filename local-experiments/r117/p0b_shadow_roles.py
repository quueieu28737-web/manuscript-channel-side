"""P0-B: Real-chain role and exact task-label diagnostics for the shadow arm.

Exploratory, post-hoc, no refitting. Uses the saved test outputs of the frozen
analysis:
  analysis/results.json            shadow_chain_diagnostics (per test fixture)
  analysis/predictions.csv         per-fixture task predictions for every attack
  private-run/.../result.json      label, shadow_schedule (start order, shadow label)

Reports per model:
  R1  chain-level role accuracy of the frozen role selector (first chain judged
      real iff p>=.5) against a start-order baseline fitted on TRAIN only;
      exact McNemar on the test fixtures
  R2  exact real-chain recovery (partition and selection both right), by start order
  T1  for each attack, exact accuracy on matching- and different-label fixtures
      (replaces the [49,70]/99 aggregate bound)
  T2  on different-label fixtures, how often the prediction equals the real label
      versus the shadow label; a role-blind attacker has these equal in expectation
      (exact sign test)
Holm is applied separately within R1 (2 tests) and within T2 (selected attacks, 2 tests).
"""
import argparse, collections
from pathlib import Path
from scipy.stats import binomtest
from common_local import (LABELS, MODELS, check_frozen, holm, load, load_records, mcnemar, now,
                          read_csv, save, write_csv)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--live-dir', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args()
    check_frozen(a.out, __file__)
    recs, data = load_records(a.live_dir)
    res = load(a.live_dir / 'analysis/results.json')
    diag = {(d['model'], d['task_id']): d for d in res['shadow_chain_diagnostics']}
    sel = {(s['model'], s['arm']): s for s in load(a.live_dir / 'analysis/validation-selection.json')}
    preds = collections.defaultdict(dict)
    for p in read_csv(a.live_dir / 'analysis/predictions.csv'):
        if p['arm'] == 'shadow':
            preds[p['model'], p['attack']][int(p['task_id'])] = int(p['prediction'])

    role_tests, order_rows, label_rows, t2 = [], [], [], []
    for model in MODELS:
        sh = {s: [r for r in recs if r['model'] == model and r['arm'] == 'shadow' and r['split'] == s] for s in ['train', 'test']}
        real_first_train = [not r['shadow_schedule']['shadow_first'] for r in sh['train']]
        majority_real_first = sum(real_first_train) * 2 >= len(real_first_train)
        test = sorted(sh['test'], key=lambda r: r['task_id'])
        real_first = [not r['shadow_schedule']['shadow_first'] for r in test]
        sel_first = [diag[model, r['task_id']]['first_chain_real_probability'] >= .5 for r in test]
        selector_ok = [x == y for x, y in zip(sel_first, real_first)]
        baseline_ok = [y == majority_real_first for y in real_first]
        role_tests.append({'model': model, 'test': 'selector role accuracy - start-order baseline',
                           'selector_correct': sum(selector_ok), 'baseline_correct': sum(baseline_ok),
                           'baseline_rule': 'always real-first' if majority_real_first else 'always shadow-first',
                           'selector_agrees_with_start_order': sum(1 for x in sel_first if x),
                           **mcnemar(selector_ok, baseline_ok)})
        for first in [True, False]:
            sub = [r for r, f in zip(test, real_first) if f == first]
            order_rows.append({'model': model, 'stratum': 'real-first' if first else 'shadow-first', 'n': len(sub),
                               'exact_partition': sum(diag[model, r['task_id']]['exact_partition'] for r in sub),
                               'exact_real_chain': sum(diag[model, r['task_id']]['exact_real_chain'] for r in sub)})
        real_lab = {r['task_id']: LABELS.index(r['label']) for r in test}
        shadow_lab = {r['task_id']: LABELS.index(r['shadow_schedule']['decoy_action']) for r in test}
        s = sel.get((model, 'shadow'), {})
        for (m, attack), pr in preds.items():
            if m != model:
                continue
            same = [t for t in real_lab if real_lab[t] == shadow_lab[t]]
            diff = [t for t in real_lab if real_lab[t] != shadow_lab[t]]
            hit_real = sum(pr[t] == real_lab[t] for t in diff); hit_shadow = sum(pr[t] == shadow_lab[t] for t in diff)
            row = {'model': model, 'attack': attack,
                   'selected': 'size+adaptive' if attack == s.get('size_selected') == s.get('adaptive_selected') else
                   ('size' if attack == s.get('size_selected') else ('adaptive' if attack == s.get('adaptive_selected') else '')),
                   'matching_n': len(same), 'matching_correct': sum(pr[t] == real_lab[t] for t in same),
                   'different_n': len(diff), 'different_correct': hit_real, 'different_pred_is_shadow': hit_shadow,
                   'different_neither': len(diff) - hit_real - hit_shadow,
                   'sign_test_p_raw': float(binomtest(hit_real, hit_real + hit_shadow, .5).pvalue) if hit_real + hit_shadow else 1.}
            label_rows.append(row)
            if attack == s.get('adaptive_selected'):
                t2.append({'model': model, 'attack': attack, 'p_raw': row['sign_test_p_raw'],
                           'real': hit_real, 'shadow': hit_shadow})
    holm(role_tests); holm(t2)
    write_csv(a.out / 'p0b-role-tests.csv', role_tests)
    write_csv(a.out / 'p0b-start-order.csv', order_rows)
    write_csv(a.out / 'p0b-task-labels.csv', label_rows)
    save(a.out / 'p0b-summary.json', {'utc': now(), 'role': 'exploratory post-hoc; no refit', 'R1': role_tests,
                                      'R2': order_rows, 'T2_selected': t2})
    for r in role_tests + order_rows + t2:
        print(r)


if __name__ == '__main__':
    main()
