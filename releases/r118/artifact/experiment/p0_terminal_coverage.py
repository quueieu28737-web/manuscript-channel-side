"""P0-T: Is the requested business action left uncovered at the end of the trace?

Exploratory, post-hoc diagnostic on existing saved predictions. No refitting.

For every test fixture and arm it determines, from the private wire trace:
  * whether the real chain issued a business action at all;
  * whether any controller cover call (or, for shadow, any shadow business
    action) started after that real business action;
  * whether the real business action is the chronologically last tool call.
It then stratifies every saved attack's test accuracy by these strata.

Inputs (read only):
  <live-dir>/private-run/formal-{none,cover}-v1/episodes/*/result.json
  <live-dir>/analysis/predictions.csv
  <live-dir>/analysis/validation-selection.json
Outputs: <out>/p0t-*.{json,csv}
"""
import argparse, collections, sys
from pathlib import Path
from scipy.stats import fisher_exact
from common_local import (ARMS, ARM_NAMES, BUSINESS, LABELS, MODELS, check_frozen, load,
                          load_records, now, read_csv, save, write_csv)


def strata(r):
    tr = sorted(r['wire_trace'], key=lambda c: (c['start_ns'], c['end_ns']))
    real_biz = [c for c in tr if c['role'] == 'real' and c['kind'] == 'honest' and c['operation'] in BUSINESS]
    if not real_biz:
        return {'real_business_call': 0, 'covered_after': None, 'real_action_last': 0}
    b = real_biz[-1]
    if r['arm'] == 'shadow':
        after = [c for c in tr if c['role'] == 'shadow' and c['operation'] in BUSINESS and c['start_ns'] > b['start_ns']]
    else:
        after = [c for c in tr if c['kind'] == 'cover' and c['start_ns'] > b['start_ns']]
    return {'real_business_call': 1, 'covered_after': int(bool(after)),
            'real_action_last': int(tr[-1] is b)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--live-dir', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args()
    check_frozen(a.out, __file__)
    recs, data = load_records(a.live_dir)
    preds = read_csv(a.live_dir / 'analysis/predictions.csv')
    sel = {(s['model'], s['arm']): s for s in load(a.live_dir / 'analysis/validation-selection.json')}

    per_fixture = []; st = {}
    for r in recs:
        if r['split'] != 'test':
            continue
        s = strata(r); st[r['model'], r['arm'], r['task_id']] = s
        per_fixture.append({'model': r['model'], 'arm': r['arm'], 'task_id': r['task_id'], **s})

    by_attack = collections.defaultdict(list)
    for p in preds:
        key = (p['model'], p['arm'], int(p['task_id']))
        by_attack[p['model'], p['arm'], p['attack']].append((key, int(p['prediction']) == int(p['truth'])))

    cells = []; attacks = []
    for model in MODELS:
        for arm in ARMS[1:]:
            fx = [v for (m, ar, _), v in st.items() if m == model and ar == arm]
            n = len(fx)
            cell = {'model': model, 'arm': ARM_NAMES[arm], 'n': n,
                    'no_real_business_call': sum(1 for v in fx if not v['real_business_call']),
                    'uncovered_terminal': sum(1 for v in fx if v['covered_after'] == 0),
                    'covered_terminal': sum(1 for v in fx if v['covered_after'] == 1),
                    'real_action_is_last_call': sum(v['real_action_last'] for v in fx)}
            s = sel.get((model, arm), {})
            cell['size_selected'] = s.get('size_selected'); cell['adaptive_selected'] = s.get('adaptive_selected')
            cells.append(cell)
            for (m, ar, att), rows in by_attack.items():
                if m != model or ar != arm:
                    continue
                grp = {'uncovered': [], 'covered': [], 'no_business': []}
                for key, ok in rows:
                    v = st[key]
                    g = 'no_business' if not v['real_business_call'] else ('covered' if v['covered_after'] else 'uncovered')
                    grp[g].append(ok)
                u, c = grp['uncovered'], grp['covered']
                table = [[sum(u), len(u) - sum(u)], [sum(c), len(c) - sum(c)]]
                p = float(fisher_exact(table)[1]) if u and c else None
                attacks.append({'model': model, 'arm': ARM_NAMES[arm], 'attack': att,
                                'selected': 'size+adaptive' if att == cell['size_selected'] == cell['adaptive_selected'] else ('size' if att == cell['size_selected'] else ('adaptive' if att == cell['adaptive_selected'] else '')),
                                'correct_total': sum(ok for _, ok in rows), 'n': len(rows),
                                'uncovered_correct': sum(u), 'uncovered_n': len(u),
                                'covered_correct': sum(c), 'covered_n': len(c),
                                'no_business_correct': sum(grp['no_business']), 'no_business_n': len(grp['no_business']),
                                'fisher_p_descriptive': p})
    write_csv(a.out / 'LOCAL-ONLY-p0t-per-fixture.csv', per_fixture)
    write_csv(a.out / 'p0t-attack-strata.csv', attacks)
    save(a.out / 'p0t-summary.json', {'utc': now(), 'role': 'exploratory association, not a causal placement intervention; no refit; Fisher p descriptive only',
                                      'terminal_definition':'last actual honest business operation, not necessarily requested/correct; after means later start, not completion',
                                      'cells': cells})
    for c in cells:
        print(c)


if __name__ == '__main__':
    main()
