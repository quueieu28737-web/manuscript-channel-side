# R111: Agent communication side-channel SoK

**Executed Cover and Joint Privacy-State Evaluation**

- [Main PDF](main.pdf): 14 pages; references begin on page 12.
- [Supplement](supplement.pdf): 38 pages.
- [Compilable LaTeX ZIP](latex-source.zip) and [source entry point](source/main.tex).
- [All 44 settings](evidence/field-map/evidence-matrix.csv) and [main-text display matrix](evidence/field-map/main-matrix-display.csv).
- [Record-only aggregate analysis and reproducibility scope](analysis/README.md).
- [Public release manifest](release-manifest.json).

The Agent SoK keeps 15 direct sources and 22 selected communication-mechanism anchors. Its main contribution is a joint evaluation of residual inference, original-task completion, business state and resource use under the same cover intervention. The full 44-setting matrix and defense taxonomy are in the main paper. Feedback observations are a scope synthesis; the earlier forwarding pilot is not presented as a verified causal effect. Adverse business writes remain a stress control, not an estimate of production harms or a reproduction of WRA's decoys.

The timing case retains the actual five-policy, two-fixed-weight-model TLS-record study. Validation-selected attacks are reported alongside the strongest tested attacks. The record-only extension removes supplied call windows and retains task association. Its primary tests and later exploratory eventizer remain distinct. In immediate cover, the largest tested record-only counts are 91/120 and 97/120; shadow maxima across tested representations are 73/120 and 69/120. The finite suite is not an upper bound on all inference.

## Build and verification

Upload the LaTeX ZIP to Overleaf and choose `main.tex` or `supplement.tex`; use pdfLaTeX and BibTeX. The clean 78-file source archive was independently extracted and compiled. Both documents have identical page text, uncompressed page content streams and bibliography relative to the delivered PDFs. All 52 rendered pages were visually inspected. Verification receipts describe their precise scope; they do not certify venue acceptance.

## Publication boundary

Only papers, LaTeX, existing source extraction, analysis code and grouped statistics are included. Individual experimental metadata, call/record timestamps, labels/predictions by episode, raw captures, credentials, model weights and the complete local review package remain local by the owner's instruction. Full empirical refitting therefore requires the withheld local package. No new model requests, analyst study or literature expansion occurred for this revision.

The unchanged R110 LaTeX source archive is under `source/archive/` for the historical receipt-timing analyses moved out of the current supplement. The separate live-study public implementation and grouped results remain at [the R110 experiment branch](https://github.com/quueieu28737-web/manuscript-channel-side/tree/ae61acb6b6ca5b32ffd113c7129cf017efe9ffef/releases/r110/live-timing/completed-v1). Earlier versioned releases are preserved.
