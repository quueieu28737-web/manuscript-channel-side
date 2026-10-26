#!/usr/bin/env python3
"""Recompute the SoK audit counts from the LaTeX tables and flag inconsistencies.

Usage:  python3 tools/audit_check.py [--json out.json]
Exit status is 1 if any check fails, so the script can run before each PDF build.

Sources parsed (all under tables/):
  r9-record-index.tex     Table 13: 39 records, measurement mode, markers
  r19-record-audit.tex    S-table: 39 x 9 record-level R1..R9 cells
  family-audit-matrix.tex Table 9: 20 x 9 family-level cells + Bound/Applicable rows
  r19-joint-bindings.tex  Table 10: query accounting
  r26-current-sensitivity.tex  current status-relaxation counts
  r26-cohort-rules.tex    cohort sizes and pair counts
"""
import hashlib
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "tables"
FAIL = []
PASS = []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))


def norm(cell):
    cell = re.sub(r"\\textbf\{(.)\}", r"\1", cell).replace("\\\\", "").strip()
    return "--" if cell in ("-", "--") else cell


def cite_key(s):
    m = re.search(r"\\cite\{([^}]*)\}", s)
    return m.group(1) if m else None


# ---------------------------------------------------------------- parsing
def parse_record_index():
    recs = []
    for line in (T / "r9-record-index.tex").read_text().splitlines():
        m = re.match(r"\\textsf\{(.+?)\}(\$\^\{\\(d?dagger)\}\$)?~\\cite\{([^}]*)\}\s*&\s*(\w+)\s*&", line.strip())
        if m:
            recs.append(dict(id=m.group(1), family=m.group(4), mode=m.group(5),
                             contextual=m.group(3) == "ddagger", added=m.group(3) == "dagger"))
    return recs


def parse_record_cells():
    out = {}
    for line in (T / "r19-record-audit.tex").read_text().splitlines():
        if "\\cite" in line and line.count("&") >= 10:
            parts = line.split("&")
            rid = re.sub(r"\\allowbreak\{\}|\$\\dagger\$|~\\cite.*", "", parts[0]).strip()
            out[rid] = dict(family=cite_key(parts[0]), contextual="dagger" in parts[0],
                            cells=[norm(c) for c in parts[1:10]], rationale=parts[10].strip().rstrip("\\"))
    return out


def parse_family_matrix():
    fam, footer = {}, {}
    for line in (T / "family-audit-matrix.tex").read_text().splitlines():
        if "\\cite" in line and "&" in line:
            parts = line.split("&")
            fam[cite_key(parts[0])] = [norm(c) for c in parts[1:10]]
        for label in ("Bound", "Applicable"):
            m = re.search(label + r"\s*&([^\\]*)\\\\", line)
            if m:
                footer[label] = [int(x) for x in m.group(1).split("&")]
    return fam, footer


def parse_query_table(fname, ncols):
    rows = {}
    for line in (T / fname).read_text().splitlines():
        m = re.match(r"([A-Za-z][A-Za-z +]+?)\s*&(.*)\\\\", line.strip())
        if m and m.group(1).strip() not in ("Query",):
            vals = [v.strip() for v in m.group(2).split("&")]
            if len(vals) == ncols:
                rows[m.group(1).strip()] = vals
    return rows


def parse_cohorts():
    rows = {}
    for line in (T / "r26-cohort-rules.tex").read_text().splitlines():
        m = re.match(r"([a-z ]+?)\s*&\s*(\d+)\s*&\s*(\d+)\s*&", line.strip())
        if m:
            rows[m.group(1)] = (int(m.group(2)), int(m.group(3)))
    return rows


QUERIES = {
    "Inference + utility": [7, 8],
    "Inference + cost": [7, 9],
    "Matched adaptation + inference": [4, 5, 7],
    "Inference + utility + cost": [7, 8, 9],
    "All five bindings": [4, 5, 7, 8, 9],
}
PRECEDENCE = ["B", "P", "?", "U", "A", "--"]  # documented existential availability projection


def peer_reviewed_keys():
    """Explicit venue-linked membership; a family's inspected version may be a preprint."""
    rows = json.loads((ROOT / "data/publication-strata.json").read_text(encoding="utf-8"))["families"]
    assert len(rows) == len({r["family"] for r in rows}) == 20
    return {r["family"] for r in rows if r["stratum"] == "venue_linked"}


