# R109: core-contribution revision with C1–C3 robustness analyses

- [Main PDF](main.pdf) · [Supplement PDF](supplement.pdf) · [LaTeX ZIP](latex-source.zip) · [Source](source/)
- [C1–C3 plan, code, freeze, results and verifier](c-ext/RESULTS.md)

## What R109 adds
Finding 3 is now a complete attack → robustness → countermeasure → cost result:

| Review concern | R109 answer | Evidence |
|---|---|---|
| W1 strawman ("you broke your own naive gateway") | Structural argument: cover generated outside the model loop lacks planner latency. Timing-matched dispatch returns the best attack to within 0–3/120 of the size view, at +12–16% latency. | §7.1, Table 7 (Matched, +Lat), S10 Table 36 |
| W2 client timestamps vs network | Refitted removal stays at 107–116/120 under σ = 100 ms jitter and 98–115/120 under σ = 200 ms; pre-registered criterion holds at every σ | Table 7 (Jit.), S10 Table 35 |
| W3 labelled-training privilege | An unsupervised GMM gap rule detects 1,820/1,820 decoys with 0 false removals; strip 107–116/120 | Table 7 (Strip), S10 Table 34 |
| W4 "timing helps discard but not classify" overreach | Reframed: a mechanism-aware attack succeeds where a generic learner on the same features fails, as in WF | §7.1 |
| W5 SoK vs attack paper | Intro: the controlled case is the strongest test of the SoK's procedure, which shows that a defense passing size-only evaluation fails | §1 |
| Minor 1–4 | Statistics out of the abstract; client-receipt timing defined; Table 7 caption and column groups explain every column; conclusion echoes Findings 1–3 | Abstract, §1, Table 7, §11 |

C1–C3 were frozen and pushed (commit `ed2388a`) before any test quantity was
computed. A reproduction gate first matched the original predictions and all 12
B1 strip counts exactly. `c-ext/verify_c.py` independently recomputes the
detector counts, tests and criteria. The pre-registered C3 "within 10 points"
rule is not met in 7/10 cells, because stripping falls further *below* the
size view; this is reported as such.

Main: 15 pages, body ends on page 13. Supplement: 32 pages (new S10).
No new LLM collection; a live timing-matched cohort (B2) remains future work.
