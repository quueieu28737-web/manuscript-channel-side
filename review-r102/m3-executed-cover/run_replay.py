"""Executed-cover replay: privacy, task outcome and state on the same runs.

Arms (cover never reaches the planner; the planner is the reference program):
  none            no cover
  transport_drop  cover request/response on the wire, terminated at an egress proxy
  read            cover is a read-only call to the decoy action's service
  isolated        decoy business action executed on a cloned fixture
  live_write      decoy business action executed on the real fixture
Schedules: fixed_after (one decoy right after the real action), fixed_before
(one decoy right before it), random (1-2 decoys at uniform positions after the
ticket fetch). Padding: paper policy (4,096-byte requests, 16,384-byte
responses) or none.

Observer: destination service and TLS 1.3 ciphertext bytes of every call.
Attackers: D0 (trained on no-cover traces), D2 (refit on the arm's own
protected training traces; LR and RF) and a position rule. Task-level split.
"""
import copy
import json
import random
import sys
from collections import defaultdict

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import cover_env as E
import tls_wire as W

SERVICES = ["helpdesk", "crm", "policy", "orders", "payments", "billing", "shipping"]
MAXPOS = 8
ARMS = ["none", "transport_drop", "read", "isolated", "live_write"]
SCHEDULES = ["fixed_after", "fixed_before", "random"]
PADDINGS = {"paper": (4096, 16384), "none": (0, 0)}


def plan_calls(task, decoys, schedule, rng):
    calls = [("ticket", "helpdesk", "get_ticket", None)]
    calls += [("check", E.CHECKS[c], f"check_{c}", None) for c in task["checks"]]
    real = ("real", E.ACTION_SERVICE[task["action"]], task["action"], task["target"])
    if schedule == "fixed_after":
        return calls + [real] + [("cover",) + d for d in decoys]
    if schedule == "fixed_before":
        return calls + [("cover",) + d for d in decoys] + [real]
    seq = calls[1:] + [real]
    for d in decoys:
        seq.insert(rng.randint(0, len(seq)), ("cover",) + d)
    return [calls[0]] + seq


def run_task(task, arm, schedule, padding, seed, k_override=None):
    rng = random.Random(f"{task['task_id']}-{seed}-{schedule}")
    qreq, qresp = PADDINGS[padding]
    k = 0 if arm == "none" else (1 if schedule != "random" else rng.randint(1, 2))
    if k_override is not None and arm != "none":
        k = k_override
    decoys = []
    for _ in range(k):
        a, o = E.pick_decoy(rng, task)
        decoys.append((E.ACTION_SERVICE[a], a, o))
    state = copy.deepcopy(task["fixture"])
    shadow = copy.deepcopy(task["fixture"])
    conns, obs, real_ok, cover_calls = {}, [], None, 0
    for kind, svc, op, obj in plan_calls(task, decoys, schedule, rng):
        req = E.body({"op": op, "order": obj}, rng.randint(40, 400))
        if kind == "ticket":
            resp = E.body({"ticket": task["task_id"]}, task["ticket_len"])
        elif kind == "check":
            resp = E.body({"check": op, "ok": True}, rng.randint(200, 2500))
        elif kind == "real":
            ok, r = E.apply_action(state, op, obj)
            real_ok = ok
            resp = E.body(r, rng.randint(200, 2500))
        else:
            cover_calls += 1
            if arm == "read":
                op = E.READ_ENDPOINT[svc]
                req = E.body({"op": op, "order": obj}, rng.randint(40, 400))
                resp = E.body({"read": op}, rng.randint(200, 2500))
            elif arm == "transport_drop":
                _, r = E.apply_action(copy.deepcopy(task["fixture"]), op, obj)  # synthesize shape only
                resp = E.body(r, rng.randint(200, 2500))
            elif arm == "isolated":
                _, r = E.apply_action(shadow, op, obj)
                resp = E.body(r, rng.randint(200, 2500))
            else:
                _, r = E.apply_action(state, op, obj)
                resp = E.body(r, rng.randint(200, 2500))
        if svc not in conns:
            conns[svc] = W.Conn(svc)
        up, down = conns[svc].exchange(W.http_frame(svc, op, req, qreq),
                                       (b"HTTP/1.1 200 OK\r\n\r\n" + resp) if not qresp else
                                       W.http_frame(svc, "resp", resp, qresp))
        obs.append((svc, up, down))
    ref = E.reference_final_state(task)
    tgt = task["target"]
    goal = bool(real_ok) and state["orders"][tgt] == ref["orders"][tgt]
    if task["action"] == "address_update":
        goal = goal and state["customer"]["address"] == ref["customer"]["address"]
    if task["action"] == "escalation":
        goal = goal and state["customer"]["escalated"]
    if task["action"] == "replacement":
        mine = [e for e in state["ledger"] if e[0] == "replacement" and e[1] == tgt]
        goal = goal and mine == [e for e in ref["ledger"] if e[0] == "replacement"]
    integrity = state == ref
    return {"obs": obs, "goal": goal, "integrity": integrity, "cover_calls": cover_calls,
            "bytes": sum(u + d for _, u, d in obs), "label": task["action"],
            "task_id": task["task_id"], "seed": seed}


