# R113: Decoys That Do Work

**Evaluating Executed Cover for LLM Agent Communication Privacy** — research-track version of the former SoK, prepared for IEEE S&P 2027.

- [Main PDF](main.pdf): 15 pages; body pages 1–8, references from page 9, Appendices A–B after the references.
- [Supplement](supplement.pdf): 38 pages.
- [Compilable LaTeX ZIP](latex-source.zip) and [source entry point](source/main.tex).
- [Revision notes (修订说明)](修订说明.md): structure mapping, new analyses, and items required before submission.
- [Pair-ambiguity floor script](experiment/shadow_floor.py) and [output](analysis/shadow-floor.json).
- [44-setting evidence matrix](evidence/field-map/evidence-matrix.csv) and [record-only aggregates](analysis/README.md).

## What changed from R112

- Repositioned from SoK to a research paper: the literature map moves to Appendix A and the gap becomes motivation (Section 2.4).
- New structure: threat model, design space, methodology (including the pair-ambiguity floor), setup, results, discussion and related work.
- New with existing data: the protocol's decision step under illustrative tolerances (Table 11) and an inference–cost frontier (Figure 3); achieved-timing table moved into the main text.
- Anonymity: all "the author" wording changed to "we".

No new runs; numbers unchanged. Before submission: release the artifact and set `\artifacturl`, and resolve the hosted-retest terms (see the revision notes).

## Build

pdfLaTeX, BibTeX, pdfLaTeX twice for `main.tex` and `supplement.tex` (Overleaf works). Both build with zero errors, undefined references or overfull boxes.
