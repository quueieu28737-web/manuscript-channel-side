"""Conditional prospective planning from saved R98 predictions, not new evidence.

The task-weighted paired accuracy contrast has cluster influence S_j - d*n_j.
We estimate its asymptotic effective SD as sd(S_j-d*n_j)/mean(n_j), then use
the two-sided normal-approximation sample-size equation. This is NOT exact
power for the original session-sign permutation test. It conditions on the
saved fitted predictors and pilot workload. No models or remote APIs run.
"""
from pathlib import Path
from statistics import NormalDist
import argparse
import hashlib
import json
import math

import numpy as np


def analyze(root):
    prediction_path = root / 'revision-preview/r98-feedback-interventions/analysis/local-formal-v1/recognition/predictions.json'
    plan_path = root / 'revision-preview/r98-feedback-interventions/experiment/frozen-collection/analysis-plan.json'
    predictions = json.loads(prediction_path.read_text(encoding='utf-8'))
    rng = np.random.default_rng(1051111)
    normal = NormalDist()
    # Reuse bootstrap indices across contrasts to preserve their pilot pairing.
    bootstrap_indices = rng.integers(0, 20, size=(50000, 20))
    rows = []
    for model in ['qwen3:8b', 'llama3.1:8b']:
        for learner in ['LR', 'kFP']:
            def find(arm, phase):
                selected = [p for p in predictions if p['key'] == [model, arm, phase, 'M', learner, 'refit']]
                assert len(selected) == 1
                return selected[0]

            full = find('serial_full', 'post_ticket')
            for contrast, comparison in [
                ('full_minus_projected', find('serial_projected', 'post_ticket')),
                ('post_minus_prefix', find('serial_full', 'prefix')),
            ]:
                for key in ['units', 'session', 'truth']:
                    assert full[key] == comparison[key]
                session = np.asarray(full['session'])
                truth = np.asarray(full['truth'])
                a = (np.asarray(full['prediction']) == truth).astype(int)
                b = (np.asarray(comparison['prediction']) == truth).astype(int)
                difference = a - b
                ids = sorted(set(session))
                counts = np.asarray([np.sum(session == s) for s in ids])
                sums = np.asarray([np.sum(difference[session == s]) for s in ids])
                assert len(ids) == 20 and int(counts.sum()) == 120
                observed_difference = float(sums.sum() / counts.sum())
                residual = sums - observed_difference * counts
                effective_sd = float(residual.std(ddof=1) / counts.mean())
                boot_counts = counts[bootstrap_indices]
                boot_sums = sums[bootstrap_indices]
                boot_d = boot_sums.sum(axis=1) / boot_counts.sum(axis=1)
                boot_sd = (boot_sums - boot_d[:, None] * boot_counts).std(axis=1, ddof=1) / boot_counts.mean(axis=1)
                upper_sd = float(np.quantile(boot_sd, 0.95))

                def approximate_n(alpha, sd):
                    return math.ceil(((normal.inv_cdf(1-alpha/2) + normal.inv_cdf(.8)) * sd / .10) ** 2)

                rows.append({
                    'model': model, 'learner': learner, 'contrast': contrast,
                    'correct_counts': [int(a.sum()), int(b.sum())],
                    'paired_test_clusters': len(ids), 'test_tasks_per_condition': int(counts.sum()),
                    'cluster_task_counts': counts.tolist(), 'cluster_paired_correctness_sums': sums.tolist(),
                    'observed_task_weighted_difference': observed_difference,
                    'effective_cluster_sd': effective_sd,
                    'bootstrap_sd_95th_percentile_sensitivity': upper_sd,
                    'approx_clusters_alpha_05': approximate_n(.05, effective_sd),
                    'approx_clusters_alpha_05_over_8': approximate_n(.05/8, effective_sd),
                    'approx_clusters_alpha_05_over_8_sd_sensitivity': approximate_n(.05/8, upper_sd),
                })
    return {
        'purpose': 'Prospective sample-size planning sensitivity using an existing pilot; no new cohort or changed original inference.',
        'target_difference': .10, 'target_marginal_power': .80,
        'test_direction': 'two-sided',
        'formula': 'ceil(((z_(1-alpha/2)+z_0.8)*effective_cluster_sd/0.10)^2)',
        'effective_cluster_sd_definition': 'sample_sd(S_j - d_hat*n_j) / mean(n_j)',
        'multiplicity': '.05/8 is a sufficient Bonferroni per-comparison threshold for an eight-test family, not an exact Holm power calculation; 80% marginal power is not 80% probability all eight comparisons reject.',
        'resampling': {'seed': 1051111, 'replicates': 50000, 'unit': 'whole paired test session', 'variance_sensitivity': '95th percentile of resampled effective SD; an illustrative planning sensitivity, not a certified upper bound.'},
        'assumptions': [
            'New paired sessions follow the pilot cluster-size and paired-error distributions, with a shifted target effect and comparable variance.',
            'Sessions are independent at the planning level; repeated sessions from a larger shared dependence unit would require a different variance model.',
            'Saved fitted predictors remain fixed; training, selection, workload design and cross-domain uncertainty are omitted.',
            'Normal approximation; original permutation-test power still requires prospective simulation under explicitly specified alternatives.',
            'Counts refer to independent nonempty paired TEST clusters for each relevant model and condition; training, validation, empty sessions and replacement policy are additional design decisions.',
        ],
        'inputs_sha256': {str(p.relative_to(root)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in [prediction_path, plan_path]},
        'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'rows': rows,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.root.resolve())
    assert not args.output.exists(), 'Preserve previous outputs; choose a new output filename.'
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'comparisons': len(result['rows']), 'normal_approx_cluster_range': [min(r['approx_clusters_alpha_05_over_8'] for r in result['rows']), max(r['approx_clusters_alpha_05_over_8'] for r in result['rows'])], 'variance_sensitivity_max': max(r['approx_clusters_alpha_05_over_8_sd_sensitivity'] for r in result['rows'])}))
