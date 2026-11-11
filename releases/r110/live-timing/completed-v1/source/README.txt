Agent communication side-channel SoK: live timing edition.

Compile with pdfLaTeX. Choose main.tex for the main manuscript and
supplement.tex for the supplementary material. Keep all folders intact.

For a command-line build, run for each NAME (main or supplement):
  pdflatex NAME.tex
  bibtex NAME
  pdflatex NAME.tex
  pdflatex NAME.tex

Overleaf: upload this ZIP as a new project; set the Main document to main.tex
or supplement.tex in project settings and select pdfLaTeX. Both share the
provided bibliography. An included .bbl permits reading without a BibTeX run,
but a clean build should run BibTeX after changing citations.

This ZIP builds the papers. The separate payload-free review package contains
the experimental code/data and offline reproduction instructions. No experiment
or model call is needed to compile the manuscripts. The included placeins.sty
retains its original license notice.
