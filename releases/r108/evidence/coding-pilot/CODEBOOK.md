# Execution-outcome coding: clarified decision rules

This manual separates an observed action from an evaluated execution outcome. It applies to source evidence, not to the correctness of a paper or the quality of an Agent. The unit is a named setting; several settings can inherit one collection population. Original C1, C2 and C3 files remain unchanged under `original/`.

## Status decision

1. **Identify the execution and its intended endpoint.** Record whether the endpoint is an application task, a probe/parser response, a prevention objective, or a behavioral-generation constraint. Classification accuracy about that execution is a separate attack endpoint.
2. **Not applicable** requires no new execution population to assess in this setting: e.g., preference-only records or a deterministic transformation of already captured traces. A study's failure to evaluate task success does **not** make success inapplicable. Record inherited source executions separately from outcomes under an unexecuted transformation.
3. **Reported** requires an explicit evaluated outcome under a named criterion and a population to which the reported outcome applies. A source-defined success rate or a success/failure count qualifies even when its criterion is not independently validated. Keep criterion and population limitations in separate columns. For a probe study, explicitly evaluated parser success, repair, reachability or prevention can qualify as a *probe* outcome; it never becomes original application-task success.
4. **Partly reported** records an assessed component or restricted subset: a capability-based retention rule, persona-consistency diagnostic, plan-validity check or stated subgoal assessment. A stopping rule alone is only partial if it supplies such a specified component; mere presence of a final message is insufficient. Name the unassessed component.
5. **Not located** means that the inspected scope contains an execution population but no evaluated outcome under the preceding rules. An action label, a log file, a completed HTTP request or an attack classifier score alone does not fill this field.

## Boundary examples

- **ANT:** scenario and risk labels, logged primitives and final responses establish labels/actions. They supply no inspected task-success result. All four settings are `not_located` for an evaluated execution outcome.
- **Cloud benchmark:** Section IV-A reports 4,070 successful and 42 failed runs (98.9%), so the collection-level source-defined outcome is `reported`. The conflicting 2,838/3,970 capture totals remain unresolved; the rate is not a per-setting or independent goal-correctness estimate.
- **PersonaFingerprint:** persona-consistency and diversity diagnostics concern actual generated behavior and are `partly_reported`, not inapplicable. They do not establish completion of an application task.
- **AgentTrace:** measured parser/repair responses are `reported` *probe* outcomes, not an application's task utility.
- **Communication graphs, active:** Section 9.5/Table 4 measures live front-running in 100 rounds per condition. This is a `reported` competition outcome, distinct from Section 9.4's analytical ranking leverage.
- **Communication graphs, transformed captures:** transformations do not re-execute applications. The outcome under that transformation is `not_applicable`; original-task utility of a deployed defense remains unmeasured.
- **HTTP signatures:** request/header observations and stable signatures do not provide a task-success criterion. The inspected execution outcome is `not_located`.

## Failure-handling field

`reported` specifies how failed/refused/interrupted executions enter, leave or repeat in the declared population. `partly_reported` covers only a failure type or collection filter; `not_located` means no treatment found in the stated scope; `not_applicable` requires no new execution population. Retaining successes alone is an explicit selection rule, not evidence that failures cannot occur. The present adjudication changes the requested outcome records; original failure-status encodings remain available for sensitivity analysis.

## Pilot provenance and interpretation

C1 is the released author extraction. C2 and C3 are two non-blind AI coding passes from the same model according to the supplied provenance. C2 had seen aggregate counts; C3 had seen ten C1 setting labels. They are not three independent human coders. Agreement and kappa describe this coding-manual pilot only. Setting-bootstrap intervals treat rows as exchangeable, despite shared sources and coder dependence; they are descriptive sensitivity summaries, not population reliability bounds.

The fifteen C1-versus-both-AI outcome disagreements are source-adjudicated with before/after values and reasons. A majority vote does not override the cited source. Other rows retain their earlier extraction, explicitly marked as not freshly adjudicated in this pass. No post-adjudication kappa is used as independent validation.
