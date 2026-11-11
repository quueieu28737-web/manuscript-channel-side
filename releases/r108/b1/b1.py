"""Frozen retrospective M3 timing extension; no inference or collection calls.

Reuse the original 153-dimensional feature extractor and LR/RF estimators.
Timing is CLIENT RECEIPT timing with supplied call/episode boundaries, not packet
timestamps. Hidden cover flags label detector examples and the privileged control
only. They never enter an ordinary attack's feature vector.
"""
import os
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['OPENBLAS_NUM_THREADS'] = '2'
from pathlib import Path
from collections import Counter
import argparse
import csv
import datetime
import gzip
import hashlib
import json
import math
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SOURCE = ROOT / 'revision-preview/r102-llm-executed-cover/review-export'
sys.path.insert(0, str(SOURCE / 'experiment'))
import analyze as original
import joblib
import numpy as np
import scipy
import sklearn
from scipy.stats import binomtest
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, confusion_matrix
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

MODELS = ['qwen3:8b', 'llama3.1:8b']
ARMS = original.ARMS
LABELS = original.LABELS
SERVICES = original.SERVICES
SEED = 1071111


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    assert not path.exists(), 'Preserve earlier output: ' + str(path)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def iter_records(splits):
    with gzip.open(SOURCE / 'data/episodes.jsonl.gz', 'rt', encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            if r['split'] in splits:
                yield r


def observe(r):
    """Whitelist only destination, ciphertext counts and client clock events."""
    receipts = {x['request']['request_id']: x for x in r['tool_receipts']}
    assert len(receipts) == len(r['wire_trace'])
    trace, timing, cover = [], [], []
    first = previous_end = None
    for w in r['wire_trace']:
        t = receipts[w['request_id']]['terminal']
        start, end = float(t['start']), float(t['end'])
        assert math.isfinite(start) and math.isfinite(end) and end > start
        if first is None:
            first = start
        gap = 0. if previous_end is None else start - previous_end
        assert gap >= 0, 'Non-monotone client clock; stop and investigate.'
        trace.append({'service': w['service'], 'bytes': list(w['bytes'])})
        timing.append([start - first, end - start, gap])
        cover.append(int(receipts[w['request_id']]['request']['kind'] == 'cover'))
        assert (w['kind'] == 'cover') == bool(cover[-1])
        previous_end = end
    assert trace
    # Privileged labels remain a separate array, absent from ordinary features.
    return {'trace': trace, 'timing': np.asarray(timing), 'cover': np.asarray(cover),
            'wall_seconds': float(r['wall_seconds'])}


def views(o):
    base = original.features({'wire_trace': o['trace']})
    t = np.zeros(49, dtype=float)
    n = min(16, len(o['timing']))
    t[:3*n] = o['timing'][:n].ravel()
    t[-1] = o['wall_seconds']
    assert base.shape == (153,)
    return {'bytes': base, 'timing_size': np.concatenate([base, t]), 'timing_only': t}


def call_features(o):
    # gap and duration in log1p(milliseconds), first-call flag, destination one-hot.
    x = np.zeros((len(o['trace']), 10))
    x[:, :2] = np.log1p(o['timing'][:, [2, 1]] * 1000)
    x[0, 2] = 1
    for i, w in enumerate(o['trace']):
        x[i, 3 + SERVICES.index(w['service'])] = 1
    return x


def stripped(o, mask):
    return original.features({'wire_trace': [w for w, remove in zip(o['trace'], mask) if not remove]})


def detector_models():
    return {
        'LR': make_pipeline(StandardScaler(), LogisticRegression(C=1, max_iter=3000,
                              random_state=102, class_weight='balanced')),
        'RF': RandomForestClassifier(n_estimators=300, n_jobs=2,
                                     random_state=102, class_weight='balanced'),
    }


def detector_metrics(truth, pred, probability=None):
    tp = int(np.sum((truth == 1) & (pred == 1)))
    fp = int(np.sum((truth == 0) & (pred == 1)))
    fn = int(np.sum((truth == 1) & (pred == 0)))
    tn = int(np.sum((truth == 0) & (pred == 0)))
    precision = tp/(tp+fp) if tp+fp else 0.
    recall = tp/(tp+fn) if tp+fn else 0.
    return {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn, 'precision': precision,
            'recall': recall, 'f1': 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.,
            'auc': float(roc_auc_score(truth, probability)) if probability is not None and len(set(truth)) == 2 else None}


def fit_detector(train, val):
    xt = np.concatenate([call_features(o) for o in train])
    yt = np.concatenate([o['cover'] for o in train])
    xv = np.concatenate([call_features(o) for o in val])
    yv = np.concatenate([o['cover'] for o in val])
    first = xv[:, 2] == 1
    candidates, fitted = [], {}
    for name, est in detector_models().items():
        est.fit(xt, yt)
        probability = est.predict_proba(xv)[:, 1]
        fitted[name] = est
        for threshold in np.arange(.05, .951, .05):
            prediction = (probability >= threshold).astype(int)
            prediction[first] = 0  # All M3 episodes begin with the controller's ticket retrieval.
            metric = detector_metrics(yv, prediction)
            candidates.append({'name': name, 'threshold': float(threshold), 'metric': metric})
    # A preregistered schedule-aware heuristic, tuned only on validation.
    for threshold in [.025, .05, .10, .20, .35, .50, 1.0]:
        gap = np.concatenate([o['timing'][:, 2] for o in val])
        prediction = ((gap < threshold) & ~first).astype(int)
        candidates.append({'name': 'gap_rule', 'threshold': threshold,
                           'metric': detector_metrics(yv, prediction)})
    selected = max(candidates, key=lambda c: (c['metric']['f1'], c['metric']['precision'],
                   {'LR': 2, 'gap_rule': 1, 'RF': 0}[c['name']], c['threshold']))
    return fitted, selected, candidates


def predict_cover(o, models, selection):
    x = call_features(o)
    if selection['name'] == 'gap_rule':
        probability = 1/(1 + o['timing'][:, 2])
        pred = o['timing'][:, 2] < selection['threshold']
    else:
        probability = models[selection['name']].predict_proba(x)[:, 1]
        pred = probability >= selection['threshold']
    pred = np.asarray(pred, dtype=int)
    pred[0] = 0
    probability = np.asarray(probability, dtype=float).copy()
    probability[0] = 0.
    return pred, probability


def freeze():
    assert not (HERE / 'freeze.json').exists()
    inputs = [SOURCE / 'data/episodes.jsonl.gz', SOURCE / 'manifest.json',
              SOURCE / 'experiment/analyze.py', SOURCE / 'experiment/analysis-plan.json',
              SOURCE / 'experiment/cohort-plan.json', SOURCE / 'analysis/features.npz',
              SOURCE / 'analysis/predictions.csv', SOURCE / 'analysis/validation-selection.json']
    old = load(SOURCE / 'manifest.json')['files']
    for p in inputs:
        if p.name != 'manifest.json':
            assert sha(p) == old[p.relative_to(SOURCE).as_posix()]['sha256']
    frozen = {'utc': now(), 'status': 'FROZEN_BEFORE_NEW_TIMING_TEST_EVALUATION',
              'upstream_commit': '6c832f068a7fb2dfc38feb1bde37c38252250bd5',
              'code_sha256': sha(Path(__file__)), 'plan_sha256': sha(HERE / 'analysis-plan.json'),
              'inputs': {p.relative_to(ROOT).as_posix(): sha(p) for p in inputs},
              'environment': {'python': sys.version, 'numpy': np.__version__, 'scipy': scipy.__version__, 'sklearn': sklearn.__version__},
              'exposure': 'Original M3 test byte-only scores and outcomes were previously published and known. Upstream timing hypothesis used validation. This is a retrospective new-observer analysis frozen before new test timing extraction/fitting/scoring, not a new independent confirmation cohort.'}
    save(HERE / 'freeze.json', frozen)
    print(json.dumps({'status': frozen['status'], 'utc': frozen['utc'], 'inputs': len(inputs)}), flush=True)


def check_freeze():
    f = load(HERE / 'freeze.json')
    assert sha(Path(__file__)) == f['code_sha256']
    assert sha(HERE / 'analysis-plan.json') == f['plan_sha256']
    for name, digest in f['inputs'].items():
        assert sha(ROOT / name) == digest, name
    return f


def prepare():
    check_freeze()
    out = HERE / 'validation'
    assert not out.exists()
    out.mkdir()
    records = list(iter_records({'train', 'validation'}))
    assert len(records) == 2160
    obs = {(r['model'], r['arm'], r['task_id']): observe(r) for r in records}
    data = {(r['model'], r['arm'], r['task_id']): r for r in records}
    selection, detector_selection, description = [], [], []
    for model in MODELS:
        fitted = {}
        ids = {s: sorted(r['task_id'] for r in records if r['model'] == model and r['arm'] == 'none' and r['split'] == s) for s in ['train', 'validation']}
        y = {s: np.array([LABELS.index(data[model, 'none', i]['label']) for i in ids[s]]) for s in ids}
        for arm in ARMS:
            train = [obs[model, arm, i] for i in ids['train']]
            val = [obs[model, arm, i] for i in ids['validation']]
            for view in ['bytes', 'timing_size', 'timing_only']:
                xtr = np.stack([views(o)[view] for o in train])
                xv = np.stack([views(o)[view] for o in val])
                scores = {}
                for name, est in original.estimators().items():
                    est.fit(xtr, y['train'])
                    scores[name] = float(np.mean(est.predict(xv) == y['validation']))
                    fitted[arm, view, name] = est
                selected = original.choose(scores)
                selection.append({'model': model, 'arm': arm, 'view': view, 'selected': selected, 'validation_accuracy': scores})
                if view == 'bytes':
                    old = next(x for x in load(SOURCE / 'analysis/validation-selection.json') if x['model'] == model and x['arm'] == arm)
                    assert old['selected'] == selected
                    assert all(abs(old['validation_BA'][n] - scores[n]) < 1e-12 for n in scores)
            times = np.concatenate([o['timing'] for o in val])
            kinds = np.concatenate([o['cover'] for o in val])
            first = np.concatenate([np.arange(len(o['trace'])) == 0 for o in val])
            for kind in [0, 1]:
                mask = (kinds == kind) & ~first
                if mask.any():
                    description.append({'model': model, 'arm': arm, 'kind': 'cover' if kind else 'honest', 'calls_excluding_initial': int(mask.sum()),
                                        'gap_median_seconds': float(np.median(times[mask, 2])),
                                        'duration_median_seconds': float(np.median(times[mask, 1]))})
            print(json.dumps({'stage': 'validation_fit', 'model': model, 'arm': arm}), flush=True)
        tr = [obs[model, r['arm'], r['task_id']] for r in records if r['model'] == model and r['split'] == 'train']
        va = [obs[model, r['arm'], r['task_id']] for r in records if r['model'] == model and r['split'] == 'validation']
        det, chosen, candidates = fit_detector(tr, va)
        detector_selection.append({'model': model, 'selected': chosen, 'validation_candidates': candidates})
        joblib.dump({'task_models': fitted, 'detector_models': det}, out / (model.replace(':', '-') + '.joblib'))
    save(out / 'task-selection.json', selection)
    save(out / 'detector-selection.json', detector_selection)
    save(out / 'timing-description.json', description)
    save(out / 'finished.json', {'utc': now(), 'records': len(records), 'test_timing_evaluated': False,
                                'files': {p.name: sha(p) for p in out.iterdir() if p.is_file()}})
    print('TRAIN_VALIDATION_COMPLETE; original validation selections match.', flush=True)


def stratified_bootstrap(y):
    rng = np.random.default_rng(SEED)
    return np.concatenate([rng.choice(np.flatnonzero(y == k), size=(10000, int(np.sum(y == k))), replace=True) for k in range(6)], axis=1)


def interval(v, indices):
    return np.quantile(np.asarray(v)[indices].mean(axis=1), [.025, .975]).tolist()


def contrast(a, b, model, arm, description, indices):
    plus, minus = int(np.sum(a & ~b)), int(np.sum(b & ~a))
    difference = a.astype(int) - b.astype(int)
    return {'model': model, 'arm': arm, 'comparison': description, 'n_pairs': len(a),
            'condition_only': plus, 'reference_only': minus,
            'difference_pp': float(difference.mean()*100),
            'conditional_ci_pp': (100*np.asarray(interval(difference, indices))).tolist(),
            'p_raw': float(binomtest(plus, plus+minus, .5).pvalue) if plus+minus else 1.}


def evaluate():
    started = time.time()
    f = check_freeze()
    val = HERE / 'validation'
    for name, digest in load(val / 'finished.json')['files'].items():
        assert sha(val / name) == digest
    out = HERE / 'results'
    assert not out.exists()
    out.mkdir()
    save(out / 'started.json', {'utc': now(), 'freeze_sha256': sha(HERE / 'freeze.json'), 'validation_finished_sha256': sha(val / 'finished.json')})
    records = list(iter_records({'test'}))
    assert len(records) == 1440
    data = {(r['model'], r['arm'], r['task_id']): r for r in records}
    obs = {key: observe(r) for key, r in data.items()}
    selection = load(val / 'task-selection.json')
    detector_selection = load(val / 'detector-selection.json')
    saved = list(csv.DictReader((SOURCE / 'analysis/predictions.csv').open(encoding='utf-8', newline='')))
    recognition, detector_rows, prediction_rows, summaries = [], [], [], []
    families = {'primary_timing_size_vs_bytes': [], 'secondary_stripping_vs_bytes': [], 'secondary_hidden_semantics': []}
    audit = []
    arrays = {'features': [], 'truth': [], 'model': [], 'arm': [], 'task': [], 'call_truth': [], 'call_probability': [], 'call_prediction': [], 'call_task': [], 'call_model': [], 'call_arm': [], 'call_features': []}
    for model in MODELS:
        fitted = joblib.load(val / (model.replace(':', '-') + '.joblib'))
        det = next(x['selected'] for x in detector_selection if x['model'] == model)
        ids = sorted(r['task_id'] for r in records if r['model'] == model and r['arm'] == 'none')
        y = np.array([LABELS.index(data[model, 'none', i]['label']) for i in ids])
        assert Counter(y) == {k: 20 for k in range(6)}
        indices = stratified_bootstrap(y)
        chosen_none = next(x['selected'] for x in selection if x['model'] == model and x['arm'] == 'none' and x['view'] == 'bytes')
        honest_classifier = fitted['task_models']['none', 'bytes', chosen_none]
        correctness = {}
        for arm in ARMS:
            observations = [obs[model, arm, i] for i in ids]
            predictions = {}
            for view in ['bytes', 'timing_size', 'timing_only']:
                x = np.stack([views(o)[view] for o in observations])
                chosen = next(z['selected'] for z in selection if z['model'] == model and z['arm'] == arm and z['view'] == view)
                for name in ['LR', 'RF']:
                    predictions[view + '/' + name] = fitted['task_models'][arm, view, name].predict(x)
                predictions[view + '/selected'] = predictions[view + '/' + chosen]
            masks, probabilities = zip(*(predict_cover(o, fitted['detector_models'], det) for o in observations))
            predictions['stripped/frozen_none'] = honest_classifier.predict(np.stack([stripped(o, mask) for o, mask in zip(observations, masks)]))
            predictions['privileged_cover_labels/frozen_none'] = honest_classifier.predict(np.stack([stripped(o, o['cover']) for o in observations]))
            for attack, pred in predictions.items():
                correct = pred == y
                recognition.append({'model': model, 'arm': arm, 'attack': attack, 'n': len(y), 'correct': int(correct.sum()), 'accuracy': float(correct.mean()),
                                    'conditional_ci': interval(correct, indices), 'confusion': confusion_matrix(y, pred, labels=list(range(6))).tolist()})
                correctness[arm, attack] = correct
            for i, task in enumerate(ids):
                r = data[model, arm, task]
                old = next(z for z in saved if z['model'] == model and z['arm'] == arm and int(z['task_id']) == task)
                assert predictions['bytes/LR'][i] == int(old['LR'])
                assert predictions['bytes/RF'][i] == int(old['RF'])
                prediction_rows.append({'model': model, 'arm': arm, 'task_id': task, 'truth': int(y[i]),
                                        **{name: int(pred[i]) for name, pred in predictions.items()}})
                o = observations[i]
                arrays['features'].append(views(o)['timing_size']); arrays['truth'].append(y[i])
                arrays['model'].append(model); arrays['arm'].append(arm); arrays['task'].append(task)
                arrays['call_truth'].extend(o['cover']); arrays['call_probability'].extend(probabilities[i]); arrays['call_prediction'].extend(masks[i])
                arrays['call_task'].extend([task]*len(masks[i]));arrays['call_model'].extend([model]*len(masks[i])); arrays['call_arm'].extend([arm]*len(masks[i]))
                arrays['call_features'].extend(call_features(o))
            actual = np.concatenate([o['cover'] for o in observations])
            predicted = np.concatenate(masks); probability = np.concatenate(probabilities)
            metric = detector_metrics(actual, predicted, probability)
            grouped = np.array([[np.sum((o['cover'] == 1) & (p == 1)), np.sum((o['cover'] == 0) & (p == 1)),
                                 np.sum((o['cover'] == 1) & (p == 0)), np.sum((o['cover'] == 0) & (p == 0))] for o,p in zip(observations,masks)])
            sampled = grouped[indices].sum(axis=1)
            pden = sampled[:, 0]+sampled[:, 1]; rden=sampled[:, 0]+sampled[:, 2]
            precision = np.divide(sampled[:,0], pden, out=np.zeros(10000), where=pden>0)
            recall = np.divide(sampled[:,0], rden, out=np.zeros(10000), where=rden>0)
            detector_rows.append({'model': model, 'arm': arm, 'detector': det['name'], 'threshold': det['threshold'], **metric,
                                  'conditional_precision_ci': np.quantile(precision,[.025,.975]).tolist(),
                                  'conditional_recall_ci': np.quantile(recall,[.025,.975]).tolist()})
            if arm != 'none':
                for family, attack in [('primary_timing_size_vs_bytes','timing_size/selected'), ('secondary_stripping_vs_bytes','stripped/frozen_none')]:
                    families[family].append(contrast(correctness[arm, attack], correctness[arm, 'bytes/selected'], model, arm, attack + ' minus bytes/selected', indices))
            audit.append({'model': model, 'arm': arm, 'original_lr_rf_predictions_match': True, 'test_fixtures': 120})
            print(json.dumps({'stage': 'test_evaluation', 'model': model, 'arm': arm}), flush=True)
        hidden = ['transport_drop', 'read', 'isolated', 'live_write']
        for i, a in enumerate(hidden):
            for b in hidden[:i]:
                families['secondary_hidden_semantics'].append(contrast(correctness[a,'timing_size/selected'], correctness[b,'timing_size/selected'], model, a, a+' minus '+b, indices))
    for name, rows in families.items():
        assert len(rows) == (12 if name == 'secondary_hidden_semantics' else 10)
        original.holm(rows)
    save(out / 'recognition.json', recognition)
    save(out / 'cover-detection.json', detector_rows)
    save(out / 'comparisons.json', families)
    save(out / 'predictions.json', prediction_rows)
    save(out / 'baseline-audit.json', audit)
    np.savez_compressed(out / 'test-arrays.npz', **{k: np.asarray(v) for k,v in arrays.items()})
    save(out / 'finished.json', {'utc': now(), 'status': 'COMPLETE', 'seconds': time.time()-started,
         'test_episodes': len(records), 'conditional_analysis': True, 'freeze_utc': f['utc'],
         'scope': 'Client-receipt timing with supplied episode/call boundaries; not packet timing or production confidentiality.',
         'files': {p.name: sha(p) for p in out.iterdir() if p.is_file()}})
    print('B1_COMPLETE; original held-out byte-only LR/RF predictions match exactly.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['freeze','prepare','evaluate'])
    args = parser.parse_args()
    {'freeze': freeze, 'prepare': prepare, 'evaluate': evaluate}[args.stage]()
