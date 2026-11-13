# R117 P0 reviewed execution protocol, version 2

Status before execution: exploratory reanalysis of previously inspected R110 data. This is not preregistration, a new cohort or an independent replication. User authorization on 12 November 2026 permits review followed by implementation when reasonable. The selected scope is P0-T, P0-B, P0-A and P0-C. New W6/P1 collection is outside this execution queue and requires the P0 findings and a complete collection protocol first.

Pre-execution amendment: a local v1 freeze was written but never published or scored. Final baseline inspection found that P0-C omitted the existing raw-record classifiers, which won some original cells. Version 2 retains their four LR/RF size/time candidates as baselines and checks exact identity with the original whitelisted observation file. The v1 code/freeze is preserved, and the original private input seal is reused byte-for-byte. No new diagnostic result informed this amendment.

## Inputs and preservation

- Original R110 formal-none-v1 and formal-cover-v1: 3,000 episodes, fixed Qwen3:8B/Llama3.1:8B, 120/60/120 fixtures per cell. Original bytes and predictions are never overwritten.
- Freeze all reviewed scripts, this protocol, imported analyze.py/record-only modules, library versions and saved input digests before any new diagnostic scoring. Bind all episode/connection/wire JSON files in a LOCAL-ONLY manifest. Publish only the code/plan/freeze on a new codex branch and independently read it back before scoring.
- Outputs are in a new local run-v2 directory. Existing start markers or outputs forbid silent reruns. Failures remain failures of execution or reproduction, not scientific negatives. No model/API calls, capture, data resampling or replacement are part of P0.
- CPU: the existing Python 3.12 runtime, numpy 2.3.3, scipy 1.18.1, sklearn 1.9.1; BLAS and RF use two threads. Run modules sequentially, retaining logs and timing. Inspect rather than repeat on any failure.
- Individual observations, timestamps, fixture identifiers, predictions and private manifests remain LOCAL ONLY. No automatic publication of results, even of the grouped subset.

## Review corrections made before scores

1. Full reproduction is a hard gate before either ablation. It checks every candidate's published test count, saved individual prediction, validation score and selected attacker. Failure saves the Full diagnostics and stops; it does not merely warn after reading ablations.
2. No-time retains the Full candidate suite, including the nominal gap detector, because that detector also uses destinations and a first-call flag. All direct time values are removed. Constant-input pure-gap behavior remains a candidate and is reported as degenerate if relevant. Dropping methods would confound representation with suite membership.
3. No-position is an explicit-position representation/suite ablation: ordered byte slots, direct position/previous-destination/is-last encodings and position-only rules are removed; timing relations and counts remain. It is not an order-free observer or a pure causal intervention on execution order.
4. P0-C uses TRAIN and VALIDATION role annotations for detector fitting and F1/precision threshold choice, as the call-window attack does. Validation task accuracy chooses the final attack. No TEST call truth enters fitting, thresholds, segmentation or selection. All task predictions are saved and sealed before TEST role/boundary audit.
5. Event-role F1 and call-boundary IoU F1 are different endpoints. Report mixed, pure-cover, pure-real and unmatched events. A mixed event marked cover can contain honest data. P0-C removes at most two EVENTS from the top ten candidates, whereas the original decoder removes calls; lower scores cannot identify a pure boundary-access effect.
6. Check the whole frozen code/dependency set at runtime, not only the current script. Keep individual prediction vectors for separate arithmetic verification.

## Questions, tests and interpretation

P0-T: classify the last actual honest business operation, not necessarily the requested/correct operation. Later means later start time, not completion. Retain episodes without business operations. Report association between terminal coverage and saved attack success; Fisher values are descriptive, not causal tests or proof that a schedule must cover a particular slot.

P0-B: compare the fixed chain selector with the TRAIN-majority start-order baseline using exact paired McNemar, Holm across two models. Report exact partition/real-chain recovery by start order. Give exact same-label/different-label task counts for every existing attacker. For the selected adaptive attacker, compare real-label and shadow-label hits under a conditional exchangeability null, Holm across two models. This is prediction asymmetry: unequal label difficulty, priors, fixture/cache histories and start order can contribute. It is not by itself a causal role test. Non-rejection proves neither exchangeability nor equivalence, and no outcome certifies a traffic privacy bound.

P0-A: refit the frozen attack family under Full, No-time and No-position. Family A: history arms x two models x {Full adaptive minus No-time adaptive, No-time adaptive minus Full selected size}, eight exact paired tests with Holm. Family B: Full adaptive minus No-position adaptive, four tests with Holm. Each policy/representation uses its own validation selection; report every candidate and the complete selected contrasts. Results condition on these fitted attacks and reused fixtures. An ablation loss is evidence about this representation/suite; non-significance does not show a feature is useless or justify deleting a limitation.

P0-C: five original idle gaps and the fixed protocol eventizer; same LR/RF definitions, fixed top-ten/two-removal decoder, validation selection. Baseline selection also includes all four original raw-record candidates, so the new attacks do not compete only against a weakened segmented baseline. The extracted observation file must have the original frozen digest before fitting. Compare selected strong and selected refitted baseline in eight cover cells, exact McNemar with Holm. The overall validation-selected candidate may also be a baseline; report it and descriptive test maxima alongside the planned strong-family contrast. TEST truth is used only in sealed-prediction audits. Episode association remains supplied. Near call-window counts show a particular pipeline can recover recognition without supplied calls; lower counts do not establish protection or general localization difficulty.

No result triggers test-driven changes to features, thresholds or multiplicity families. Interpret effect sizes and counts alongside tests. Any necessary engineering repair creates a new version/output directory and discloses previously observed results. P0 does not repair the original no-cover collection-phase confounding, establish online-shadow superiority, measure a noncooperating provider or observe M+T.

## Stop and completion

Stop on input drift, missing episodes, changed dependencies/runtime, failed Full reproduction, invalid dimensions, missing predictions or nonzero script exit. Preserve logs and actual outputs before investigation. A complete P0 campaign requires all four modules plus separate saved-vector/statistical verification and unchanged input seals. A negative or inconclusive scientific result can complete the campaign. Do not proceed automatically to new collection, paper rewriting, branch merging or data publication.
