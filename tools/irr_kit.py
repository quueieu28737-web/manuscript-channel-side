#!/usr/bin/env python3
"""Inter-rater reliability (IRR) kit for the 351 record-item cells.

Two subcommands:

  make-sheet   Write a blinded coding sheet for an independent second coder.
               The sheet lists record ID, cited source, the source locator from
               Table 13 and the item; the original code and rationale are omitted.
               python3 tools/irr_kit.py make-sheet --out irr/coder2_sheet.csv [--seed 7]

  make-pair-sheet  Write a blinded sheet of the related pairs (same cohort) for
               coder 2.  Needs the released record->cohort file
               (columns record_id, cohort), which is not in this repository.
               python3 tools/irr_kit.py make-pair-sheet --membership cohorts.csv

  score-pairs  Agreement on pair judgments (C = compatible, M = mismatch,
               U = unresolved) between two CSVs with record_a, record_b, judgment.

  score        Compare coder 2's codes with the archived record cells.
               Reports per-item and overall agreement, Cohen's kappa,
               Krippendorff's alpha (nominal) with a record-cluster bootstrap CI,
               the confusion matrix, and whether the headline joint-query
               counts (Table 10) survive when coder 2's codes are used.
               python3 tools/irr_kit.py score --coder2 irr/coder2_sheet.csv

Coder 2's file must contain columns record_id, item (R1..R9) and code
(one of B, P, U, A, ?, --).  Blank codes are ignored for agreement and
treated as missing.
"""
import argparse
import csv
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_check import QUERIES, parse_record_cells, parse_record_index  # noqa: E402

CODES = ["B", "P", "U", "A", "?", "--"]
ITEMS = [f"R{i}" for i in range(1, 10)]


def archived():
    cells = parse_record_cells()
    return {(rid, ITEMS[j]): v["cells"][j] for rid, v in cells.items() for j in range(9)}, cells


def make_sheet(out, seed):
    idx = {r["id"]: r for r in parse_record_index()}
    loc = {}
    for line in (Path(__file__).resolve().parents[1] / "tables/r9-record-index.tex").read_text().splitlines():
        if line.startswith("\\textsf{"):
            rid = line.split("}")[0][len("\\textsf{"):]
            loc[rid] = line.split("&")[2].strip().rstrip("\\").strip()
    rows = [dict(record_id=rid, family_cite=idx[rid]["family"], scope_and_locator=loc.get(rid, ""),
                 contextual="yes" if idx[rid]["contextual"] else "no", item=it, code="", note="")
            for rid in idx for it in ITEMS]
    random.Random(seed).shuffle(rows)  # break record order so codes are not copied row-to-row
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} cells for {len(idx)} records to {out}")


def kappa(pairs):
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def kripp_alpha(pairs):
    """Nominal Krippendorff's alpha for two coders, no missing values within a unit."""
    n = 2 * len(pairs)
    tot = Counter()
    do = 0
    for a, b in pairs:
        tot[a] += 1
        tot[b] += 1
        do += 2 * (a != b)
    de = sum(tot[c] * tot[k] for c in tot for k in tot if c != k)
    return 1.0 if de == 0 else 1 - (n - 1) * do / de


def joint_counts(codes, cells):
    mit = [rid for rid, v in cells.items() if not v["contextual"]]
    out = {}
    for q, items in QUERIES.items():
        elig = [r for r in mit if all(codes[(r, f"R{i}")] != "--" for i in items)]
        bound = [r for r in elig if all(codes[(r, f"R{i}")] == "B" for i in items)]
        out[q] = (len(elig), len(bound), sorted(bound))
    return out


