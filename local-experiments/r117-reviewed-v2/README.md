# R117 reviewed local diagnostics

This task-owned copy is based on PR #9, commit b26b5bab8afae5031abf7a643d2c0b4e0cf49eeb. The original checkout is preserved unchanged under revision-preview/r117-remote-pull/upstream/.

Read PROTOCOL.md for the reviewed scientific definitions, corrections and stopping rules. The upstream README remains available in that input checkout; its suggested interpretations do not override this protocol.

Execution order: focused synthetic/metamorphic checks; input sealing; code/dependency/runtime freeze; public code/plan/freeze readback on codex/r117-p0-v2; sequential P0-T, P0-B, P0-A and P0-C; separate saved-vector/statistic and input-preservation verification. run_queue.py records the actual process/log state and refuses an existing queue lock. Full reproduction is required before ablations.

All inputs and individual outputs remain local. In particular LOCAL-ONLY-* files, run-v1/, run-v2/, logs containing individual data and the complete input package must never be staged for GitHub. Only an explicit allowlist of code, this protocol and the hash-only freeze is published before scoring. No result publication is automatic.

P0 is exploratory reused-workload analysis, not new LLM execution. W6 and P1 new collection are not implemented or started by this queue. A valid negative or inconclusive result can complete P0.
