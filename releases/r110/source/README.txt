R110 - SoK: Agent Communication Side Channels
Feedback Paths and Executed Cover

Compile main.tex and supplement.tex separately with pdfLaTeX and BibTeX:
  pdflatex -interaction=nonstopmode -halt-on-error -no-shell-escape main.tex
  bibtex main
  pdflatex -interaction=nonstopmode -halt-on-error -no-shell-escape main.tex
  pdflatex -interaction=nonstopmode -halt-on-error -no-shell-escape main.tex
Repeat with supplement in place of main. IEEEtran.cls (v1.8b or later) must be
available; current .bbl files are included. Both documents share reference
numbers. Supplement tables and figures are numbered S1, S2, ...

Scope is unchanged: 15 direct studies, 44 settings and 22 mechanism anchors.
Main Section 7.1 applies the evaluation procedure to the executed-cover
cohort (3,600 episodes; 120 paired test fixtures per model). Supplement S11
adds attacks that adapt to timing-matched dispatch; it reuses the same
executions and was frozen before any of its test quantities were computed.
There is no new collection and no additional independent test cohort.
