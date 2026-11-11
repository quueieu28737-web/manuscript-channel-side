# R103 evidence and coding-manual pilot

`field-map/evidence-matrix.csv` preserves 44 settings from 15 direct sources.
`field-map/target-evidence.csv` is the current author outcome extraction.
`coding-pilot/CODEBOOK.md` defines applicability, source-defined success and
probe outcomes. The original C1/C2/C3 data are immutable under `original/`.
Fifteen disagreements were source-adjudicated: thirteen statuses changed;
CG-active and CG-transform were retained contrary to the two AI votes.
The other twenty-nine rows retain their prior extraction. The resulting 15/42
is descriptive author coding, not an independent validation or prevalence bound.

Run `python verify_evidence.py` here for manifest and synthesis arithmetic.
Run `python coding-pilot/recompute.py` here for the original agreement,
exposed-row sensitivity and adjudication checks (requires NumPy).
Neither command requests a model, redoes an experiment or retrieves sources.
The original failure counts have different applicable denominators:
19/42, 18/43, 16/43. Original outcomes are 13/38, 7/38, 15/43.
No common-denominator interval or human-coder reliability is claimed.

The four-setting query/workflow privacy denominator is unchanged: adaptation
is located in two settings, original-task utility in one, and both in none.
Broader intervention counts combine different objectives and are not substituted
for this denominator. Counts concern located evidence, not source quality.
