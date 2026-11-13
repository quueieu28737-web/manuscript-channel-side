"""Record the exact analysis code before any test scoring.

Writes <out>/freeze.json and a copy under freezes/ for committing to Git.
Each p0*.py script refuses to run unless its bytes match this receipt.
"""
import argparse, platform, sys
from pathlib import Path
from common_local import load, now, save, sha

HERE = Path(__file__).resolve().parent
SCRIPTS = ['common_local.py', 'p0_terminal_coverage.py', 'p0a_feature_ablation.py',
           'p0b_shadow_roles.py', 'p0c_record_only_strong.py']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--live-dir', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--record-only-dir', type=Path,
                    default=HERE.parents[1] / 'releases/r116/artifact/record-only/experiment')
    ap.add_argument('--no-copy', action='store_true', help='smoke tests: do not write freezes/ copy')
    a = ap.parse_args()
    receipt = a.out / 'freeze.json'
    if receipt.exists():
        sys.exit(f'{receipt} already exists. Use a new --out directory for a new frozen version.')
    import numpy, scipy, sklearn
    deps = {'analyze.py': a.live_dir / 'experiment/analyze.py',
            'no_call_windows.py': a.record_only_dir / 'no_call_windows.py',
            'protocol_record_events.py': a.record_only_dir / 'protocol_record_events.py'}
    for k, p in deps.items():
        if not p.exists():
            sys.exit(f'Missing dependency {p}')
    prior = a.live_dir / 'analysis/results.json'
    x = {'utc': now(), 'files': {s: sha(HERE / s) for s in SCRIPTS},
         'dependencies': {k: sha(p) for k, p in deps.items()},
         'existing_analysis_results_sha256': sha(prior) if prior.exists() else None,
         'python': platform.python_version(),
         'versions': {'numpy': numpy.__version__, 'scipy': scipy.__version__, 'sklearn': sklearn.__version__},
         'status': 'EXPLORATORY, post-hoc; frozen before scoring these new analyses'}
    save(receipt, x)
    print('Wrote', receipt)
    if not a.no_copy:
        copy = HERE / 'freezes' / f'freeze-{x["utc"][:19].replace(":", "")}.json'
        save(copy, x)
        print('Wrote', copy, '- commit and push it before running any p0*.py script.')


if __name__ == '__main__':
    main()
