"""Make complete presentation tables from verified outputs; no new fitting."""
import json
from common import H, load

assert load(H/'verification/formal-analysis-verified.json')['status']=='PASS'
rows=load(H/'analysis/table-values.json')['rows']
paired=load(H/'analysis/paired-comparisons.json')
names={'none':'No cover','transport_drop':'Proxy discard','read':'Read cover','isolated':'Isolated, hidden','live_write':'Live write','isolated_visible':'Isolated, visible'}
models={'qwen3:8b':'Qwen3:8B','llama3.1:8b':'Llama3.1:8B'}
def ptext(p):return f'{p:.2g}' if p<.001 else f'{p:.3f}'

intro='''# M3 LLM-planner results

The six-arm experiment is complete: 3,600 formal episodes, including 1,440 held-out executions of 120 paired test fixtures. Qwen3:8B and Llama3.1:8B used fixed weight identities, real LangGraph decisions, and local MCP Streamable HTTP over TLS 1.3/HTTP/2. Each model/arm has 120 training, 60 validation and 120 test fixtures. There are no unresolved formal requests. A separate development-run request remains unknown and was never retried or included in these results.

**The strongest finding is the gap between completing a task and preserving its business state.** Under live-state cover, Qwen completed 102/120 tasks but preserved the exact reference state in only 7/120; Llama completed 76/120 but preserved state in only 3/120. Respectively, 95 and 73 completed tasks had incorrect global state. The state-integrity reductions versus no cover survived the predeclared multiplicity correction for both models. The task-completion reduction survived correction for Qwen, but not for Llama.

**Live writes produced severe state loss while their recognition scores stayed in the range already observed with other cover policies.** The primary attacker scored 62/120 on Qwen live writes and 80/120 on Llama live writes. Proxy discard, read, and isolated execution scored 61–62/120 and 72–82/120 respectively. This is a measured comparison within constructed adverse business operations, not a claim that all cover policies are information-theoretically equivalent or that WRA has this defect.

**Marked visible decoys affected individual paths, with no established average gain or loss in the primary endpoints.** Hidden and visible isolated arms had identical cover responses in all 120 pairs per model. Honest action sequences differed in 16 Qwen and 65 Llama pairs. Visible-minus-hidden recognition, goal and integrity contrasts all had Holm-adjusted p=1. Mean prompt tokens increased from 1668.34 to 1969.49 (18.1%) for Qwen and from 2251.48 to 2675.95 (18.9%) for Llama. Non-visible arms also showed some execution variation; the released path audit retains it.

## All held-out conditions

Every count below has denominator 120. “Selected” is the LR/RF attacker chosen by validation balanced accuracy; it is not the largest test score. Goal requires the requested action and object, prerequisites and target postcondition. State compares the entire final state with the single intended-action reference. The stricter object requirement means state can match even when the goal predicate fails.

| Model | Condition | Selected correct | Goal | State | Goal with state error | Call bytes × | Total TLS bytes × |
|---|---|---:|---:|---:|---:|---:|---:|
'''
out=[intro]
for r in rows:
 c=r['costs'];out.append(f"| {models[r['model']]} | {names[r['arm']]} | {r['correct']} ({r['selected']}) | {r['goal_success']} | {r['state_integrity']} | {r['goal_with_state_error']} | {c['tool_byte_ratio']:.3f} | {c['transport_byte_ratio']:.3f} |\n")
out.append('''
All 182 planned held-out decoys triggered in every cover cell. Both model families completed all formal requests; Llama had 1/120 step-limit episodes in no-cover, proxy-discard, read and hidden-isolated cells, 2/120 in live-write, and 0/120 in visible-isolated. Qwen had none. All were retained.

## Every attack and position control

The six classes are balanced, so uniform chance is 20/120. The primary LR/RF comparison falls substantially under random cover, but the stronger observed controls must remain visible: the last-destination rule reaches 75–77/120 in Qwen cover arms. Attained scores are lower bounds on what an attacker can achieve with this observation. They are not privacy guarantees.

| Model | Condition | Frozen | LR | RF | Last destination | Penultimate destination |
|---|---|---:|---:|---:|---:|---:|
''')
for r in rows:
 a=r['attack_correct'];out.append(f"| {models[r['model']]} | {names[r['arm']]} | {a['frozen']} | {a['LR']} | {a['RF']} | {a['position_last']} | {a['position_penultimate']} |\n")
