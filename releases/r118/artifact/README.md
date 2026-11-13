# R118: feature ablations and record-context decoding

This release integrates an exploratory reanalysis of the existing 3,000-episode live TLS study. It adds no cohort, model request or capture. Source manuscript R117 and all earlier numerical results are preserved in their versioned releases.

The two main results are:

- Full-minus-No-time recognition decreases pass Holm correction in three of four history cells. The timing family contains eight contrasts, not four. Qwen sequential does not reject (`p = .0931`). None of the four explicit-position contrasts rejects in its separate family.
- Validation-selected context/joint attacks beat validation-selected refitted record-only baselines in five of eight cells after Holm correction. Llama immediate and both shadow contrasts do not reject. Overall validation selection retains the baseline at 69/120 for both shadows.

## Inspect and check

`p0/` contains candidate-level validation/test counts, every selected paired contrast, event audits and terminal/role summaries. These are aggregates over the fixed fixture population, not individual observations. Each held-out attack cell has 120 fixtures. The arithmetic checker needs only Python's standard library:

```sh
python verify_aggregates.py
```

To regenerate the seven added tables and the record-only columns of the worksheet, extract the LaTeX source ZIP into `source/`, alongside this artifact directory, then run:

```sh
python generate_tables.py --source ../source
```

The unchanged collection and original attack results are under the versioned R116 artifact. The earlier 52-candidate record-only suite includes 28 baseline and 24 GMM-removal candidates. The new 76-candidate extension retains all 28 baselines and adds 24 context-removal and 24 joint-decoding candidates. The legacy GMM results remain separate; 76 is not the size of their union. In these eight cells the displayed new maxima also exceed or equal the earlier maxima.

## Method and observation conditions

The feature ablations reproduce all sixty original controller candidate records before evaluating the changed representations. No-time keeps the candidate family, destinations, sequence and bytes; No-position is an explicit-position representation/suite ablation and still contains temporal order. The new results are exploratory because the original test results had already been inspected.

The record-context attacks receive associated whole-episode encrypted connections, relative record times, destination classes, directions and ciphertext lengths. TRAIN and validation call-role annotations support fitting and threshold selection. TEST call truth enters only audits after the task prediction file is saved and sealed. Up to two inferred events are removed; this differs from removing two supplied calls. The record-context baseline retains raw-record LR/RF candidates as well as segmented candidates. All selections use validation data. Test maxima are descriptive finite-suite maxima, not privacy bounds.

Terminal stratification is observational. First-role prediction, exact chain recovery and six-class task recognition are distinct. The first-role tests compare with the TRAIN-majority start-order baseline, which scores 53/120 on this realized test split. Conditional real-versus-shadow label tests additionally rely on exchangeability; they do not establish causal role leakage or role equivalence.

## Code identity and distribution

`experiment/` preserves the reviewed analysis source bytes frozen before new scoring in commit `994e8e3b6dade9a544f4a2793128d01d0ce133dd`. `dependencies/` preserves the four imported analysis sources. `portable-code-identity.json` records their exact hashes, numerical-library versions and the aggregate file identities. It is a portable derivative, not the original local freeze receipt. Original machine-path receipts and individual input manifests are withheld. Preserved historical protocol text does not authorize uploading a newly generated local receipt or data file.

The original local verification checked saved vectors, selections, exact paired arithmetic and unchanged input files. The public checker verifies only the released identities and aggregate arithmetic. Full refitting, feature reconstruction, independent role/boundary checks and per-fixture state replay require withheld inputs.

No per-episode fixtures, record streams, individual timestamps, prediction vectors, message bodies, packet captures, keys, weights, private manifests or logs are included. The public aggregates do not turn the local 3,000 episodes into a new independent dataset. New interleaved controls and matched controller replay remain uncollected plans.
