"""Record the exact analysis code before any test scoring.

Writes <out>/freeze.json and a copy under freezes/ for committing to Git.
Each p0*.py script refuses to run unless its bytes match this receipt.
"""
import argparse, platform, sys, json
from pathlib import Path
from common_local import load, now, save, sha

HERE = Path(__file__).resolve().parent
SCRIPTS = sorted(p.name for p in HERE.iterdir() if p.is_file() and p.suffix in {'.py','.md'})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--live-dir', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--published', required=True, type=Path)
    ap.add_argument('--record-only-dir', type=Path,
                    default=HERE.parents[1] / 'releases/r116/artifact/record-only/experiment')
    ap.add_argument('--no-copy', action='store_true', help='smoke tests: do not write freezes/ copy')
    a = ap.parse_args()
    receipt = a.out / 'freeze.json'
    if receipt.exists():
        sys.exit(f'{receipt} already exists. Use a new --out directory for a new frozen version.')
    import numpy, scipy, sklearn
    deps = {'analyze.py': a.live_dir / 'experiment/analyze.py',
            'live_common.py': a.live_dir / 'experiment/common.py',
            'published-attacks.json':a.published,
            'record-only-verified.json':a.record_only_dir.parent/'verification/no-call-verified.json',
            'no_call_windows.py': a.record_only_dir / 'no_call_windows.py',
            'protocol_record_events.py': a.record_only_dir / 'protocol_record_events.py'}
    for k, p in deps.items():
        if not p.exists():
            sys.exit(f'Missing dependency {p}')
    prior = a.live_dir / 'analysis/results.json'
    seal = a.out / 'LOCAL-ONLY-input-manifest.json'
    if not seal.is_file():
        sys.exit('Prepare and verify the immutable local input manifest first')
    inputs = {n:a.live_dir/'analysis'/n for n in ['results.json','predictions.csv','validation-selection.json']}
    x = {'utc': now(), 'files': {s: sha(HERE / s) for s in SCRIPTS},
         'dependencies': {k: sha(p) for k, p in deps.items()},
         'dependency_paths': {k:str(p.resolve()) for k,p in deps.items()},
         'saved_inputs': {k:sha(p) for k,p in inputs.items()},
         'saved_input_paths': {k:str(p.resolve()) for k,p in inputs.items()},
         'input_seal_sha256':sha(seal),
         'analysis_plan_sha256':sha(HERE/'PROTOCOL.md'),
         'existing_analysis_results_sha256': sha(prior) if prior.exists() else None,
         'python': platform.python_version(),
         'versions': {'numpy': numpy.__version__, 'scipy': scipy.__version__, 'sklearn': sklearn.__version__},
         'status': 'EXPLORATORY, post-hoc; frozen before scoring these new analyses'}
    save(receipt, x)
    print('Wrote', receipt)
    if not a.no_copy:
        copy = HERE / 'freezes' / 'freeze.json'
        save(copy, x)
        print('Wrote', copy, '- commit and push it before running any p0*.py script.')


if __name__ == '__main__':
    main()
