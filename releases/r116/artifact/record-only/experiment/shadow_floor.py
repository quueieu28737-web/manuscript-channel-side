"""Pair-ambiguity floor for planner-generated shadow cover.

An idealized attacker perfectly partitions the real chain and k shadow chains
and recovers every chain's action label, but not which chain is real. The real
chain is exchangeable with the shadows, so guessing label c succeeds with
probability n_c/(k+1); the best guess is the modal label. This script computes
the expected success exactly by enumeration, for shadow labels drawn
independently and uniformly from C classes ("iid") and for shadow labels drawn
without replacement from the classes other than the real one ("distinct").
It also evaluates the floor realized by the R110 live test split.
"""
import itertools
import json
from fractions import Fraction
from pathlib import Path

C = 6


def iid_floor(k: int, c: int = C) -> Fraction:
    total = Fraction(0)
    for labels in itertools.product(range(c), repeat=k + 1):
        counts = [labels.count(x) for x in set(labels)]
        total += Fraction(max(counts), k + 1)
    return total / c ** (k + 1)


def distinct_floor(k: int, c: int = C) -> Fraction:
    if k > c - 1:
        raise ValueError("distinct sampling needs k <= C-1")
    return Fraction(1, k + 1)


def realized_floor(n_test: int, n_matching: int) -> Fraction:
    """k=1 floor on a realized split: matching pairs are always recoverable."""
    return Fraction(2 * n_matching + (n_test - n_matching), 2 * n_test)


def main() -> None:
    rows = []
    for k in range(0, 5):
        row = {"k": k, "iid_floor": float(iid_floor(k)), "iid_floor_exact": str(iid_floor(k)),
               "token_factor_nominal": k + 1}
        if 1 <= k <= C - 1:
            row["distinct_floor"] = float(distinct_floor(k))
        rows.append(row)
    # R110 live split (Supplement S2.5): 120 test fixtures, 21 matching labels per model.
    realized = realized_floor(120, 21)
    observed = {"qwen3:8b": {"selected": 54, "test_max_call_window": 70},
                "llama3.1:8b": {"selected": 64, "test_max_call_window": 64}}
    # Bounds on real-label accuracy among the 99 distinct-label fixtures,
    # using only the aggregate count (correct on matching fixtures is between 0 and 21).
    bounds = {m: {"attack_correct": v["test_max_call_window"],
                  "distinct_correct_lower": max(0, v["test_max_call_window"] - 21),
                  "distinct_correct_upper": min(99, v["test_max_call_window"])}
              for m, v in observed.items()}
    out = {"classes": C, "floors": rows,
           "realized_k1_floor": {"n_test": 120, "n_matching": 21, "value": float(realized),
                                 "count_equivalent": float(realized * 120)},
           "observed_shadow": observed, "distinct_label_bounds": bounds}
    path = Path(__file__).resolve().parent.parent / "analysis" / "shadow-floor.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
