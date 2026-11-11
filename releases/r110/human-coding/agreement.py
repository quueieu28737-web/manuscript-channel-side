"""Compare an independent coder's sheets with the author key.

Usage: python agreement.py CODER_DIR
CODER_DIR contains the coder's sheet-A-settings.csv, sheet-B-interventions.csv
and sheet-C-transfer.csv. Writes agreement.json and disagreements.csv to CODER_DIR.
B2/B3 are compared only where both coders put the setting in query_workflow_privacy.
"""
import csv, json, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHEETS = {'A': 'sheet-A-settings.csv', 'B': 'sheet-B-interventions.csv', 'C': 'sheet-C-transfer.csv'}
ID = {'A': 'setting_id', 'B': 'setting_id', 'C': 'id'}


def kappa(pairs):
    n = len(pairs)
    if n == 0:
        return None
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n / n
    return 1. if pe == 1 else (po - pe) / (1 - pe)


def main(coder_dir):
    coder_dir = Path(coder_dir)
    key = {}
    for r in csv.DictReader((HERE / 'author-key.csv').open()):
        key[r['sheet'], r['id'], r['field']] = r['author_code'].strip()
    coder = {}
    for s, name in SHEETS.items():
        for r in csv.DictReader((coder_dir / name).open()):
            for f, v in r.items():
                if f[:2] in ('A1', 'A2', 'B1', 'B2', 'B3', 'C1'):
                    coder[s, r[ID[s]], f] = (v or '').strip()
    fields, disagreements = {}, []
    for (s, i, f), a in key.items():
        c = coder.get((s, i, f), '')
        if f in ('B2_protected_condition_adaptation', 'B3_original_task_utility_same_intervention'):
            if key[s, i, 'B1_intervention_purpose'] != 'query_workflow_privacy' or \
                    coder.get((s, i, 'B1_intervention_purpose')) != 'query_workflow_privacy':
                continue
        fields.setdefault(f, []).append((a, c))
        if a != c:
            disagreements.append({'sheet': s, 'id': i, 'field': f, 'author': a, 'coder': c,
                                  'resolution': '', 'final': '', 'reason': ''})
    summary = {f: {'n': len(p), 'agree': sum(a == b for a, b in p), 'cohen_kappa': kappa(p),
                   'coder_unclear_or_blank': sum(b in ('', 'unclear') for _, b in p)} for f, p in fields.items()}
    a_den = sorted(i for (s, i, f), v in key.items() if f == 'B1_intervention_purpose' and v == 'query_workflow_privacy')
    c_den = sorted(i for (s, i, f), v in coder.items() if f == 'B1_intervention_purpose' and v == 'query_workflow_privacy')
    summary['privacy_denominator'] = {'author': a_den, 'coder': c_den, 'identical': a_den == c_den}
    (coder_dir / 'agreement.json').write_text(json.dumps(summary, indent=2) + '\n')
    with (coder_dir / 'disagreements.csv').open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['sheet', 'id', 'field', 'author', 'coder', 'resolution', 'final', 'reason'])
        w.writeheader(); w.writerows(disagreements)
    print(json.dumps(summary, indent=2))
    print(len(disagreements), 'disagreements written to', coder_dir / 'disagreements.csv')


if __name__ == '__main__':
    main(sys.argv[1])
