# R112: Agent communication side-channel SoK

**Executed Cover and Joint Privacy-State Evaluation** — revision answering review points W2–W7 on R111.

- [Main PDF](main.pdf): 15 pages; body pages 1–12, references begin on page 13.
- [Supplement](supplement.pdf): 38 pages.
- [Compilable LaTeX ZIP](latex-source.zip) and [source entry point](source/main.tex).
- [Revision notes (修订说明)](修订说明.md): what changed for each review point and what still needs data or new runs.
- [Pair-ambiguity floor script](experiment/shadow_floor.py) and [its output](analysis/shadow-floor.json).
- [All 44 settings](evidence/field-map/evidence-matrix.csv) and the [record-only aggregate analysis](analysis/README.md), unchanged from R111.

## What changed from R111

- Threat model: new Section 3.2 and Table 2 state when cover must execute (no defender-controlled terminator after the observer); new Section 3.3 and Table 3 give a four-axis cover taxonomy (termination/state, feedback, dispatcher).
- Shadow result: the strongest tested attack (70/120 and 64/120) is compared with the 7/12 pair-ambiguity floor (realized 70.5/120 on the test split) instead of the 1/6 uniform reference. Table 10 gives the floor for k shadows and for distinct-label sampling. Family E is labelled degenerate.
- Abstract and introduction report validation-selected results, state the negative record-only primary result, and frame immediate cover as a calibration baseline.
- Section 7 opens with a study map (Table 8), one statistical-conventions paragraph and a dispatcher timeline (Figure 3). Forwarding-pilot material is removed from the main text.
- Availability now describes a complete synthetic-data artifact behind an anonymized link placeholder (`\artifacturl` in `main.tex` and `supplement.tex`).
- Fixed a wrong cross-reference: the adverse-write state control is Supplement S1, not S10.

No new model requests, captures or literature retrieval were made. All experimental numbers are unchanged from R111/R110 aggregates.

## Build

Upload the ZIP to Overleaf, choose `main.tex` or `supplement.tex`, and use pdfLaTeX and BibTeX. Locally: pdfLaTeX, BibTeX, pdfLaTeX twice. Both documents built with zero errors, zero undefined references and zero overfull boxes; all main pages were visually checked.
