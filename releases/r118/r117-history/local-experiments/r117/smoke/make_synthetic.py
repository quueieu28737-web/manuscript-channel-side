"""Build a SYNTHETIC stand-in for the private live-timing directory.

Purpose: smoke-test the R117 scripts end to end (including the frozen
analyze.py) without the private data. Values are random and carry no
scientific meaning. Never mix this directory with real outputs.
"""
import argparse, hashlib, json, random, shutil
from pathlib import Path

SERVICES = ['helpdesk', 'crm', 'policy', 'orders', 'payments', 'billing', 'shipping']
ACTIONS = ['refund', 'address_update', 'escalation', 'replacement', 'cancellation', 'receipt']
ACTION_SERVICE = {'refund': 'payments', 'receipt': 'billing', 'address_update': 'crm',
                  'escalation': 'helpdesk', 'replacement': 'shipping', 'cancellation': 'orders'}
CHECKS = {'account': 'crm', 'policy': 'policy', 'approval': 'policy', 'status': 'orders'}
MODELS = ['qwen3:8b', 'llama3.1:8b']
ARMS = ['none', 'unmatched', 'gdm_live', 'concurrent', 'shadow']
REPO = Path(__file__).resolve().parents[3]
LIVE = REPO / 'releases/r116/artifact/live-study'


def dump(p, x):
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(x), encoding='utf-8')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def units(rng):
    out = []; tid = 0
    for split, n in [('train', 120), ('validation', 60), ('test', 120)]:
        for i in range(n):
            a = ACTIONS[i % 6]; checks = rng.sample(sorted(CHECKS), rng.randint(1, 3))
            nd = rng.randint(1, 2)
            decoys = [{'action': rng.choice([x for x in ACTIONS if x != a]), 'after_honest_calls': rng.randint(0, len(checks) + 1)}
                      for _ in range(nd)]
            out.append({'task_id': tid, 'split': split, 'action': a, 'checks': checks, 'decoys': decoys}); tid += 1
    return out


def chain_calls(rng, u, t, role, model_wait):
    """Honest calls of one planner chain: get_ticket, checks, action."""
    seq = [('get_ticket', 'helpdesk')] + [(c, CHECKS[c]) for c in u['checks']] + [(u['action'], ACTION_SERVICE[u['action']])]
    calls = []
    for k, (op, svc) in enumerate(seq):
        if k:
            t += rng.lognormvariate(model_wait, .3)
        d = rng.uniform(.02, .08)
        calls.append({'service': svc, 'operation': op, 'kind': 'honest', 'role': role, 'start': t, 'end': t + d}); t += d
    return calls, t


def episode(rng, u, model, arm):
    wait = -0.7 if model == 'qwen3:8b' else -0.5
    real, t_end = chain_calls(rng, u, 1.0, 'real', wait)
    trace = list(real); shadow = None; sched = None
    if arm in ['unmatched', 'gdm_live', 'concurrent']:
        honest_seen = [c for c in real]
        for d in u['decoys']:
            idx = min(d['after_honest_calls'], len(honest_seen) - 1)
            anchor = honest_seen[idx]
            gap = rng.uniform(.002, .008) if arm == 'unmatched' else rng.lognormvariate(-0.7, .4)
            s = anchor['end'] + gap; dur = rng.uniform(.02, .1)
            trace.append({'service': ACTION_SERVICE[d['action']], 'operation': d['action'], 'kind': 'cover', 'role': 'real',
                          'start': s, 'end': s + dur})
    if arm == 'shadow':
        su = dict(u); su['action'] = rng.choice(ACTIONS); su['checks'] = rng.sample(sorted(CHECKS), rng.randint(1, 3))
        first = bool(rng.randrange(2)); off = rng.uniform(.2, 1.5)
        sc, _ = chain_calls(rng, su, 1.0 + (0 if first else off), 'shadow', wait)
        if first:
            shift = off
            for c in real:
                c['start'] += shift; c['end'] += shift
        trace += sc; sched = {'shadow_first': first, 'offset_s': off, 'decoy_action': su['action']}
        shadow = {'model_usage': [{'prompt_eval_count': 900, 'eval_count': 20}] * len(sc)}
    trace.sort(key=lambda c: c['start'])
    # Serialize same-service calls so windows never overlap on one connection.
    last = {}
    for c in trace:
        if c['service'] in last and c['start'] < last[c['service']] + .003:
            sh = last[c['service']] + .003 - c['start']; c['start'] += sh; c['end'] += sh
        last[c['service']] = c['end']
    trace.sort(key=lambda c: c['start'])
    base = 10 ** 12
    wt = [{'service': c['service'], 'bytes': [4096 + rng.randint(40, 90), 16384 + rng.randint(40, 200)],
           'start_ns': base + int(c['start'] * 1e9), 'end_ns': base + int(c['end'] * 1e9),
           'request_id': f'r{i}', 'kind': c['kind'], 'role': c['role'], 'operation': c['operation']} for i, c in enumerate(trace)]
    honest = [c for c in real]
    primary = {'calls': [{'kind': 'honest', 'action': c['operation'], 'order_id': 'O'} for c in honest],
               'model_usage': [{'prompt_eval_count': 900, 'eval_count': 20}] * len(honest),
               'goal_success': rng.random() < .9, 'state_integrity': rng.random() < .9,
               'start': 1.0, 'end': max(c['end'] for c in real)}
    return {'job_id': f'{model}-{arm}-{u["task_id"]}', 'model': model, 'arm': arm, 'task_id': u['task_id'], 'split': u['split'],
            'label': u['action'], 'admitted_at': 1.0, 'primary': primary, 'shadow': shadow, 'shadow_schedule': sched,
            'wire_trace': wt, 'transport_total_bytes': sum(sum(x['bytes']) for x in wt) + 7 * 30000}