out.append('''
## Prespecified paired comparisons

Each endpoint has its own 12-comparison Holm family. Intervals use 10,000 paired fixture resamples stratified by requested action, conditional on fitted attackers and this workload. These are fixture-level intervals, not estimates of template, deployment or training-selection uncertainty. All ten primary cover-versus-no-cover recognition contrasts pass the prespecified family correction (largest adjusted p=3.08e-8). The visible-versus-hidden contrasts do not establish equivalence.

''')
latex=[r'\begin{table}[ht]',r'\centering\small',r'\setlength{\tabcolsep}{8pt}',r'\caption{Selected prespecified contrasts. Differences are percentage points (condition minus reference). Each endpoint uses its own 12-comparison Holm family; the full 36 contrasts are released.}',r'\label{tab:m3-llm-contrasts}',r'\begin{tabular}{lllrll}',r'\toprule',r'Model & Contrast & Endpoint & Difference & 95\% CI & Holm $p$ \\',r'\midrule']
for endpoint, vals in paired.items():
 out.append(f'### {endpoint}\n\n| Model | Condition − reference | Difference pp | Conditional 95% CI pp | Raw p | Holm p |\n|---|---|---:|---|---:|---:|\n')
 for r in vals:
  lo,hi=r['conditional_ci_pp'];contrast=names[r['condition']]+' − '+names[r['reference']]
  out.append(f"| {models[r['model']]} | {contrast} | {r['difference_pp']:.2f} | [{lo:.2f}, {hi:.2f}] | {ptext(r['p_raw'])} | {ptext(r['p_holm'])} |\n")
  if r['condition']=='live_write' or r['reference']=='isolated':
   short='Live--none' if r['condition']=='live_write' else 'Visible--hidden'
   label={'privacy':'Recognition','goal_success':'Goal','state_integrity':'State'}[endpoint]
   latex.append(f"{models[r['model']]} & {short} & {label} & {r['difference_pp']:.2f} & [{lo:.2f}, {hi:.2f}] & {ptext(r['p_holm'])}"+r' \\')
latex += [r'\bottomrule',r'\end{tabular}',r'\end{table}',
 r'All 182 planned held-out decoys triggered in every cover cell. No held-out response had invalid JSON. Qwen reached no step limits; Llama reached the limit in one no-cover, proxy-discard, read, and hidden-isolated execution, two live-write executions, and no visible-isolated executions. All remain in the denominators.',
 r'The action-path audit records hidden-arm variation as well as the visible contrast. Relative to hidden isolation, proxy-discard and read had different honest choices in 1 and 0 Qwen pairs, and 15 and 15 Llama pairs; the visible arm differed in 16 and 65 pairs. These are descriptive path comparisons, not an additional significance-test family.',
 r'Llama already had imperfect task execution without cover (82/120 goals and 69/120 exact states). Its no-cover traces included 69 episodes with multiple business attempts. The analysis retains that baseline behavior rather than treating every state error as caused by cover.']
(H/'latex/m3-llm-comparisons.tex').write_text('\n'.join(latex)+'\n',encoding='utf-8')
out.append('''
## Interpretation for the Agent SoK

The result supports a concrete evaluation distinction: traffic obfuscation, executing the requested action, and preserving business state are separate outcomes. A task-success-only evaluation would conceal most of the collateral effects of the constructed live-write policy. State-isolated cover avoids directly applying decoy writes to the primary fixture, while exposing marked responses is a separate planner-interface choice. The new visibility control supplies a real LLM comparison, but does not show a reliable average effect on recognition or utility at this sample size.

The synthetic adverse writes deliberately consume or modify business state. This measures the consequence under LLM planning; it does not discover a production vulnerability or reproduce WRA's actual mechanism. Llama's baseline is already imperfect (82/120 goals and 69/120 intact states), so its absolute state failures cannot all be attributed to cover.

## Costs, scope and verification

Cover call-byte ratios range from 1.280 to 1.346. Total TLS-byte ratios range from 1.131 to 1.149 because this protocol initializes all seven MCP sessions for each episode. Mean local wall times are 8.14–9.94 seconds per test episode, including setup, journaling and two-worker contention; these are not production latency estimates. All resource summaries, intervals and model token counts are in `analysis/outcomes-costs.csv`.

The observer uses destinations and ciphertext byte counts within supplied call/episode windows. All endpoints share `/mcp`; the reference replay's variable-path read-cover result is not carried over. Physical timing, the model link, WAN behavior, shared-connection localization, unseen templates and real customer workloads are outside this experiment. The original fixed-position and k=1–4 reference sweeps remain separate.

The unchanged collection and analysis programs passed separately implemented state/socket and numerical checks: 3,600 terminal episodes, 16,601 model request/response chains, 21,163 tool calls and 4,550 cover calls. Both model manifests and all supporting weight blobs matched their pre-run hashes. The original slow audit was stopped for filesystem I/O performance, its logs were retained, and the identical check programs completed in an authorized filesystem environment. No model request, raw result, analysis rule or test selection changed during that adjustment.

See `REPRODUCE.md` for offline state replay, feature reconstruction, statistics and attacker refitting. The insertion-ready English text is `latex/m3-llm-results.tex`; the report includes every condition and every specified attacker. The R101 main manuscript and supplement are unchanged.
''')
(H/'RESULTS.md').write_text(''.join(out),encoding='utf-8')
print('Summary and all 36 comparisons written from verified outputs')
