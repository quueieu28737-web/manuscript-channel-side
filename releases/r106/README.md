# R106: Agent communication side-channel SoK (acceptance-focused revision)

- [Main PDF](main.pdf)
- [Supplement PDF](supplement.pdf)
- [Compilable LaTeX ZIP](latex-source.zip)
- [LaTeX source](source/)

R106 revises the R105 main text in response to an S&P-style review. It adds no
new collection, model fit, hypothesis test or literature search. Every number in
the revised text already appears in the R105 main paper or supplement.

## What changed and why

| Review concern | Revision |
|---|---|
| Findings read as restatements of threat-modeling principles | Abstract and introduction now state *which WF evaluation assumptions fail* (single-trace unit of protection; side-effect-free cover) and give three numbered findings. |
| Executed-cover experiment looked tautological | Section 7.1 now reports the contrast that is not obvious: four cover semantics leave Qwen recognition at 61--62/120, while state integrity ranges from 116/120 to 7/120. The last-destination rule (77/120) shows that schedule coverage limits privacy. Resulting design rule: terminate cover as early as the observer model allows. The live-write arm is still described as an adverse control. |
| Inconclusive forwarding pilot took up main-text space | Section 7.2 is now three measurement lessons: single-step minimization leaves the complete-execution view above chance; 19.5--22.5x joint shaping gives no detectable gain under concurrency; event metrics are sensitive to IoU. Non-rejection and lack of power are stated up front. |
| Low coding reliability | Section 2.2 states that Findings 1--2 depend only on full-agreement fields, directly quoted numbers and the four locator-listed privacy decisions. |
| Thin defense systematization | Section 6.2 links BuFLO/Tamaraw-style constant-rate shaping to the measured Agent shaping cost. Added Cai et al. (CCS 2014). |
| Readability / caveat density | Caveats are consolidated in Section 10; there is a contributions list, Section 9.2 "Lessons for defense designers and evaluators", and a shorter conclusion. |
| "Why an SoK now" | The introduction explains the timing (protocol convergence, preprint-stage defenses, and the WF precedent). |

The main body ends on page 13 and references begin on page 14 (15 pages in total).
The supplement is unchanged except for one added bibliography entry (shared numbering).

Build: compile `source/main.tex` and `source/supplement.tex` separately with
pdfLaTeX + BibTeX (IEEEtran class required), or upload `latex-source.zip` to Overleaf.