def wires(rng, ep):
    """Per-connection TLS records consistent with the call windows (record-only view)."""
    t0 = min(c['start_ns'] for c in ep['wire_trace']) - 200_000_000
    out = []
    for k, svc in enumerate(SERVICES):
        up, down = [], []
        t = t0 + k * 3_000_000
        for _ in range(2):  # MCP initialize / initialized
            up.append([23, 4096 + 60, t, t]); down.append([23, 16384 + 80, t + 2_000_000, t + 2_000_000]); t += 5_000_000
        for c in ep['wire_trace']:
            if c['service'] != svc:
                continue
            up.append([23, c['bytes'][0], c['start_ns'], c['start_ns']])
            down.append([23, 300, c['start_ns'] + 1_000_000, 0])
            down.append([23, c['bytes'][1] - 300, c['end_ns'], c['end_ns']])
        te = max(c['end_ns'] for c in ep['wire_trace']) + 50_000_000
        up.append([23, 40, te, te]); down.append([23, 40, te + 1_000_000, te])
        up.sort(key=lambda r: r[2]); down.sort(key=lambda r: r[2])
        out.append({'id': f'{ep["job_id"]}-{svc}', 'service': svc, 'closed': True, 'trailing_bytes': [0, 0],
                    'record_schema': ['outer_type', 'wire_length', 'completion_perf_ns', 'completion_epoch_ns'],
                    'records': [up, down]})
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True, type=Path); a = ap.parse_args()
    if a.out.exists():
        shutil.rmtree(a.out)
    rng = random.Random(7)
    (a.out / 'experiment').mkdir(parents=True)
    for f in ['analyze.py', 'common.py']:
        shutil.copy(LIVE / 'experiment' / f, a.out / 'experiment' / f)
    U = units(rng)
    for model in MODELS:
        for arm in ARMS:
            run = 'formal-none-v1' if arm == 'none' else 'formal-cover-v1'
            for u in U:
                ep = episode(rng, u, model, arm)
                d = a.out / 'private-run' / run / 'episodes' / ep['job_id'].replace(':', '-')
                dump(d / 'result.json', ep)
                for w in wires(rng, ep):
                    name = w['id'].replace(':', '-') + '.json'
                    dump(d / 'connections' / name, {'id': w['id'], 'service': w['service']})
                    dump(a.out / 'private-run' / run / 'wire' / name, w)
    dump(a.out / 'experiment/freeze.json', {'files': {'experiment/analyze.py': sha(a.out / 'experiment/analyze.py')}})
    for run in ['formal-none-v1', 'formal-cover-v1']:
        dump(a.out / 'verification' / f'{run}-verified.json', {'status': 'PASS', 'note': 'SYNTHETIC smoke test only'})
    print('Synthetic live dir at', a.out)


if __name__ == '__main__':
    main()
