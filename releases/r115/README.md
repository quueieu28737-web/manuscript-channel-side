# R115: Decoys That Do Work

**Evaluating Executed Cover for LLM Agent Communication Privacy** — research-track version of the former SoK, prepared for IEEE S&P 2027.

- [Main PDF](main.pdf): 14 pages; body pages 1–10, references from page 10, Appendices A–B after the references.
- [Supplement](supplement.pdf): 41 pages.
- [Compilable LaTeX ZIP](latex-source.zip) and [source entry point](source/main.tex).
- [Revision notes (修订说明)](修订说明.md): structure mapping, new analyses, and items required before submission.
- [Pair-ambiguity floor script](experiment/shadow_floor.py) and [output](analysis/shadow-floor.json).
- [44-setting evidence matrix](evidence/field-map/evidence-matrix.csv) and [record-only aggregates](analysis/README.md).

## What changed from R114

- The dispatcher result (controller decoys lack the model wait) now leads the abstract, introduction and conclusion.
- Necessity narrowed with TLS 1.3 / HTTP/2 padding and PING analysis: cover must reach the application only when the privacy target includes exchanges, response sizes or service latency; reaching it does not require a business write.
- Shadow: "consistent with" the 7/12 reference rather than "reaching the floor"; its gain is not attributed to planner generation (call count, composition and tokens change together).
- New service-contract table: the live study models a cooperating provider (response padding, server-side holds, isolated clones); the non-cooperating case is unmeasured.
- Availability lists exactly what is public and what stays local.
- Fixed the §7.5 reasoning error about sample size.

No new runs. See [修订说明](修订说明.md).

## Build

pdfLaTeX, BibTeX, pdfLaTeX twice for `main.tex` and `supplement.tex` (Overleaf works). Both build with zero errors, undefined references or overfull boxes.
