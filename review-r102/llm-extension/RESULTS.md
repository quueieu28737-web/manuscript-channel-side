# M3 LLM-planner results

The six-arm experiment is complete: 3,600 formal episodes, including 1,440 held-out executions of 120 paired test fixtures. Qwen3:8B and Llama3.1:8B used fixed weight identities, real LangGraph decisions, and local MCP Streamable HTTP over TLS 1.3/HTTP/2. Each model/arm has 120 training, 60 validation and 120 test fixtures. There are no unresolved formal requests. A separate development-run request remains unknown and was never retried or included in these results.

**The strongest finding is the gap between completing a task and preserving its business state.** Under live-state cover, Qwen completed 102/120 tasks but preserved the exact reference state in only 7/120; Llama completed 76/120 but preserved state in only 3/120. Respectively, 95 and 73 completed tasks had incorrect global state. The state-integrity reductions versus no cover survived the predeclared multiplicity correction for both models. The task-completion reduction survived correction for Qwen, but not for Llama.

**Live writes produced severe state loss while their recognition scores stayed in the range already observed with other cover policies.** The primary attacker scored 62/120 on Qwen live writes and 80/120 on Llama live writes. Proxy discard, read, and isolated execution scored 61–62/120 and 72–82/120 respectively. This is a measured comparison within constructed adverse business operations, not a claim that all cover policies are information-theoretically equivalent or that WRA has this defect.

**Marked visible decoys affected individual paths, with no established average gain or loss in the primary endpoints.** Hidden and visible isolated arms had identical cover responses in all 120 pairs per model. Honest action sequences differed in 16 Qwen and 65 Llama pairs. Visible-minus-hidden recognition, goal and integrity contrasts all had Holm-adjusted p=1. Mean prompt tokens increased from 1668.34 to 1969.49 (18.1%) for Qwen and from 2251.48 to 2675.95 (18.9%) for Llama. Non-visible arms also showed some execution variation; the released path audit retains it.

## All held-out conditions

Every count below has denominator 120. “Selected” is the LR/RF attacker chosen by validation balanced accuracy; it is not the largest test score. Goal requires the requested action and object, prerequisites and target postcondition. State compares the entire final state with the single intended-action reference. The stricter object requirement means state can match even when the goal predicate fails.

| Model | Condition | Selected correct | Goal | State | Goal with state error | Call bytes × | Total TLS bytes × |
|---|---|---:|---:|---:|---:|---:|---:|
| Qwen3:8B | No cover | 118 (LR) | 114 | 116 | 0 | 1.000 | 1.000 |
| Qwen3:8B | Proxy discard | 62 (RF) | 114 | 116 | 0 | 1.338 | 1.147 |
| Qwen3:8B | Read cover | 62 (RF) | 114 | 115 | 0 | 1.341 | 1.148 |
| Qwen3:8B | Isolated, hidden | 61 (RF) | 114 | 115 | 0 | 1.341 | 1.148 |
| Qwen3:8B | Live write | 62 (RF) | 102 | 7 | 95 | 1.343 | 1.149 |
| Qwen3:8B | Isolated, visible | 63 (RF) | 113 | 114 | 1 | 1.346 | 1.149 |
| Llama3.1:8B | No cover | 113 (LR) | 82 | 69 | 13 | 1.000 | 1.000 |
| Llama3.1:8B | Proxy discard | 79 (RF) | 80 | 68 | 13 | 1.288 | 1.136 |
| Llama3.1:8B | Read cover | 72 (RF) | 84 | 71 | 14 | 1.280 | 1.131 |
| Llama3.1:8B | Isolated, hidden | 82 (RF) | 83 | 70 | 13 | 1.282 | 1.132 |
| Llama3.1:8B | Live write | 80 (LR) | 76 | 3 | 73 | 1.292 | 1.138 |
| Llama3.1:8B | Isolated, visible | 81 (RF) | 83 | 73 | 11 | 1.293 | 1.135 |

All 182 planned held-out decoys triggered in every cover cell. Both model families completed all formal requests; Llama had 1/120 step-limit episodes in no-cover, proxy-discard, read and hidden-isolated cells, 2/120 in live-write, and 0/120 in visible-isolated. Qwen had none. All were retained.

## Every attack and position control

The six classes are balanced, so uniform chance is 20/120. The primary LR/RF comparison falls substantially under random cover, but the stronger observed controls must remain visible: the last-destination rule reaches 75–77/120 in Qwen cover arms. Attained scores are lower bounds on what an attacker can achieve with this observation. They are not privacy guarantees.

