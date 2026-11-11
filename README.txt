R108 - SoK: Agent Communication Side Channels
Feedback Paths and Executed Cover

Compile main.tex and supplement.tex separately with pdfLaTeX and BibTeX:
  pdflatex -interaction=nonstopmode -halt-on-error -no-shell-escape main.tex
  bibtex main
  pdflatex -interaction=nonstopmode -halt-on-error -no-shell-escape main.tex
  pdflatex -interaction=nonstopmode -halt-on-error -no-shell-escape main.tex
Repeat with supplement in place of main. On Overleaf upload this ZIP as a
new project, choose pdfLaTeX, and select main.tex or supplement.tex as the
Main document. Current .bbl files are included. Both documents share reference
numbers. No external experiment files or shell-escape commands are needed.

This revision preserves the Agent communication side-channel SoK scope:
15 direct studies, 44 settings and 22 mechanism anchors. Main Section 7.1
and Supplement S9 integrate the completed B1 timing reanalysis of the same
3,600 M3 episodes. There is no new collection and no additional independent
test cohort. Original measurements and business outcomes are preserved.

B1's direct-feature primary comparisons and planned cover-removal secondary
comparisons are reported separately. The input diagnostic was performed after
scoring and is labelled exploratory. Timestamps come from client receipts;
the study does not measure passive packet-time or WAN recovery. Experiments
A and B2 remain future new-cohort designs and are not reported as completed.

The separate review evidence contains frozen protocols, feature arrays,
predictions, statistical checks and input fingerprints. Original synthetic
M3 metadata permit state replay. The evidence also preserves the earlier
forwarding pilot, source extraction and dependent AI coding-manual pilot;
these are not independent human coding or new confirmation studies.

This LaTeX ZIP contains manuscript sources and bibliography only. It excludes
credentials, raw captures, private transcripts, model weights and third-party
full texts. Source versions and passage locators support external checking.
