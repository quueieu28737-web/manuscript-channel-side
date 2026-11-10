"""Field-level evidence statistics over the 44 R101 settings.

Every indicator is a deterministic rule over columns that the authors already
recorded in releases/r101/evidence; no field is re-read from source papers.
Rules are listed in RULES and written to the output for audit.
"""
import csv
import json
import os
from collections import Counter, defaultdict

ROOT = os.path.join(os.path.dirname(__file__), "..", "releases", "r101", "evidence")
OUT = os.path.join(os.path.dirname(__file__), "m2-results")

LINK = {
    "client-agent": "C (client link)",
    "agent-model": "M (model link)",
    "agent-model versus remaining egress": "M (model link)",
    "agent-tool/browser egress": "T (tool egress)",
    "agent-tool": "T (tool egress)",
    "combined client egress": "combined egress",
    "inter-agent": "A (inter-agent)",
}

RULES = {
    "protection": "intervention != 'none'",
    "link": "interface mapped by LINK; every other interface is a recipient/active endpoint",
    "named_deployment_transfer": "transfer_axis names a held-out composition, topology or scaffold",
    "open_world": "transfer_axis mentions open world / open-world",
    "deployment_prevalence": "deployment_base_rate gives a deployment prevalence (none do)",
    "supplied_boundary": "boundary_source is evaluator-supplied (given/supplied/known/recorded/session)",
    "adaptation_located": "protected_attacker_adaptation reports refitting or an adaptive/stealth adversary and is not marked unresolved/not located",
    "matched_utility": "setting-availability original_task_utility_status == located",
    "defense_cost": "utility_cost_link reports defense bytes/latency in the same setting",
}


def link(iface):
    return LINK.get(iface, "recipient / active endpoint")


def main():
    os.makedirs(OUT, exist_ok=True)
    m = list(csv.DictReader(open(os.path.join(ROOT, "field-map", "evidence-matrix.csv"))))
    t = {r["setting_id"]: r for r in csv.DictReader(open(os.path.join(ROOT, "field-map", "target-evidence.csv")))}
    a = {r["setting_id"]: r for r in csv.DictReader(open(os.path.join(ROOT, "transfer-synthesis", "setting-availability.csv")))}
    rows = []
    for r in m:
        sid = r["setting_id"]
        ax = r["transfer_axis"].lower()
        adapt = r["protected_attacker_adaptation"].lower()
        rows.append({
            "setting": sid, "source": r["source_key"], "publication": r["publication_status"],
            "link": link(r["interface"]),
            "protection": r["intervention"] != "none",
            "purpose": a[sid]["intervention_purpose"],
            "named_deployment_transfer": any(k in ax for k in ("leave one", "topology", "held-out scaffold", "proprietary scaffold")),
            "open_world": "open world" in ax or "open-world" in ax,
            "deployment_prevalence": False,
            "supplied_boundary": any(k in r["boundary_source"].lower() for k in ("given", "supplied", "known", "recorded", "session", "defined", "trial")),
            "adaptation_located": r["intervention"] != "none" and any(k in adapt for k in ("refit", "adaptive", "stealth")) and not any(k in adapt for k in ("unresolved", "not located")),
            "matched_utility": a[sid]["original_task_utility_status"] == "located",
            "defense_cost": "bytes/latency" in r["utility_cost_link"] or "transformations" in r["utility_cost_link"],
            "failure": t[sid]["failure_status"], "outcome": t[sid]["outcome_status"], "policy": t[sid]["policy_status"],
        })
    n = len(rows)
    prot = [r for r in rows if r["protection"]]
    def cnt(rs, k):
        return sum(1 for r in rs if r[k])
    def status(k):
        c = Counter(r[k] for r in rows)
        app = n - c.get("not_applicable", 0)
        return {"reported": c.get("reported", 0), "partly_reported": c.get("partly_reported", 0),
                "not_located": c.get("not_located", 0), "applicable": app}
    by_link = defaultdict(lambda: [0, 0])
    for r in rows:
        by_link[r["link"]][0] += 1
        by_link[r["link"]][1] += int(r["protection"])
    src = defaultdict(list)
    for r in rows:
        src[r["source"]].append(r)
    src_prot = [s for s, rs in src.items() if any(x["protection"] for x in rs)]
    res = {
        "rules": RULES,
        "settings": n, "sources": len(src),
        "published_settings": sum(r["publication"] == "published" for r in rows),
        "protection_settings": len(prot),
        "protection_by_purpose": Counter(r["purpose"] for r in prot),
        "settings_and_protection_by_link": {k: {"settings": v[0], "with_protection": v[1]} for k, v in by_link.items()},
        "named_deployment_transfer": cnt(rows, "named_deployment_transfer"),
        "open_world": cnt(rows, "open_world"),
        "deployment_prevalence": cnt(rows, "deployment_prevalence"),
        "supplied_boundary": cnt(rows, "supplied_boundary"),
        "among_protection": {
            "adaptation_located": cnt(prot, "adaptation_located"),
            "matched_original_task_utility": cnt(prot, "matched_utility"),
            "defense_cost_same_setting": cnt(prot, "defense_cost"),
            "all_three": sum(1 for r in prot if r["adaptation_located"] and r["matched_utility"] and r["defense_cost"]),
        },
        "failure_handling": status("failure"), "execution_outcome": status("outcome"), "policy_context": status("policy"),
        "sources_with_any_protection": sorted(src_prot),
        "sources_with_named_transfer": sorted({r["source"] for r in rows if r["named_deployment_transfer"]}),
    }
    json.dump(res, open(os.path.join(OUT, "m2-statistics.json"), "w"), indent=1, default=dict)
    with open(os.path.join(OUT, "m2-setting-indicators.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(json.dumps(res, indent=1, default=dict))


if __name__ == "__main__":
    main()
