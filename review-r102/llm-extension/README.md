# M3 with LLM planners

This extension runs the PR's executed-cover comparison with fixed Qwen3:8B and Llama3.1:8B planners, plus an isolated-cover condition that shows marked decoy responses to the planner. The protocol uses 3,600 formal episodes, actual local MCP Streamable HTTP over TLS 1.3/HTTP/2, and one-to-two randomly placed decoys.

- [Results and interpretation](RESULTS.md)
- [Result report PDF](m3-llm-report.pdf)
- [Protocol and endpoints](PROTOCOL.md)
- [Offline verification and reproduction](REPRODUCE.md)
- [Insertion-ready paragraph and tables](latex/)
- [Analysis outputs](analysis/) and [synthetic evidence](data/)
- [Audit of the original PR inputs](PR-AUDIT-NOTES.md)

The original reference-program replay and R101 manuscript remain separate. The added experiment uses a fixture holdout; it does not add a human analyst study. `manifest.json` binds the files in this review bundle.
