"""Cover-count sweep under random placement, paper padding: privacy vs bytes vs state."""
import json, random
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
import cover_env as E
import run_replay as R

rng = random.Random(2027)
tasks = []
for a in E.ACTIONS:
    for _ in range(100):
        tasks.append(E.make_task(rng, len(tasks), a))
ids = list(range(len(tasks))); rng.shuffle(ids); train = set(ids[:300])
base = [R.run_task(t, "none", "fixed_after", "paper", s) for t in tasks for s in range(2)]
bb = np.mean([r["bytes"] for r in base])
out = []
for arm in ["transport_drop", "live_write"]:
    for k in [1, 2, 3, 4]:
        rs = [R.run_task(t, arm, "random", "paper", s, k_override=k) for t in tasks for s in range(2)]
        tr = [r for r in rs if r["task_id"] in train]; te = [r for r in rs if r["task_id"] not in train]
        X = lambda q: np.array([R.featurize(r["obs"]) for r in q]); y = lambda q: [r["label"] for r in q]
        lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000)).fit(X(tr), y(tr))
        rf = RandomForestClassifier(n_estimators=300, random_state=0, n_jobs=-1).fit(X(tr), y(tr))
        row = {"arm": arm, "k": k,
               "BA_D2_LR": R.ba(y(te), lr.predict(X(te))), "BA_D2_RF": R.ba(y(te), rf.predict(X(te))),
               "BA_rule": R.ba(y(te), [R.position_rule(r["obs"], "random") for r in te]),
               "goal_success": float(np.mean([r["goal"] for r in rs])),
               "state_integrity": float(np.mean([r["integrity"] for r in rs])),
               "byte_ratio_vs_none": float(np.mean([r["bytes"] for r in rs]) / bb)}
        row["BA_best"] = max(row["BA_D2_LR"], row["BA_D2_RF"], row["BA_rule"])
        print(row); out.append(row)
json.dump(out, open("results/k_sweep.json", "w"), indent=1)
