# Current execution entry point

The original freeze is commit `198f3ba2b86a807ff37c37f6fe8f4e4a0ed422ce` on `codex/r110-live-timing-v1`. Its 26 published files were read back byte for byte. The original frozen README and collector remain preserved as historical inputs.

The cover-only correction was declared in commit `95b97bac44da3ad7468c6cfd4d5518b2e6bbe6ac`, before any formal cover data. Consecutive cover calls use an updated timing anchor; concurrent cover uses one persistent episode dispatcher. No fixture, model, attack or statistical comparison changes.

Use these actual entry points:

1. **None:** `experiment/collect.py --phase none --run formal-none-v1` — already running. Never start it a second time.
2. `verification/advance_to_pools_v3.py` waits for that run to finish, audits it, exercises the cover correction on development fixtures with no GPU overlap, extracts the training-only pools and writes `experiment/cover-freeze-v3.json`. It stops for Git readback.
3. Push/read back the new cover freeze and its bound files, including the pools. Save `verification/cover-freeze-v3-pushed.json` and `verification/pools-pushed.json`.
4. **Cover:** `experiment/collect_cover_v3.py --phase cover --run formal-cover-v1` — start once, after the preceding gates. The cover command in the preserved original README is superseded.
5. Verify the cover collection/captures, the protocol, and fixed weights; run the unchanged frozen `experiment/analyze.py`, then `experiment/verify_analysis.py`.

The live phase is recorded in `task-state.json` and the collector lock. A failure or unknown request requires inspection and versioned continuation, never replay. Raw captures, transcripts and TLS keys stay private. No final experiment result or manuscript revision has been claimed yet.

The cover-v3 deadline loop also corrects an observed development timer early wakeup without widening readiness tolerance. The generation-aware audit verified all 600 original none episodes and 143,920 record observations. Use verification/verify_collection_v2.py for the long cover capture; the original auditor remains preserved. Training pools contain 120 TRAIN fixtures per model only. No formal cover episode has started.