def score(path, boots, seed):
    arch, cells = archived()
    c2 = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            code = row["code"].strip()
            if code == "-":
                code = "--"
            if code:
                if code not in CODES:
                    sys.exit(f"invalid code {code!r} for {row['record_id']} {row['item']}")
                c2[(row["record_id"], row["item"])] = code
    keys = [k for k in arch if k in c2]
    if not keys:
        sys.exit("no coded cells found")
    pairs = [(arch[k], c2[k]) for k in keys]
    print(f"coded cells: {len(keys)}/{len(arch)}")
    print(f"overall agreement {sum(a == b for a, b in pairs) / len(pairs):.3f}  "
          f"Cohen kappa {kappa(pairs):.3f}  Krippendorff alpha {kripp_alpha(pairs):.3f}")

    # applicability (-- vs not) and binding (B vs not) are the two decisions that drive the joins
    app = [(a == "--", b == "--") for a, b in pairs]
    bnd = [(a == "B", b == "B") for a, b in pairs]
    print(f"applicability kappa {kappa(app):.3f}   bound-vs-not kappa {kappa(bnd):.3f}")

    recs = sorted({k[0] for k in keys})
    by_rec = defaultdict(list)
    for k in keys:
        by_rec[k[0]].append((arch[k], c2[k]))
    rng = random.Random(seed)
    al = []
    for _ in range(boots):
        sample = [p for r in (rng.choice(recs) for _ in recs) for p in by_rec[r]]
        al.append(kripp_alpha(sample))
    al.sort()
    print(f"alpha 95% record-cluster bootstrap CI [{al[int(.025 * boots)]:.3f}, {al[int(.975 * boots) - 1]:.3f}]  ({boots} draws)")

    print("\nper item: n  agreement  kappa")
    for it in ITEMS:
        p = [(arch[k], c2[k]) for k in keys if k[1] == it]
        if p:
            print(f"  {it}: {len(p):3d}  {sum(a == b for a, b in p) / len(p):.3f}  {kappa(p):.3f}")

    print("\nconfusion (rows archived, cols coder 2):")
    print("      " + " ".join(f"{c:>4}" for c in CODES))
    cm = Counter(pairs)
    for a in CODES:
        print(f"  {a:>3} " + " ".join(f"{cm[(a, b)]:>4}" for b in CODES))

    if len(keys) == len(arch):
        print("\nheadline joins, archived vs coder 2 (eligible, bound):")
        ja, jb = joint_counts(arch, cells), joint_counts(c2, cells)
        for q in QUERIES:
            flag = "" if ja[q][:2] == jb[q][:2] else "   <-- differs"
            print(f"  {q:<32} {ja[q][:2]}  vs  {jb[q][:2]}{flag}")
            if flag:
                print(f"      coder-2 bound records: {jb[q][2]}")
    disagreements = [(k, arch[k], c2[k]) for k in keys if arch[k] != c2[k]]
    out = Path(path).with_name(Path(path).stem + "_disagreements.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["record_id", "item", "archived", "coder2", "resolution", "resolved_code"])
        for (rid, it), a, b in sorted(disagreements):
            w.writerow([rid, it, a, b, "", ""])
    print(f"\n{len(disagreements)} disagreements written to {out} for adjudication")


def make_pair_sheet(membership, out, seed):
    idx = {r["id"]: r for r in parse_record_index()}
    coh = defaultdict(list)
    with open(membership) as f:
        for row in csv.DictReader(f):
            if row["record_id"] not in idx:
                sys.exit(f"unknown record {row['record_id']}")
            coh[row["cohort"].strip()].append(row["record_id"])
    rows = []
    for c, rs in sorted(coh.items()):
        for i, a in enumerate(sorted(rs)):
            for b in sorted(rs)[i + 1:]:
                rows.append(dict(cohort=c, record_a=a, record_b=b,
                                 same_family="yes" if idx[a]["family"] == idx[b]["family"] else "no",
                                 judgment="", reason=""))
    random.Random(seed).shuffle(rows)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} related pairs ({sum(r['same_family'] == 'yes' for r in rows)} same-family) to {out}")


def score_pairs(a_path, b_path):
    def load(p):
        with open(p) as f:
            return {tuple(sorted((r["record_a"], r["record_b"]))): r["judgment"].strip().upper()[:1]
                    for r in csv.DictReader(f) if r["judgment"].strip()}
    a, b = load(a_path), load(b_path)
    keys = sorted(set(a) & set(b))
    pairs = [(a[k], b[k]) for k in keys]
    print(f"pairs coded by both: {len(keys)}")
    print(f"agreement {sum(x == y for x, y in pairs) / len(pairs):.3f}  kappa {kappa(pairs):.3f}  "
          f"alpha {kripp_alpha(pairs):.3f}")
    cm = Counter(pairs)
    print("      " + " ".join(f"{c:>4}" for c in "CMU"))
    for x in "CMU":
        print(f"  {x:>3} " + " ".join(f"{cm[(x, y)]:>4}" for y in "CMU"))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make-sheet")
    m.add_argument("--out", default="irr/coder2_sheet.csv")
    m.add_argument("--seed", type=int, default=7)
    mp = sub.add_parser("make-pair-sheet")
    mp.add_argument("--membership", required=True)
    mp.add_argument("--out", default="irr/coder2_pairs.csv")
    mp.add_argument("--seed", type=int, default=7)
    sp = sub.add_parser("score-pairs")
    sp.add_argument("--archived", required=True)
    sp.add_argument("--coder2", required=True)
    s = sub.add_parser("score")
    s.add_argument("--coder2", required=True)
    s.add_argument("--boots", type=int, default=2000)
    s.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    if a.cmd == "make-sheet":
        make_sheet(a.out, a.seed)
    elif a.cmd == "make-pair-sheet":
        make_pair_sheet(a.membership, a.out, a.seed)
    elif a.cmd == "score-pairs":
        score_pairs(a.archived, a.coder2)
    else:
        score(a.coder2, a.boots, a.seed)


if __name__ == "__main__":
    main()