def featurize(obs):
    v = np.zeros(len(SERVICES) * (MAXPOS + 1) + 2 * MAXPOS + 2)
    for i, (svc, up, down) in enumerate(obs[:MAXPOS]):
        v[i * len(SERVICES) + SERVICES.index(svc)] = 1
    base = len(SERVICES) * MAXPOS
    for svc, _, _ in obs:
        v[base + SERVICES.index(svc)] += 1
    base += len(SERVICES)
    for i, (_, up, down) in enumerate(obs[:MAXPOS]):
        v[base + 2 * i] = up / 1024
        v[base + 2 * i + 1] = down / 1024
    v[-2] = len(obs)
    v[-1] = sum(u + d for _, u, d in obs) / 1024
    return v


def position_rule(obs, schedule):
    # Service -> action map is public; the rule picks the last (or second-to-last) call.
    inv = {s: a for a, s in E.ACTION_SERVICE.items()}
    idx = -2 if schedule == "fixed_after" and len(obs) >= 2 else -1
    return inv.get(obs[idx][0], "escalation")


def task_bootstrap(task_ids, correct, labels, n=2000, rng=None):
    rng = rng or np.random.default_rng(0)
    uniq = np.array(sorted(set(task_ids)))
    by = defaultdict(list)
    for t, c, l in zip(task_ids, correct, labels):
        by[t].append((c, l))
    vals = []
    for _ in range(n):
        pick = rng.choice(uniq, len(uniq))
        ys, ps = [], []
        for t in pick:
            for c, l in by[t]:
                ys.append(l)
                ps.append(c)
        vals.append(np.mean(ps))
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def ba(y, p):
    return float(balanced_accuracy_score(y, p))


def main(n_per_class=100, seeds=2, out="results"):
    import os
    os.makedirs(out, exist_ok=True)
    rng = random.Random(2027)
    tasks = []
    for a in E.ACTIONS:
        for _ in range(n_per_class):
            tasks.append(E.make_task(rng, len(tasks), a))
    ids = list(range(len(tasks)))
    rng.shuffle(ids)
    train = set(ids[: len(ids) // 2])
    runs = {}
    for padding in PADDINGS:
        for arm in ARMS:
            for schedule in (SCHEDULES if arm != "none" else ["none"]):
                rs = [run_task(t, arm, schedule if arm != "none" else "fixed_after", padding, s)
                      for t in tasks for s in range(seeds)]
                runs[(padding, arm, schedule)] = rs
                print(padding, arm, schedule, len(rs), file=sys.stderr)
    rows = []
    for padding in PADDINGS:
        base = runs[(padding, "none", "none")]
        Xb = np.array([featurize(r["obs"]) for r in base if r["task_id"] in train])
        yb = [r["label"] for r in base if r["task_id"] in train]
        d0 = make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, C=1.0)).fit(Xb, yb)
        base_bytes = np.mean([r["bytes"] for r in base])
        for (pad, arm, schedule), rs in runs.items():
            if pad != padding:
                continue
            tr = [r for r in rs if r["task_id"] in train]
            te = [r for r in rs if r["task_id"] not in train]
            Xtr = np.array([featurize(r["obs"]) for r in tr]); ytr = [r["label"] for r in tr]
            Xte = np.array([featurize(r["obs"]) for r in te]); yte = [r["label"] for r in te]
            lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, C=1.0)).fit(Xtr, ytr)
            rf = RandomForestClassifier(n_estimators=300, random_state=0, n_jobs=-1).fit(Xtr, ytr)
            preds = {"D0_LR": d0.predict(Xte), "D2_LR": lr.predict(Xte), "D2_RF": rf.predict(Xte),
                     "rule": [position_rule(r["obs"], schedule) for r in te]}
            tid = [r["task_id"] for r in te]
            row = {"padding": padding, "arm": arm, "schedule": schedule, "n_test_runs": len(te),
                   "n_test_tasks": len(set(tid))}
            for k, p in preds.items():
                row[f"BA_{k}"] = ba(yte, p)
                row[f"BA_{k}_ci"] = task_bootstrap(tid, [int(a == b) for a, b in zip(p, yte)], yte)
            row["BA_best"] = max(row[f"BA_{k}"] for k in preds)
            allr = rs
            row["goal_success"] = float(np.mean([r["goal"] for r in allr]))
            row["goal_success_ci"] = task_bootstrap([r["task_id"] for r in allr],
                                                    [int(r["goal"]) for r in allr], [0] * len(allr))
            row["state_integrity"] = float(np.mean([r["integrity"] for r in allr]))
            row["state_integrity_ci"] = task_bootstrap([r["task_id"] for r in allr],
                                                       [int(r["integrity"]) for r in allr], [0] * len(allr))
            row["cover_calls_per_task"] = float(np.mean([r["cover_calls"] for r in allr]))
            row["byte_ratio_vs_none"] = float(np.mean([r["bytes"] for r in allr]) / base_bytes)
            rows.append(row)
    json.dump({"design": __doc__, "n_tasks": len(tasks), "seeds": seeds, "train_tasks": len(train),
               "chance_BA": 1 / 6, "rows": rows}, open(f"{out}/replay_results.json", "w"), indent=1)
    by_action = defaultdict(lambda: defaultdict(list))
    for (pad, arm, schedule), rs in runs.items():
        if pad == "paper":
            for r in rs:
                by_action[(arm, schedule)][r["label"]].append(r["goal"])
    json.dump({f"{a}|{s}": {k: float(np.mean(v)) for k, v in d.items()} for (a, s), d in by_action.items()},
              open(f"{out}/goal_by_action_paper_padding.json", "w"), indent=1)
    return rows


if __name__ == "__main__":
    main()
