"""Cohen's kappa between the authors' released coding (coder 1) and a second coding.

Usage: python irr_kappa.py [coder2.csv]   (default: coder2_ai.csv)
A human second coder fills coder2_template.csv blind to coder 1 and reruns this
script with that file. Kappa is reported per field with a 2,000-draw
setting-bootstrap 95% interval, observed agreement and the confusion matrix.
"""
import csv
import json
import os
import sys
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.join(HERE, "..", "..", "releases", "r101", "evidence")
FIELDS = ["access_class", "protection", "named_transfer", "open_world", "failure_status", "outcome_status"]


def coder1():
    m = {r["setting_id"]: r for r in csv.DictReader(open(os.path.join(EV, "field-map", "evidence-matrix.csv")))}
    t = {r["setting_id"]: r for r in csv.DictReader(open(os.path.join(EV, "field-map", "target-evidence.csv")))}
    a = {r["setting_id"]: r for r in csv.DictReader(open(os.path.join(EV, "transfer-synthesis", "setting-availability.csv")))}
    out = {}
    for sid, r in m.items():
        ax = r["transfer_axis"].lower()
        out[sid] = {
            "access_class": a[sid]["access_class"],
            "protection": "Y" if r["intervention"] != "none" else "N",
            "named_transfer": "Y" if any(k in ax for k in ("leave one", "topology", "held-out scaffold", "proprietary scaffold")) else "N",
            "open_world": "Y" if ("open world" in ax or "open-world" in ax) else "N",
            "failure_status": t[sid]["failure_status"],
            "outcome_status": t[sid]["outcome_status"],
        }
    return out


def kappa(x, y):
    x, y = list(x), list(y)
    cats = sorted(set(x) | set(y))
    n = len(x)
    po = sum(a == b for a, b in zip(x, y)) / n
    cx, cy = Counter(x), Counter(y)
    pe = sum(cx[c] * cy[c] for c in cats) / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else float("nan"), po


def boot(x, y, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    x, y = np.array(x), np.array(y)
    ks = []
    for _ in range(n):
        i = rng.integers(0, len(x), len(x))
        k, _ = kappa(x[i], y[i])
        if not np.isnan(k):
            ks.append(k)
    return [float(np.percentile(ks, 2.5)), float(np.percentile(ks, 97.5))]


def main(path):
    c1 = coder1()
    c2 = {r["setting_id"]: r for r in csv.DictReader(open(path))}
    ids = sorted(c1)
    assert set(ids) == set(c2), "coder 2 must code all 44 settings"
    res = {}
    for f in FIELDS:
        x = [c1[i][f] for i in ids]
        y = [c2[i][f] for i in ids]
        k, po = kappa(x, y)
        cats = sorted(set(x) | set(y))
        res[f] = {"kappa": round(k, 3), "ci95": [round(v, 3) for v in boot(x, y)],
                  "observed_agreement": round(po, 3), "n": len(ids),
                  "confusion_rows_coder1_cols_coder2": {a: {b: sum(1 for i in ids if c1[i][f] == a and c2[i][f] == b) for b in cats} for a in cats},
                  "disagreements": [i for i in ids if c1[i][f] != c2[i][f]]}
        if f in ("failure_status", "outcome_status"):
            bx = ["full" if v == "reported" else "other" for v in x]
            by = ["full" if v == "reported" else "other" for v in y]
            kb, pob = kappa(bx, by)
            res[f]["kappa_binary_reported_vs_other"] = round(kb, 3)
            res[f]["ci95_binary"] = [round(v, 3) for v in boot(bx, by)]
    out = os.path.join(HERE, "kappa-" + os.path.splitext(os.path.basename(path))[0] + ".json")
    json.dump(res, open(out, "w"), indent=1)
    for f, r in res.items():
        extra = f"  binary {r['kappa_binary_reported_vs_other']} {r['ci95_binary']}" if "kappa_binary_reported_vs_other" in r else ""
        print(f"{f:16} kappa {r['kappa']:6} {r['ci95']}  agree {r['observed_agreement']}{extra}  disagree {len(r['disagreements'])}")
    return res


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "coder2_ai.csv"))
