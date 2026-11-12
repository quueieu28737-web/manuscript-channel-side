# Record-only aggregate analysis

The analysis reuses all 3,000 existing main episodes: 120 training, 60 validation and 120 test fixtures per model/condition. It supplies episode-associated connection bundles, removes true call endpoints, and observes only relative TLS-record completion times, destination, direction and ciphertext record length. It does not evaluate unknown-task discovery in a continuous stream.

The first fixed 44-candidate suite and its two immediate-cover paired tests are preserved. Qwen removal changes 80 to 69/120 (Holm p=.02545); Llama changes 90 to 86 (p=.5413). The subsequent public-protocol eventizer is explicitly exploratory after the first Qwen test scores were seen. It changes Qwen 68 to 91 and Llama 90 to 87; no new superiority test family is declared. Maxima across 52 candidates are descriptive, not substitutions for primary tests or universal attacker bounds.

Files here contain cell-level counts and statistics only. `boundary-diagnostic.csv` is a separate post-prediction aggregate audit using private call truth; that truth is never an attacker input.

## Reproduction scope

`../experiment/` preserves the exact plans, frozen hashes and implementation. Complete fitting requires the local-only `inputs/record-only.jsonl` and the original R110 records; they are deliberately not part of this public release. The extractor expects a sibling R110 local study directory. `../verification/verify_no_call.py` additionally needs saved individual predictions and original call truth for its complete audit. Public aggregates allow arithmetic/source inspection, not independent full-data replication. Source hashes identify withheld inputs without revealing their contents.

The manuscript/source package builds without experimental data. As of R112 this directory still contains aggregates only; the per-episode records, predictions, captures and synthetic-deployment keys described in the paper's Availability paragraph are to be released at the anonymized artifact link before submission.
