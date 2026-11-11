# LLM extension of draft PR #4

PR commit: `d42204c4a6b888c059220f5cf7ac79ee0666fa77`. The pulled `pr4/review-r102/` inputs and all R101 files are preserved. No PR merge has been performed.

The new experiment keeps the six PR action classes, business-state transitions, random one-to-two decoys, and five cover policies. A sixth condition executes the same decoys on a cloned state and shows their explicitly marked responses to the LLM. Genuine Qwen3:8B and Llama3.1:8B decisions control checks, business action, target order, recovery, and completion. No reference planner supplies the business choice.

Each model/condition has 120 training, 60 validation, and 120 held-out test fixtures. Splits are by fixture; task phrasing comes from the existing synthetic workload, so this is not an unseen-template or deployment-transfer claim. Both models use the same fixtures, cover draws and fixed seeds. Formal total: 3,600 episodes, including 1,440 test episodes. All terminal failures remain in the test population.

The primary schedule places one or two cover calls in preselected slots after the ticket and among the prerequisite/first business calls. This is the PR's random-placement condition adapted to a dynamic planner. Fixed-before/fixed-after and the k=1–4 oracle sweep remain reference-program results, not newly claimed LLM experiments.

Seven local MCP Streamable HTTP endpoints represent the seven named service destinations. Calls use actual TLS 1.3 and HTTP/2 sockets, with 4,096-byte request-body and 16,384-byte response-body padding quanta. A non-decrypting relay records TLS socket byte counts. The observation is destination plus bytes within supplied logical call/episode windows. Timing, WAN behavior, packet segmentation and the model link are outside this M3 observation. MCP uses a common `/mcp` path: the PR's differing HTTP request-path lengths are not presumed to persist.

The model's allowed actions enforce prerequisite checks but leave all six business choices and all three order identifiers available. After a business attempt the model can finish or take further actions. The isolated-visible condition does not forge assistant tool calls or pretend a background operation was requested by the user.

The business services are synthetic, in-memory fixtures. The proxy-discard arm synthesizes each cover reply from a disposable copy of the initial fixture and leaves no persistent business change. Read cover returns a non-mutating lookup acknowledgment. Isolated cover applies writes to a persistent cloned fixture; live-write cover applies them to the primary fixture. Only the isolated-visible arm forwards the explicitly marked cover replies to the planner. These distinctions define the controlled comparison; they do not reproduce the application behavior or operating cost of a production proxy or retail service.

Privacy, target completion, exact state integrity, tool traffic and model resources are evaluated on the same held-out fixtures. Attack selection uses validation data only. LR and RF are both reported, alongside the baseline-trained frozen attack and position rules. The analysis plan fixes comparison families and uncertainty before formal collection; intervals are conditional on the fitted attackers and synthetic workload.

The attack label is the requested business-action class, including episodes in which the planner takes another action or fails. Target completion requires all prerequisite checks, a successful requested action on the requested object, and the specified target-state postcondition. Exact state integrity instead compares the complete customer/order/ledger state with the single intended-action reference. These endpoints can disagree; neither is replaced by the other.

All seven MCP sessions initialize before the ticket and are reused within that episode. Call-byte costs exclude initialization; total TLS-byte costs include initialization and connection closing. Per-episode wall time starts before initialization and ends after the planner finishes, before session teardown. Model loading occurs outside the episode timer. Wall measurements include local journaling and two-worker contention; resource counts and bytes are reported separately.

Requests are journaled before dispatch. A missing terminal is unknown, not a failure; it is never automatically replayed or replaced. A collection stops for audit if a model/tool request cannot be resolved. Readiness runs are separate development fixtures and are never included in the paper's experiment denominator.

## Input audit findings

The original reference experiment implements TLS with `ssl.MemoryBIO`; it is a TLS cryptographic replay without actual network send/receive. Its connections are reused by service. Its random placement, synthetic adverse business writes, and no-timing observation must remain explicit. It does not demonstrate failure of WRA's actual decoy mechanism.

The PR's M2 rules are reproducible arithmetic over an existing extraction, not a fresh source audit. In particular, the deployment-prevalence flag is hard-coded false, and the nine intervention settings span different purposes. Counts must retain the inspected-setting denominator and purpose distinctions.

No new analyst study, source search, hosted API call, or claim of universal classical-assumption failure is part of this extension.
