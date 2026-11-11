# R110: Plan A (SoK positioning), adaptive attacks on timing-matched dispatch

- [Main PDF](main.pdf) · [Supplement PDF](supplement.pdf) · [LaTeX ZIP](latex-source.zip) · [Source](source/)
- [D analysis: plan, freeze, code, results, verifier](d-ext/RESULTS.md)
- [Blind second-coder packet](human-coding/CODER-INSTRUCTIONS.md)

## What R110 changes, by review point

| Review point | R110 response | Where |
|---|---|---|
| M2: "best attack" excluded position rules | Size-only best is now validation-selected among learners **and** position rules: 75–77 (Qwen), 65–82 (Llama). "Halves recognition" is removed. | Table 7 (Best), §7.1 Step 1, S11 |
| M3: no attack adapted to the countermeasure | New frozen analysis (D): a context detector (AUROC .93–.94 on matched decoys) and joint decoding. The adaptive best beats size-only best in 9/10 cells, with 2/10 Holm-significant. The pre-registered "defeated" rule is not met. A position-matched defender (PM) leaves the same 2 cells. | §7.1 Step 3, Table 7 (Adapt.), S11, Tables S37–S38 |
| M3: post-hoc reframing of the R109 criterion | The failure of the R109 matched-strip criterion (7/10 cells) is now stated in the main text. | §7.1 Step 3, §10 |
| M1: novelty vs. WTF-PAD / adaptive padding | Cites Adaptive Padding, WTF-PAD, FRONT and Tik-Tok. The Agent-specific result is that matched timing marginals leave the **destination schedule** visible (post-hoc ablation: AUROC .83–.85 without any timing input). Finding 3 is restated as "cover must imitate the planner's joint sequence and timing". | §1 Finding 3, §7.1, Table S39 |
| M4: Finding 1 rested on a negative pilot | Finding 1 now rests on the literature. The pilot is described as calibration with non-rejecting primary tests, and the main text states that Projected retains task fields. A category-free projection is added to Q2. | §1, §7.2, Table 9 |
| M5: AI-assisted coding / reliability | The coding protocol is described accurately: the author decides every code; the AI passes are a codebook audit, not inter-rater reliability. A blind second-coder packet is released. | §2.2, §10, S4.1, `human-coding/` |
| M6: SoK vs. attack paper | Abstract, introduction and contributions present §7.1 as a worked application of the procedure, not a new attack. | Abstract, §1 |
| M7: "1,440 executions" inflates n | The main text states 120 paired fixtures per model as the independent unit. Live-write numbers are removed from the abstract. | Abstract, §7.1 |
| Minor: naming collisions / internal codes | R108, M3, B1, C1–C3 (analyses) and C1–C3 (coders) are removed from typeset text. Coders are AU / AI-1 / AI-2; matched variants are GM / GDM / PM. The checklist keeps C1–C8. | Supplement |
| Minor: supplement table numbers | Supplement tables and figures are numbered S1, S2, … | Supplement |
| Minor: constant-rate shaping generalization | The claim is limited to the one tested configuration. | §6.2 |

## Verification

- **Reproduction gate.** The D analysis reproduces all 20 R109 C3 counts exactly.
- **Independent checks.** `d-ext/verify_d.py` passes 242/242 checks.
- **Generated tables.** Main Table 7 and Tables S37–S39 are generated from saved results by
  `tools/make_d_tables.py`, plus the in-session Table 7 script, whose values were cross-checked
  against `C1.json` and `C2.json`.
- **Clean build.** The ZIP rebuilds to text identical to the released PDFs.
- **Page budget.** Main: 16 pages; the body ends on page 13, references on pages 14–16.
  Supplement: 35 pages.

## Independent human coding (coder-1)

An independent security PhD researcher coded the blind packet (`human-coding/coder-1/`).
Agreement before discussion is 104/111 decisions:

| Field | Agreement | κ |
|---|---|---|
| Access class | 44/44 | 1 |
| Intervention purpose | 9/9 | 1 |
| Adaptation in the privacy settings | 4/4 | 1 |
| Utility in the privacy settings | 4/4 | 1 |
| Protection flag | 38/44 | .61 |
| Transfer relation | 5/6 | .77 |

The privacy denominator and every Finding 2 decision are reproduced. §2.2, §10 and S4.1 report
these numbers.

### Author adjudication (final)

The coder's code was adopted for CG-composition (counted with CG-transform), FAY-network,
FAY-combined, ATR-main, ATR-budget and T1; AU's code was retained for CG-active.

- **Partition of the 44 settings.** 4 privacy (+ CG-composition counted with CG-transform),
  3 identity obfuscation, 2 blocking, 34 without a protection comparison.
- **Finding 2.** Unchanged.
- **Records.** [`ADJUDICATION.md`](human-coding/coder-1/ADJUDICATION.md),
  `human-coding/coder-1/disagreements.csv`, and `evidence/*-adjudicated.csv`.

## Still open

- **Live cohort.** No live timing-matched cohort, and no planner-sampled cover design, has been
  collected yet.
