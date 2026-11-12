# R114: Decoys That Do Work

**Evaluating Executed Cover for LLM Agent Communication Privacy** — research-track version of the former SoK, prepared for IEEE S&P 2027.

- [Main PDF](main.pdf): 13 pages; body pages 1–9, references from page 10, Appendices A–B after the references.
- [Supplement](supplement.pdf): 41 pages.
- [Compilable LaTeX ZIP](latex-source.zip) and [source entry point](source/main.tex).
- [Revision notes (修订说明)](修订说明.md): structure mapping, new analyses, and items required before submission.
- [Pair-ambiguity floor script](experiment/shadow_floor.py) and [output](analysis/shadow-floor.json).
- [44-setting evidence matrix](evidence/field-map/evidence-matrix.csv) and [record-only aggregates](analysis/README.md).

## What changed from R113

- M1: the cross-observer claim is dropped. The record-only suite lacks the adaptive decoders, so record-only decisions on history arms are marked not comparable; the protocol now requires the same suite across observers.
- M2: a related-work paragraph on decoy-query obfuscation (TrackMeNot, GooPIR, Peddinti & Saxena, OB-PWS, Gervais et al.); P*(k) is framed as the plausible-deniability floor carried over from that line.
- M5: three-valued, interval-based decisions with a latency column. Controller policies fail robustly; the shadow is undecided at 120 fixtures.
- Shorter abstract; Figure 3 renamed; the full 44-setting matrix moves to Supplement S11.

No new runs. See [修订说明](修订说明.md).

## Build

pdfLaTeX, BibTeX, pdfLaTeX twice for `main.tex` and `supplement.tex` (Overleaf works). Both build with zero errors, undefined references or overfull boxes.