| Model | Condition | Frozen | LR | RF | Last destination | Penultimate destination |
|---|---|---:|---:|---:|---:|---:|
| Qwen3:8B | No cover | 118 | 118 | 117 | 116 | 14 |
| Qwen3:8B | Proxy discard | 44 | 63 | 62 | 77 | 43 |
| Qwen3:8B | Read cover | 42 | 59 | 62 | 77 | 42 |
| Qwen3:8B | Isolated, hidden | 43 | 62 | 61 | 77 | 42 |
| Qwen3:8B | Live write | 42 | 60 | 62 | 75 | 44 |
| Qwen3:8B | Isolated, visible | 40 | 63 | 63 | 77 | 42 |
| Llama3.1:8B | No cover | 113 | 113 | 110 | 79 | 64 |
| Llama3.1:8B | Proxy discard | 54 | 81 | 79 | 67 | 61 |
| Llama3.1:8B | Read cover | 57 | 78 | 72 | 67 | 62 |
| Llama3.1:8B | Isolated, hidden | 56 | 81 | 82 | 67 | 60 |
| Llama3.1:8B | Live write | 58 | 80 | 75 | 65 | 59 |
| Llama3.1:8B | Isolated, visible | 58 | 79 | 81 | 68 | 64 |

## Prespecified paired comparisons

Each endpoint has its own 12-comparison Holm family. Intervals use 10,000 paired fixture resamples stratified by requested action, conditional on fitted attackers and this workload. These are fixture-level intervals, not estimates of template, deployment or training-selection uncertainty. All ten primary cover-versus-no-cover recognition contrasts pass the prespecified family correction (largest adjusted p=3.08e-8). The visible-versus-hidden contrasts do not establish equivalence.

### goal_success

| Model | Condition − reference | Difference pp | Conditional 95% CI pp | Raw p | Holm p |
|---|---|---:|---|---:|---:|
| Qwen3:8B | Proxy discard − No cover | 0.00 | [0.00, 0.00] | 1.000 | 1.000 |
| Qwen3:8B | Read cover − No cover | 0.00 | [0.00, 0.00] | 1.000 | 1.000 |
| Qwen3:8B | Isolated, hidden − No cover | 0.00 | [0.00, 0.00] | 1.000 | 1.000 |
| Qwen3:8B | Live write − No cover | -10.00 | [-15.00, -5.00] | 0.002 | 0.022 |
| Qwen3:8B | Isolated, visible − No cover | -0.83 | [-4.17, 2.50] | 1.000 | 1.000 |
| Qwen3:8B | Isolated, visible − Isolated, hidden | -0.83 | [-4.17, 2.50] | 1.000 | 1.000 |
| Llama3.1:8B | Proxy discard − No cover | -1.67 | [-5.00, 1.67] | 0.625 | 1.000 |
| Llama3.1:8B | Read cover − No cover | 1.67 | [-2.50, 5.83] | 0.688 | 1.000 |
| Llama3.1:8B | Isolated, hidden − No cover | 0.83 | [0.00, 2.50] | 1.000 | 1.000 |
| Llama3.1:8B | Live write − No cover | -5.00 | [-10.83, 0.83] | 0.210 | 1.000 |
| Llama3.1:8B | Isolated, visible − No cover | 0.83 | [-6.67, 8.33] | 1.000 | 1.000 |
| Llama3.1:8B | Isolated, visible − Isolated, hidden | 0.00 | [-7.50, 7.50] | 1.000 | 1.000 |
### privacy

| Model | Condition − reference | Difference pp | Conditional 95% CI pp | Raw p | Holm p |
|---|---|---:|---|---:|---:|
| Qwen3:8B | Proxy discard − No cover | -46.67 | [-55.83, -37.50] | 2.8e-17 | 3.1e-16 |
| Qwen3:8B | Read cover − No cover | -46.67 | [-55.00, -37.50] | 2.8e-17 | 3.1e-16 |
| Qwen3:8B | Isolated, hidden − No cover | -47.50 | [-56.67, -38.33] | 1.4e-17 | 1.7e-16 |
| Qwen3:8B | Live write − No cover | -46.67 | [-55.83, -37.50] | 2.8e-17 | 3.1e-16 |
| Qwen3:8B | Isolated, visible − No cover | -45.83 | [-55.00, -36.67] | 8e-16 | 6.4e-15 |
| Qwen3:8B | Isolated, visible − Isolated, hidden | 1.67 | [-5.00, 8.33] | 0.815 | 1.000 |
| Llama3.1:8B | Proxy discard − No cover | -28.33 | [-35.83, -20.83] | 1.1e-09 | 5.6e-09 |
| Llama3.1:8B | Read cover − No cover | -34.17 | [-42.50, -25.83] | 9.1e-13 | 6.4e-12 |
| Llama3.1:8B | Isolated, hidden − No cover | -25.83 | [-34.17, -18.33] | 9.3e-10 | 5.6e-09 |
| Llama3.1:8B | Live write − No cover | -27.50 | [-35.83, -19.17] | 1e-08 | 3.1e-08 |
| Llama3.1:8B | Isolated, visible − No cover | -26.67 | [-35.00, -19.17] | 4.1e-09 | 1.6e-08 |
| Llama3.1:8B | Isolated, visible − Isolated, hidden | -0.83 | [-8.33, 6.67] | 1.000 | 1.000 |
### state_integrity

