"""Shared helpers for the R117 local diagnostics.

These scripts only read existing local outputs of the R110 live-timing study
(private-run/ episodes and analysis/). They never call a model, start a
collector or modify the source directories.
"""
import csv, datetime, hashlib, json, sys
from pathlib import Path

from scipy.stats import binomtest

MODELS = ['qwen3:8b', 'llama3.1:8b']
ARMS = ['none', 'unmatched', 'gdm_live', 'concurrent', 'shadow']
ARM_NAMES = {'none': 'No cover', 'unmatched': 'Immediate', 'gdm_live': 'History, sequential',
             'concurrent': 'History, concurrent', 'shadow': 'Planner shadow'}
LABELS = ['refund', 'address_update', 'escalation', 'replacement', 'cancellation', 'receipt']
BUSINESS = set(LABELS)
RUNS = ['formal-none-v1', 'formal-cover-v1']


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def save(p, x):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def write_csv(p, rows):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        p.write_text('', encoding='utf-8'); return
    with p.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def read_csv(p):
    with Path(p).open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def episode_paths(live_dir, runs=RUNS):
    paths = []
    for run in runs:
        paths += sorted((Path(live_dir) / 'private-run' / run / 'episodes').glob('*/result.json'))
    return paths


def load_records(live_dir, runs=RUNS, expect=3000):
    recs = [load(p) for p in episode_paths(live_dir, runs)]
    data = {(r['model'], r['arm'], r['task_id']): r for r in recs}
    if expect is not None and (len(data) != expect or len(recs) != expect):
        sys.exit(f'Expected {expect} unique episodes, found {len(data)}; check --live-dir.')
    return recs, data


def mcnemar(a, b):
    """Exact two-sided paired test on boolean vectors a (condition) and b (reference)."""
    plus = int(sum(1 for x, y in zip(a, b) if x and not y))
    minus = int(sum(1 for x, y in zip(a, b) if y and not x))
    p = float(binomtest(plus, plus + minus, .5).pvalue) if plus + minus else 1.
    return {'condition_only': plus, 'reference_only': minus,
            'difference_pp': 100. * (plus - minus) / len(a), 'p_raw': p, 'n': len(a)}


def holm(rows, key='p_raw', out='p_holm'):
    last = 0.
    for rank, i in enumerate(sorted(range(len(rows)), key=lambda j: rows[j][key])):
        last = max(last, min(1., rows[i][key] * (len(rows) - rank)))
        rows[i][out] = last
    return rows


def check_frozen(out_dir, script):
    """Check the complete frozen code/dependency set, and refuse duplicate starts."""
    receipt = Path(out_dir) / 'freeze.json'
    if not receipt.exists():
        sys.exit(f'Missing {receipt}. Run freeze.py before any test scoring.')
    frozen = load(receipt)
    for name, expected in frozen['files'].items():
        p = Path(script).resolve().parent / name
        if not p.is_file() or sha(p) != expected:
            sys.exit(f'Frozen code changed: {name}')
    for name, p in frozen['dependency_paths'].items():
        if sha(p) != frozen['dependencies'][name]:
            sys.exit(f'Frozen dependency changed: {name}')
    for name, p in frozen['saved_input_paths'].items():
        if sha(p) != frozen['saved_inputs'][name]:
            sys.exit(f'Existing analysis input changed: {name}')
    import numpy, scipy, sklearn
    actual = {'numpy':numpy.__version__, 'scipy':scipy.__version__, 'sklearn':sklearn.__version__}
    if actual != frozen['versions']:
        sys.exit(f'Runtime versions changed: {actual}')
    seal = Path(out_dir) / 'LOCAL-ONLY-input-manifest.json'
    if sha(seal) != frozen['input_seal_sha256']:
        sys.exit('Private input seal changed')
    if not (Path(out_dir)/'freeze-remote-readback.json').is_file():
        sys.exit('Frozen code/plan must be pushed and independently read back before scoring')
    name = Path(script).stem
    marker = Path(out_dir)/(name+'-started.json')
    with marker.open('x', encoding='utf-8') as f:
        json.dump({'event':'STARTED','utc':now(),'script':name,'freeze_sha256':sha(receipt)},f)
    return frozen
