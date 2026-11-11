# R109 C1–C3: robustness of timing-informed cover removal, and the fix

Retrospective offline reanalysis of the public M3 cohort (3,600 episodes,
1,440 held-out). The plan, code and input hashes were frozen and pushed in commit
`ed2388a` before any C test quantity was computed; `freeze.json` records the
hashes. Exposure: B1 test results were known, and validation gap extremes and the
B1 validation candidate table had been viewed (see analysis-plan.json).

**Reproduction gate:** passed. Refitted byte-only LR/RF predictions equal the
original M3 predictions, and all 12 B1 strip counts reproduce exactly.

## C2 — no cover labels needed
An unsupervised 2-component GMM on unlabeled training log-gaps gives thresholds
of 0.189 s (Qwen) and 0.142 s (Llama). On test, the rule detects cover with
precision = recall = 1.000 in all 10 arms. Stripping recovers 111–115/120 (Qwen)
and 107–116/120 (Llama), against byte-view scores of 61–63 and 72–82. All 10
Holm-adjusted p ≤ 6.2e-6. Fixed 0.1 s and 0.2 s rules give identical counts.

## C1 — robust to network-like jitter
Half-normal jitter is added independently to every call start and end (5 draws).
Mean adaptive strip recognition:

| σ | Qwen (5 arms) | Llama (5 arms) |
|---|---|---|
| 10 ms | 110.2–114.8 | 107.0–115.6 |
| 50 ms | 110.6–114.0 | 107.0–115.8 |
| 100 ms | 109.8–113.2 | 107.0–116.0 |
| 200 ms | 98.4–105.6 | 105.4–114.8 |

The pre-registered robustness criterion (≥ byte + 24/120 in every arm) holds at
every σ. A detector frozen on clean data degrades (Qwen 76.8–80.0 at 200 ms);
refitting restores performance.

## C3 — timing-matched dispatch removes the removal advantage
Counterfactual: decoy gaps (C3a) or gaps and durations (C3b) are drawn from the
defender's own no-cover training history. The attacker is fully refitted.

- C3b strip recognition falls to 43–57 (Qwen) and 55–66 (Llama). All 10 drops
  vs. B1 strip are significant (Holm p ≤ 2.1e-10).
- The best reported attack (max of byte, direct timing+size, strip) returns to
  within 0–3/120 of the byte view in every arm.
- The detector still has AUROC 0.82–0.88 but precision only 0.46–0.57, so
  stripping deletes honest calls and falls below the byte view in 10/10 arms.
- Pre-registered rule "strip within 10 pp of byte in every arm": not met
  (3/10 arms), because 7 arms fall more than 10 pp *below* the byte view.
  Only Llama/isolated is significantly below (Holm p = .003).
- Cost: +1.08–1.12 s (Qwen) and +1.28–1.34 s (Llama) per covered episode,
  i.e. 12.3–12.8% and 15.7–16.4% of mean no-cover wall time.
  C3a (gap only): strip 30–55, +1.04–1.23 s.

## Limits
Receipt timestamps, local loopback, supplied windows. C3 is a receipt-level
simulation that assumes planner behaviour is unaffected by decoy delay (true for
hidden cover because the planner never sees it). It is not a collected cohort;
B2 would measure it live. Intervals and tests condition on the fitted attacks.