def query(mit, items, accept=("B",)):
    out = [r for r in mit if any(mit[r]["cells"][i - 1] == "--" for i in items)]
    elig = [r for r in mit if r not in out]
    bound = [r for r in elig if all(mit[r]["cells"][i - 1] in accept for i in items)]
    return len(out), len(elig), bound


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    args = ap.parse_args()

    idx = parse_record_index()
    cells = parse_record_cells()
    fam, footer = parse_family_matrix()

    # ---------------------------------------------------------- record census
    n = len(idx)
    check("Table 13 lists 39 records", n == 39, f"found {n}")
    check("record index and record-cell table list the same IDs",
          set(r["id"] for r in idx) == set(cells),
          f"only in index: {sorted(set(r['id'] for r in idx) - set(cells))}; only in cells: {sorted(set(cells) - set(r['id'] for r in idx))}")
    modes = Counter(r["mode"] for r in idx)
    check("mode counts Ex20/Tr6/Si5/Co6/Un2", modes == Counter(Ex=20, Tr=6, Si=5, Co=6, Un=2), dict(modes))
    ctx = [r for r in idx if r["contextual"]]
    check("6 contextual records", len(ctx) == 6, len(ctx))
    check("6 final-search additions", sum(r["added"] for r in idx) == 6, sum(r["added"] for r in idx))
    fams = defaultdict(list)
    for r in idx:
        fams[r["family"]].append(r)
    check("26 families in ledger", len(fams) == 26, len(fams))
    mit_fams = {f for f, rs in fams.items() if not any(x["contextual"] for x in rs)}
    check("20 mitigation families", len(mit_fams) == 20, len(mit_fams))
    multi = {f: rs for f, rs in fams.items() if len(rs) > 1}
    check("11 multi-record families", len(multi) == 11, len(multi))
    multimode = [f for f, rs in multi.items() if len({x["mode"] for x in rs}) > 1]
    check("9 multi-record families span >1 mode", len(multimode) == 9, len(multimode))
    sfp = sum(len(rs) * (len(rs) - 1) // 2 for rs in fams.values())
    check("15 same-family pairs", sfp == 15, sfp)
    check("741 = C(39,2) pairs", n * (n - 1) // 2 == 741)
    check("351 = 39 x 9 record cells", len(cells) * 9 == 351, len(cells) * 9)

    # ---------------------------------------------------------- cohorts
    coh = parse_cohorts()
    check("cohort record sizes sum to 39", sum(v[0] for v in coh.values()) == 39, coh)
    check("cohort pair counts = C(size,2)", all(p == s * (s - 1) // 2 for s, p in coh.values()), coh)
    check("related pairs = 133", sum(v[1] for v in coh.values()) == 133, sum(v[1] for v in coh.values()))

    # ---------------------------------------------------------- Table 9 footer
    names = list(fam)
    bound = [sum(fam[f][j] == "B" for f in names) for j in range(9)]
    appl = [sum(fam[f][j] != "--" for f in names) for j in range(9)]
    check("Table 9 Bound row matches its cells", bound == footer.get("Bound"), f"cells {bound} vs row {footer.get('Bound')}")
    check("Table 9 Applicable row matches its cells", appl == footer.get("Applicable"), f"cells {appl} vs row {footer.get('Applicable')}")

    # ---------------------------------------------------------- family vs record aggregation
    mit = {r: v for r, v in cells.items() if not v["contextual"]}
    check("33 mitigation records", len(mit) == 33, len(mit))
    agg_mismatch = []
    agg = {}
    for f in names:
        recs = [v["cells"] for v in mit.values() if v["family"] == f]
        row = []
        for j in range(9):
            col = [c[j] for c in recs]
            a = next((s for s in PRECEDENCE if s in col), "--")
            row.append(a)
            if a != fam[f][j]:
                agg_mismatch.append(dict(family=f, item=f"R{j+1}", family_cell=fam[f][j], record_cells=col))
        agg[f] = row
    check("Family matrix equals documented record-derived availability projection",
          not agg_mismatch, f"{len(agg_mismatch)} mismatches")
    agg_bound = [sum(agg[f][j] == "B" for f in names) for j in range(9)]
    agg_appl = [sum(agg[f][j] != "--" for f in names) for j in range(9)]

    # ---------------------------------------------------------- Table 10 + stress tables
    t10 = parse_query_table("r19-joint-bindings.tex", 4)
    stress = parse_query_table("r26-current-sensitivity.tex", 5)
    recomputed = {}
    for q, items in QUERIES.items():
        o, e, b = query(mit, items)
        famcfg = len({mit[r]["family"] for r in b})
        recomputed[q] = dict(out=o, eligible=e, bound=len(b), bound_records=b,
                             BP=len(query(mit, items, ("B", "P"))[2]),
                             BQ=len(query(mit, items, ("B", "?"))[2]),
                             BPQ=len(query(mit, items, ("B", "P", "?"))[2]), families=famcfg)
        if q in t10:
            o_, e_, b_ = (int(x) for x in t10[q][:3])
            check(f"Table 10 '{q}' Out/Eligible/Bound", (o, e, len(b)) == (o_, e_, b_), f"recomputed {(o, e, len(b))} vs table {(o_, e_, b_)}")
        if q in stress:
            s = [int(x) for x in stress[q]]
            r = [e, len(b), recomputed[q]["BP"], recomputed[q]["BQ"], recomputed[q]["BPQ"]]
            check(f"current stress table '{q}'", s == r, f"recomputed {r} vs table {s}")

    check("all five joint query rows present", set(t10) == set(QUERIES), sorted(t10))
    check("all five sensitivity query rows present", set(stress) == set(QUERIES), sorted(stress))
    witnesses = json.loads((ROOT / "data/family-record-witnesses.json").read_text(encoding="utf-8"))
    expected = [{"family": f, "item": f"R{j+1}", "status": agg[f][j],
                 "records": [{"id": rid, "status": rec["cells"][j], "source_scope": rec["rationale"]}
                             for rid, rec in mit.items() if rec["family"] == f]}
                for f in names for j in range(9)]
    check("180 source-linked aggregation witnesses", witnesses["cells"] == expected and len(expected)==180)
    check("record-source hash matches aggregation witnesses", witnesses["source_sha256"] == hashlib.sha256((T/"r19-record-audit.tex").read_bytes()).hexdigest())
    stratified = json.loads((ROOT/"data/publication-query-counts.json").read_text())
    pkeys=peer_reviewed_keys()
    groups={"all":mit,"venue":{k:v for k,v in mit.items() if v["family"] in pkeys},"other":{k:v for k,v in mit.items() if v["family"] not in pkeys}}
    expected_strata={}
    for label, items in QUERIES.items():
        expected_strata[label]={}
        for group, records in groups.items():
            o,e,b=query(records,items)
            expected_strata[label][group]={"excluded":o,"eligible":e,"bound":len(b),"bound_ids":b}
    check("all 15 stratified query cells and member IDs reproduce", stratified["queries"]==expected_strata)
    st=parse_query_table("r32-publication-strata.tex",3)
    check("stratified publication table matches records", set(st)==set(QUERIES) and all(st[q]==[str(expected_strata[q][g]["bound"])+"/"+str(expected_strata[q][g]["eligible"]) for g in groups] for q in QUERIES))
    # ---------------------------------------------------------- venue sensitivity (informational)
    pr = peer_reviewed_keys()
    strata = json.loads((ROOT / "data/publication-strata.json").read_text(encoding="utf-8"))["families"]
    check("publication strata cover precisely the mitigation families", {x["family"] for x in strata} == mit_fams)
    pr_fams = sorted(f for f in mit_fams if f in pr)
    pr_mit = {r: v for r, v in mit.items() if v["family"] in pr}
    venue = dict(peer_reviewed_mitigation_families=pr_fams,
                 preprint_mitigation_families=len(mit_fams) - len(pr_fams),
                 joins_peer_reviewed_only={q: (query(pr_mit, it)[1], len(query(pr_mit, it)[2])) for q, it in QUERIES.items()})

    # ---------------------------------------------------------- leftover '?' cells
    q_cells = [(r, f"R{j+1}") for r, v in cells.items() for j, c in enumerate(v["cells"]) if c == "?"]

    report = dict(venue_sensitivity=venue, passed=len(PASS), failed=len(FAIL), failures=FAIL, family_record_mismatches=agg_mismatch,
                  table9_bound_if_aggregated=agg_bound, table9_applicable_if_aggregated=agg_appl,
                  record_level_unverified_cells=q_cells, queries=recomputed,
                  record_status_counts=Counter(c for v in cells.values() for c in v["cells"]))
    for name, d in PASS:
        print(f"PASS  {name}")
    for name, d in FAIL:
        print(f"FAIL  {name}: {d}")
    if agg_mismatch:
        print("\nFamily (Table 9) vs record-level cells:")
        for m in agg_mismatch:
            print(f"  {m['family']:<24} {m['item']}: Table 9 = {m['family_cell']:<2}  records = {m['record_cells']}")
        print(f"  Table 9 Bound row if aggregated from records: {agg_bound} (printed {footer.get('Bound')})")
    print(f"\nRecord-level '?' cells remaining: {len(q_cells)} -> {q_cells}")
    print(f"\nVenue-linked mitigation families (inspected-version scope retained): {len(pr_fams)}/20 {pr_fams}")
    print("Joins restricted to peer-reviewed families (eligible, bound):")
    for q, v in venue["joins_peer_reviewed_only"].items():
        print(f"  {q:<32} {v}")
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2, default=str))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
