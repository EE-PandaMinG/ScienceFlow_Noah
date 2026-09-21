# V5.1 failed-acceptance baseline

This directory freezes the V5 remote failure used by the V5.1 regression suite.
The source checkout and workspaces remain on H200; `SHA256SUMS` makes the referenced
evidence immutable without copying large interaction logs into Git.

- Captured: 2026-08-29
- Remote root: `/home/mingming/miing_agents_wsp/scienceflow_multi_modules_v5_6b46f12`
- ScienceFlow commit: `6b46f12a078ed3be337ffcd493229fe95c8eefa6`
- InquiryCraft commit: `46329a41702ad667f13f248ca8bd964baf13e3e6`
- Model: `Qwen3.6-27B`
- Cases: Circle Packing, Nomad2018 Deep, SciModelingBench TFBind8
- Shape: 2 workers, seed 2222, 3600-second agent budget, 4200-second outer watchdog

All three cases ended as `budget_done/time_budget_expired` at about 4205 seconds.
All six workers produced a syntactically valid candidate, but all six `stage.log`
files are empty and no authoritative final manifest exists. Provider telemetry has
239 rows whose input/output/cached-token fields are all zero; the vLLM process-level
cumulative counters observed at diagnosis time were 222,792,668 prompt tokens and
196,980,000 cached prompt tokens (88.41%), so the per-run zero values are a telemetry
transport failure rather than proof of a cold prefix cache.

The canonical pre-V5 callback-order baseline is commit `72b2ec478ebd7cbeff4cd77822bc1525890ba7a6`.
The canonical original-project reference is commit
`fd54f300abab5d11912f363870af5af4145a67a2`; read it from Git objects or a clean
worktree, never from the active compatibility-experiment worktree.
