# R110 D: adaptive attacks against timing-matched dispatch

This is a retrospective offline reanalysis of the public cover cohort (3,600 episodes; 120 paired
test fixtures per model). The plan, code and input hashes were frozen and pushed in commit
`1b4e368` before any D test quantity was computed. The pre-freeze exposure is listed in
`analysis-plan.json`. `verify_d.py` re-derives every selection, p-value, Holm family and rule
from the saved records: **242/242 checks pass**.

**Reproduction gate: passed.** All 20 R109 C3a/C3b strip and timing+size counts reproduce
exactly.

## D1/D3 — the cover's own protection level, with position rules included

Timing-matched dispatch leaves the destination sequence unchanged. Position rules therefore
score the same as on the unmatched cover:

- **Qwen:** the last-destination rule scores 75–77/120. The validation-selected size-only best
  is that rule in all five arms, not the byte learner (61–63).
- **Llama:** the size-only best is byte-RF (72–82) in four arms and the last-destination rule
  (65) in the live-write arm.

The size-only best is the correct baseline for "returns to the size-only level". The cover alone
reduces recognition from 118 to 75–77 (Qwen) and from 113 to 65–82 (Llama). This is not a
halving.

## D2 — adaptive attacks on gap+duration-matched dispatch (C3b)

| Model | Size-only best | Adaptive best (validation-selected) | Joint decoding | Context strip | R109 strip |
|---|---|---|---|---|---|
| Qwen | 75–77 | 76–86 | 76–86 | 68–79 | 43–57 |
| Llama | 65–82 | 87–97 | 87–97 | 80–89 | 55–66 |

**Primary family:** adaptive best minus size-only best, 10 exact McNemar tests, Holm.

- Qwen: −0.8 to +7.5 points; no cell rejects.
- Llama: +5.0 to +22.5 points; two cells reject (read +14.2, Holm p = .030; live write +22.5,
  Holm p = .002).
- **Pre-registered rule:** "does not withstand" requires at least 5 of 10 cells with ≥ 12/120
  and Holm < .05. It is **not met (2/10)**. We therefore report that C3b withstands the tested
  adaptive attacks relative to the size-only best, with a significant residual timing gain in two
  Llama cells. This is not an equivalence claim.

The context detector separates matched decoys at the call level with AUROC .93–.94 (R109's
detector: .82–.88). The precision is .68–.77, against .46–.57 for R109's detector.

## D4 — position-conditioned dispatch (C3c)

Drawing each decoy gap from honest gaps at the same call position does not remove the residual.
The secondary family again has two Llama cells that reject (read +21.7, live write +20.0); the
rule is not met (2/10). Detector AUROC stays at .92–.94. Added latency is 12.0–16.8%.

## Post-hoc exploratory: what carries the separability

`exploratory/feature-groups.json` was run after the frozen results were saved and tests no
claim. It reports context-detector test AUROC on non-first calls:

| Variant | All features | No timing | Timing only |
|---|---|---|---|
| C3b | .91–.92 | .83–.85 | .80–.81 |
| C3c | .91–.92 | .83–.85 | .82 |

Decoys stay separable without any timing input, through destination and position context alone,
and also from timing alone. A decoy schedule that is drawn independently of the planner's
destination sequence is visible even when its timing is matched.

## Implication for Finding 3

- Timing-matched dispatch removes the large unmatched removal advantage (107–116 → at most 97).
- It does not make cover indistinguishable. Matching the marginal gap/duration distribution, or
  the position-conditioned one, leaves call-level separability. An attacker that decodes the
  removal jointly with the task can still exceed the size-only best, by up to 22.5 points for
  Llama.
- To be indistinguishable, cover generated outside the model loop must reproduce the planner's
  joint destination-sequence and timing behavior, not only its timing marginals.
- A live cohort and record-level timestamps remain untested.
