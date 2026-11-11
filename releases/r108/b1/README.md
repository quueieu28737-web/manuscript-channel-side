# B1: retrospective timing reanalysis

Start with RESULTS.md and result-summary.json. Original byte-view primary
results and all M3 business outcomes are unchanged. Ten direct timing-feature
comparisons do not reject; ten planned secondary cover-removal comparisons
survive Holm correction. diagnostic/ is a separately labelled post-scoring
input ablation, not a replacement primary or a new confirmation cohort.

The observer has supplied call/episode windows, destination and client-receipt
times, plus cover-labelled training. These are not measured packet-time or WAN
attacks. All 3,600 original episodes are reused; paired test fixtures remain 120.
A and B2 are revised plans only. No new collection is included in R108.

## Inputs and replay

Original M3 synthetic metadata and analysis are available at the immutable
commit https://github.com/quueieu28737-web/manuscript-channel-side/tree/21f136e75161651f0ab2c73e6d7d1fb2a32a067f/review-r102/llm-extension
The eight exact input SHA-256 values are in freeze.json. Saved selections,
readable predictions and every paired comparison are provided here. The NPZ
test-feature array remains local: automatic publication review did not approve
its public upload. It has not been transformed or uploaded by another route.
Its original identity remains recorded in the unchanged analysis receipts.
The offline source scripts regenerate it during a fresh refit. Locally trained
joblib objects are also excluded; the verifiers need refitting.

For an offline refit, use a NEW workspace, not this immutable result directory:
1. Put the original llm-extension/ contents in
   work/revision-preview/r102-llm-executed-cover/review-export/.
2. Put b1.py, analysis-plan.json, verify_b1.py, detector_ablation.py and
   verify_diagnostic.py in work/revision-preview/r107-m3-followup/.
   Do not copy saved freeze/results/validation/diagnostic into that fresh run.
3. With the recorded Python 3.12 / NumPy 2.3.3 / SciPy 1.18.1 /
   scikit-learn 1.9.1 environment, run from that new followup directory:
      python b1.py freeze
      python b1.py prepare
      python b1.py evaluate
      python verify_b1.py
      python detector_ablation.py
      python verify_diagnostic.py
These commands fit offline data and make no LLM/API calls. Existing output is
protected against overwrite. A replay has new timestamps and is not the old
prospective freeze. Compare numeric outcomes with the saved release, rather
than expecting timestamp-bearing receipts to have identical hashes.

The source collection's private captures, transcripts, credentials and model
weights are excluded. plan_power.py and EXPERIMENT-PLANS.md concern later
collection design; they do not establish completed equivalence or protection.