| Model | Condition − reference | Difference pp | Conditional 95% CI pp | Raw p | Holm p |
|---|---|---:|---|---:|---:|
| Qwen3:8B | Proxy discard − No cover | 0.00 | [0.00, 0.00] | 1.000 | 1.000 |
| Qwen3:8B | Read cover − No cover | -0.83 | [-2.50, 0.00] | 1.000 | 1.000 |
| Qwen3:8B | Isolated, hidden − No cover | -0.83 | [-2.50, 0.00] | 1.000 | 1.000 |
| Qwen3:8B | Live write − No cover | -90.83 | [-95.00, -85.83] | 3.1e-33 | 3.7e-32 |
| Qwen3:8B | Isolated, visible − No cover | -1.67 | [-5.83, 1.67] | 0.688 | 1.000 |
| Qwen3:8B | Isolated, visible − Isolated, hidden | -0.83 | [-4.17, 2.50] | 1.000 | 1.000 |
| Llama3.1:8B | Proxy discard − No cover | -0.83 | [-4.17, 2.50] | 1.000 | 1.000 |
| Llama3.1:8B | Read cover − No cover | 1.67 | [-2.50, 6.67] | 0.727 | 1.000 |
| Llama3.1:8B | Isolated, hidden − No cover | 0.83 | [-1.67, 3.33] | 1.000 | 1.000 |
| Llama3.1:8B | Live write − No cover | -55.00 | [-62.50, -47.50] | 2.7e-20 | 3e-19 |
| Llama3.1:8B | Isolated, visible − No cover | 3.33 | [-4.17, 10.83] | 0.523 | 1.000 |
| Llama3.1:8B | Isolated, visible − Isolated, hidden | 2.50 | [-5.00, 10.00] | 0.664 | 1.000 |

## Interpretation for the Agent SoK

The result supports a concrete evaluation distinction: traffic obfuscation, executing the requested action, and preserving business state are separate outcomes. A task-success-only evaluation would conceal most of the collateral effects of the constructed live-write policy. State-isolated cover avoids directly applying decoy writes to the primary fixture, while exposing marked responses is a separate planner-interface choice. The new visibility control supplies a real LLM comparison, but does not show a reliable average effect on recognition or utility at this sample size.

The synthetic adverse writes deliberately consume or modify business state. This measures the consequence under LLM planning; it does not discover a production vulnerability or reproduce WRA's actual mechanism. Llama's baseline is already imperfect (82/120 goals and 69/120 intact states), so its absolute state failures cannot all be attributed to cover.

## Costs, scope and verification

Cover call-byte ratios range from 1.280 to 1.346. Total TLS-byte ratios range from 1.131 to 1.149 because this protocol initializes all seven MCP sessions for each episode. Mean local wall times are 8.14–9.94 seconds per test episode, including setup, journaling and two-worker contention; these are not production latency estimates. All resource summaries, intervals and model token counts are in `analysis/outcomes-costs.csv`.

The observer uses destinations and ciphertext byte counts within supplied call/episode windows. All endpoints share `/mcp`; the reference replay's variable-path read-cover result is not carried over. Physical timing, the model link, WAN behavior, shared-connection localization, unseen templates and real customer workloads are outside this experiment. The original fixed-position and k=1–4 reference sweeps remain separate.

The unchanged collection and analysis programs passed separately implemented state/socket and numerical checks: 3,600 terminal episodes, 16,601 model request/response chains, 21,163 tool calls and 4,550 cover calls. Both model manifests and all supporting weight blobs matched their pre-run hashes. The original slow audit was stopped for filesystem I/O performance, its logs were retained, and the identical check programs completed in an authorized filesystem environment. No model request, raw result, analysis rule or test selection changed during that adjustment.

See `REPRODUCE.md` for offline state replay, feature reconstruction, statistics and attacker refitting. The insertion-ready English text is `latex/m3-llm-results.tex`; the report includes every condition and every specified attacker. The R101 main manuscript and supplement are unchanged.
