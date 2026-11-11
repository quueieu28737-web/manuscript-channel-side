# R103: completed M3 integrated into the Agent side-channel SoK

- [Main PDF](main.pdf)
- [Supplement PDF](supplement.pdf)
- [Compilable LaTeX ZIP](latex-source.zip)
- [Current evidence and coding manual](evidence/README.md)
- [Complete M3 experiment artifact](../../review-r102/llm-extension/README.md)

Main Section 7.1 and Supplement S8 distinguish task completion from full
business-state integrity. Under the deliberately adverse live-write policy,
95/120 Qwen and 73/120 Llama test executions complete the requested action but
leave incorrect global state. Both integrity losses survive the original Holm
correction; completion loss survives only in Qwen. All 36 paired contrasts and
all attack controls are retained. Visible/hidden differences and the separate
forwarding pilot remain inconclusive. No new experiments were run for this
manuscript integration.

Supplement S4.1 reports the author/AI coding-manual pilot as a dependent,
non-blind sensitivity analysis, not independent human reliability. Of fifteen
outcome disagreements, thirteen are changed and two retained based on cited
source passages. The clarified manual distinguishes an explicit source-defined
success or probe outcome from partial evidence, missing evidence and absence
of a new execution population. Original codes and the exposure sensitivity
are preserved. The revised 15/42 is descriptive author coding.

The fifteen-source, forty-four-setting corpus and six-row transfer matrix are
retained. The original R101 release and the submitted R102 review materials
remain unchanged. This integrated text does not adopt the proposed universal
WF-assumption-failure claims or substitute broad intervention counts for the
four-setting query/workflow privacy denominator.

All 41 PDF pages were visually checked; the 59-file LaTeX ZIP independently
rebuilds to identical page text, pixels and bibliography. Run
`python evidence/verify_evidence.py` and (with NumPy)
`python evidence/coding-pilot/recompute.py` to check the current evidence.
The complete local review ZIP also preserves the earlier review archive;
that large historical package is not duplicated in this Git release.
This commit updates the draft PR branch; it does not merge main.
