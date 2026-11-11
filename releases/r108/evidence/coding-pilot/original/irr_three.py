"""Three-coder agreement: pairwise Cohen's kappa, Light's kappa and Fleiss' kappa.

Coder 1 is the authors' released coding; coders 2 and 3 are CSV files in
coder2_template.csv format. Usage: python irr_three.py coder2.csv coder3.csv
"""
import csv
import json
import os
import sys

import numpy as np

from irr_kappa import FIELDS, HERE, boot, coder1, kappa


def fleiss(rows):
    cats = sorted({v for r in rows for v in r})
    n = len(rows[0])
    M = np.array([[r.count(c) for c in cats] for r in rows], dtype=float)
    p_j = M.sum(0) / M.sum()
    P_i = ((M * M).sum(1) - n) / (n * (n - 1))
    pbar, pe = P_i.mean(), (p_j ** 2).sum()
    return (pbar - pe) / (1 - pe) if pe < 1 else float("nan")


def fleiss_boot(rows, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    ks = []
    for _ in range(n):
        i = rng.integers(0, len(rows), len(rows))
        k = fleiss([rows[j] for j in i])
        if not np.isnan(k):
            ks.append(k)
    return [float(np.percentile(ks, 2.5)), float(np.percentile(ks, 97.5))]


def main(p2, p3):
    c = [coder1(), {r["setting_id"]: r for r in csv.DictReader(open(p2))},
         {r["setting_id"]: r for r in csv.DictReader(open(p3))}]
    ids = sorted(c[0])
    res = {}
    for f in FIELDS:
        v = [[c[k][i][f] for i in ids] for k in range(3)]
        pair = {}
        for a, b in [(0, 1), (0, 2), (1, 2)]:
            k, po = kappa(v[a], v[b])
            pair[f"C{a+1}-C{b+1}"] = {"kappa": round(k, 3), "ci95": [round(x, 3) for x in boot(v[a], v[b])], "agreement": round(po, 3)}
        rows = [[v[k][j] for k in range(3)] for j in range(len(ids))]
        res[f] = {"pairwise": pair,
                  "light_kappa": round(float(np.mean([p["kappa"] for p in pair.values()])), 3),
                  "fleiss_kappa": round(fleiss(rows), 3), "fleiss_ci95": [round(x, 3) for x in fleiss_boot(rows)],
                  "all_three_agree": sum(len(set(r)) == 1 for r in rows),
                  "majority_exists": sum(max(r.count(x) for x in r) >= 2 for r in rows),
                  "coder1_is_minority": [ids[j] for j, r in enumerate(rows) if r[1] == r[2] != r[0]]}
    out = os.path.join(HERE, "kappa-three-coders.json")
    json.dump(res, open(out, "w"), indent=1)
    for f, r in res.items():
        p = r["pairwise"]
        print(f"{f:15} C1-C2 {p['C1-C2']['kappa']:6} C1-C3 {p['C1-C3']['kappa']:6} C2-C3 {p['C2-C3']['kappa']:6} "
              f"| Fleiss {r['fleiss_kappa']} {r['fleiss_ci95']} | all-agree {r['all_three_agree']}/44 | C1 minority {len(r['coder1_is_minority'])}")
    return res


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "coder2_ai.csv"),
         sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "coder3_ai.csv"))
