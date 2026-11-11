# Live TLS-record timing and shadow-cover experiment

This is a timing extension to the Agent traffic SoK. It reuses the 300 synthetic M3 fixtures and the two fixed-weight Ollama models. It does not replace earlier data or establish a new-workload replication.

The source proposal is `74e2e8294b10dc2c0ba208924cd8abb58a9cf7ec`, `releases/r110/live-timing`. Its Chinese plan and English draft are preserved in `vendor/`. The finalized protocol is `experiment/analysis-plan.json`.

Five arms: none, immediate unmatched cover, sequential live gap/duration matching, concurrent live matching, and an independent hidden full shadow episode. All cover executes in isolated state. The experiment has one active episode and two Ollama inference slots. Calls on one shared service connection are serialized to define nonoverlapping record windows; calls to different services and model inference can overlap. This restriction is explicit and does not represent unrestricted per-service multiplexing.

Primary timing comes from encrypted-record completion at an opaque TCP relay. The independent verifier reassembles Npcap TCP payloads and compares every connection's record types, lengths and counts; it reports completion-time error. Logical call and episode windows are supplied. Neither timing attacker receives plaintext, operations, object IDs, true/shadow role, model-link traffic or model token counts. In the shadow arm the first call is not known to be real.

## Execution order

1. Verify every fixed model layer; test only the six disjoint development fixtures.
2. Freeze plan, collector, pool extractor, attack analysis, verifier and inputs; push and read back the freeze commit before formal collection.
3. Collect `formal-none-v1` (600 episodes); verify terminal requests, isolated state and independent captures.
4. Extract `pools/timing-pools.json` from the 120 TRAIN fixtures per model only. Freeze, push and read back the pools before any formal cover collection.
5. Collect `formal-cover-v1` (2,400 episodes), verify, analyze all planned attacks/families and independently recompute reported arithmetic.

Commands use Python 3.12 with the existing local M3 runtime. `collect.py --phase none --run formal-none-v1` and `collect.py --phase cover --run formal-cover-v1` refuse to start without matching remote-freeze receipts. They also refuse an existing output directory or collector lock. An interrupted request remains unknown and cannot be automatically retried. Any continuation needs a versioned itemwise audit.

The six superiority contrasts and six equivalence contrasts have separate prespecified Holm families. Equivalence means the selected timing attack suite's accuracy increment is within ten points, not universal cover indistinguishability. At 120 paired test fixtures and assumed discordance .2, planning power is about .574 at unadjusted alpha .05 and .095 at the first Holm threshold .05/6; inconclusive equivalence is permitted. The six-class prior is 1/6, while perfect recovery of an unordered pair of independent real/shadow labels yields a 7/12 target-guessing baseline.

Development outcomes are engineering checks and excluded from all scientific denominators. The rejected sum-only unconditional equivalence candidate is retained in local preformal records; it was replaced before any formal data because it discarded observed discordance information and had zero power under the planning model.

Packet captures, transcripts, TLS keys and model weights remain private. Public release is limited to reviewed synthetic, payload-free observations, predictions, pools, code, plans and verification receipts. Existing manuscripts and historical experiment bytes remain unchanged during collection.
