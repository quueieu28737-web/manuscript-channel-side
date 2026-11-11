# R108: Agent communication side-channel SoK

- [Main PDF](main.pdf) | [Supplement PDF](supplement.pdf)
- [Compilable LaTeX ZIP](latex-source.zip) | [Source](source/)
- [B1 timing results, inputs and replay instructions](b1/README.md)
- [44-setting evidence matrix](evidence/field-map/evidence-matrix.csv)
- [Extraction manual and arithmetic verification](evidence/README.md)
- [New-byte document checks](checks/new-byte-release-review.json)
- [Scoped claim/evidence review](SCIENTIFIC-REVIEW.md)

The SoK retains 15 direct studies, 44 settings and 22 mechanism anchors. R108
integrates B1 into Main Section 7.1 and Supplement S9 while preserving all
original M3 business outcomes and nonsignificant forwarding primary tests.

Timing-informed detection/removal raises task recognition from 61–63/120 to
111–114/120 for Qwen and from 72–82/120 to 107–115/120 for Llama. All ten
planned secondary contrasts survive correction. Simply concatenating timing
features shows no improvement; all ten primary tests remain nonsignificant.
The post-scoring input diagnostic remains explicitly exploratory. Timestamps
are client receipts, with supplied windows and labelled detector training;
this is neither measured passive packet timing nor a new confirmation cohort.

Main: 15 pages, references begin on page 13. Supplement: 30 pages. All 45 pages
were visually inspected. The 66-file source ZIP was independently rebuilt
with identical page text, pixels and bibliography. Compile main.tex and
supplement.tex separately, or upload the ZIP to Overleaf using pdfLaTeX.

B1 is complete. A and B2 remain uncollected future designs. The manuscript's
adverse-write controls do not estimate production or WRA harms. The dependent
author/AI coding pilot is not independent human reliability.

The evidence/ subset retains its original R103 manifest and labels. Earlier
releases and the complete M3 artifact remain available at immutable commits.
This release excludes private captures, credentials, transcripts, model weights,
joblib objects, the B1 NPZ feature array and third-party full texts. The NPZ
was not approved for public upload and remains local; offline scripts recreate
it from the original already-public M3 metadata. This is a public repository, not an
anonymous-review host. Source-study experiments have not been independently
rerun by this publication step.

Run python verify_release.py for file identity, source-ZIP closure, B1 count
and contrast-family consistency. Run python evidence/verify_evidence.py for
the existing extraction subset. Neither command independently validates the
source interpretations or reproduces new LLM collection.
