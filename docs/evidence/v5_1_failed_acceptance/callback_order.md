# Canonical callback order

Source: Git object `72b2ec478ebd7cbeff4cd77822bc1525890ba7a6`.

## Tool-result path

The old effective runtime committed the bounded tool feedback to factual memory before
calling ScienceFlow domain callbacks. The order to preserve is:

1. execute the canonical tool invocation and retain the raw `ToolResult`;
2. apply guard coaching and build the single provider-visible feedback projection;
3. append the tool message to factual memory;
4. call `candidate_archive` with the raw result;
5. process long-horizon ledger commit guards;
6. for successful Bash results, run embedded/full-run validation; its missing-score
   fallback may call `metric_interpretation`;
7. update the bare-run snapshot and call `stage_capture` when snapshot/artifact
   readiness allows it;
8. return the typed continue/terminate/finalize outcome to the agent runtime.

V5.1 maps steps 4-8 to InquiryCraft's post-tool-commit host contract. Output reduction
has one owner and is not repeated by the host callback.

## Text-only path

`text_only_decision` runs before the generic auto-continue policy. A non-empty callback
result terminates the current IQ session with that output. Agentic routing and generic
`RunPolicy.on_text_only()` are fallbacks only when the typed callback does not decide.

## Context path

`context_compact_observer` surrounds compaction phases. On an automatic context limit,
`context_limit_estra` runs before primary compaction and may return an early terminal or
stage-switch result. V5.1 must consume that result as a typed runtime decision rather
than leaving it in metadata.
