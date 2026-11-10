# Reproduce the LLM cover extension

The collection uses Windows, Python 3.12, Ollama 0.34.0 and the two model manifests in `verification/weights-before.json`. Tested Python package versions are in `requirements.txt` in the exported bundle. A 16 GB RTX 4090 Laptop GPU served two parallel requests with one model loaded at a time. No hosted API or credential is needed.

## Offline review

From the exported bundle, run:

```text
python experiment/verify_public.py .
python experiment/verify_public_statistics.py .
python experiment/recompute_attackers.py .
```

The first command checks every file hash, paired fixtures, state transitions, model request/response receipts, TLS-length-derived feature rows and confusion matrices. The second recomputes all conditional intervals, cost summaries, paired exact tests and the three separate Holm families. The third refits the fixed LR/RF suite from the released training features, repeats validation selection, and compares every frozen/adapted held-out prediction. These commands do not collect traffic or query a model. The dataset includes the generated synthetic messages and symbolic business states needed for these checks. It excludes model weights, credentials, packet payloads and unrelated transcripts.

## Repeat collection

Use a fresh workspace so the original observations cannot be overwritten. Copy `experiment/`, `inputs/`, `requirements.txt`, and `verification/weights-before.json` into it. Install the pinned dependencies, obtain the exact model identities, and run:

```text
python experiment/check_runtime.py
```

Start a dedicated local Ollama server on `127.0.0.1:11502`, with `OLLAMA_NUM_PARALLEL=2`, `OLLAMA_MAX_LOADED_MODELS=1` and `OLLAMA_FLASH_ATTENTION=1`. Leave an existing service on that port alone. The collector opens only the experiment's loopback MCP ports 40120–40126 and backend ports 40220–40226. Then run:

```text
python experiment/collect.py formal-v1
python experiment/verify_collection.py formal-v1
python experiment/verify_weights_after.py
python experiment/analyze.py
python experiment/verify_analysis.py
python experiment/path_audit.py
```

The protocol contains 3,600 episodes: two models, six arms and 300 fixtures per cell (120 training, 60 validation, 120 test). Both models share fixtures; each arm starts from a fresh business state. Readiness results are not part of these denominators. This is fixture holdout within the synthetic workload, not unseen-template or deployment transfer.

The collector refuses an existing run directory or lock. If a request lacks a terminal, retain its directory and inspect it before continuing; deleting the lock and rerunning would risk duplicating an unknown request. A fresh replication is not an authorized way to replace an unresolved episode from an interrupted collection.

## Interpret the comparison

The primary observer receives known episode and tool-call windows, destinations and bidirectional TLS byte counts. It does not receive labels, operation names, business state, plaintext, the model link or physical timing. The visibility control executes on the same cloned state as the hidden isolated arm and forwards explicitly marked background results. The model remains responsible for its business choice and completion.

The privacy metric is attained six-class balanced accuracy for the requested action, not an information-theoretic upper bound or a score against only successful executions. Select LR/RF on validation only; inspect both individual attacks and the frozen/position baselines in the released tables. Conditional intervals resample test fixtures within class while retaining the fitted attacks. Keep the two utility endpoints distinct: completing the requested action and target-state postcondition, and exact preservation of the whole reference business state. The protocol states the timing and connection-initialization boundaries used for cost accounting.

The original PR reference replay remains a separate study. It uses MemoryBIO TLS, a reference planner, different train/test accounting and HTTP request paths. Its fixed-position and k=1–4 sweeps are not LLM results from this extension.

## Compile the result report

From the exported bundle root, run `pdflatex -halt-on-error latex/m3-llm-report.tex` twice. The other files in `latex/` provide the insertion-ready result paragraph and all-condition tables. This report accompanies the experiment; it is separate from the unchanged R101 main manuscript and supplement.
