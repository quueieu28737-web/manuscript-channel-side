# R105: Agent communication side-channel SoK

- [Main PDF](main.pdf)
- [Supplement PDF](supplement.pdf)
- [Compilable LaTeX ZIP](latex-source.zip)
- [LaTeX source](source/)
- [44-setting evidence matrix](evidence/field-map/evidence-matrix.csv)
- [Current extraction, coding manual and arithmetic checker](evidence/README.md)
- [Later conditional forwarding sample-size calculation](planning/README.txt)
- [Document checks](document-validation.json)

The manuscript remains a SoK of Agent communication side channels: 15 direct
sources, 44 settings and 22 mechanism anchors. R105 foregrounds observation
permissions, protection placement and matched execution outcomes. It retains
all original results, including nonsignificant forwarding comparisons and the
deliberately adverse nature of live writes. The author/AI coding exercise is
not independent human reliability. The source-inspection summary covers all
15 sources; contextual related work and the WRA query-decoy locator are updated.

The main PDF has 15 pages, with references beginning on page 13; the supplement
has 26 pages. The unchanged 59-file source ZIP was independently recompiled and
all 41 pages were visually checked. Compile source/main.tex and
source/supplement.tex separately, or upload latex-source.zip to Overleaf.

The evidence directory is the unchanged R103 extraction/adjudication subset;
its own manifest, historic label and checker remain valid. From this directory:
python evidence/verify_evidence.py

The previously published complete M3 LLM artifact remains available at
[the immutable experiment commit](https://github.com/quueieu28737-web/manuscript-channel-side/tree/21f136e75161651f0ab2c73e6d7d1fb2a32a067f/review-r102/llm-extension).
The later planning calculation includes the exact payload-free saved prediction
input and frozen analysis plan needed to reproduce its arithmetic. It does not
modify the old hypotheses or establish prospective power.

This public release contains the PDFs, clean source closure, selected evidence
and the planning calculation. The 154 MB local historical review archive, private
captures, credentials, transcripts, model weights and third-party full texts
are outside this publication scope. The repository is public and is not an
anonymous-review service. Existing remote files and earlier releases are kept.
