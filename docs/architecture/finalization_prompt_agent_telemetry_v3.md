# Finalization, Prompt Context, Agent Factory, and Telemetry v3

This phase removes four remaining cross-cutting responsibilities from the LNR
solver surface while preserving the existing prompts, final artifacts, manifests,
and legacy event files byte-for-byte where they are public contracts.

## Finalization

`scienceflow/research/quality/finalization/` is the canonical owner of candidate evidence packing,
deterministic fallback ranking, final artifact materialization, submission links,
global-merge execution, and worker outcome classification. `FinalizationService`
is the production boundary used by the solver. The former
`solver/lnr/global_merge/*`, `solver/lnr/submission_links.py`, and runtime-local
finalization modules are removed; orchestration delegates to the canonical quality owner.

Runtime still owns when reduction starts and its deadline. Finalization owns how
candidates are collected, ranked, materialized, evaluated, and represented in the
merge manifest. A merge-agent timeout remains distinct from overall finalization:
the deterministic fallback may still satisfy the final-artifact requirement while
`agent_status=failed` records the timeout.

## Prompt Context

`PromptContextBuilder` projects task, Workspace, Memory, peer-worker, Resource,
Gate/validity, EStra, skill, and tool/output-policy facts into a versioned immutable
projection with a semantic hash. It performs no I/O and calls no LLM. The worker
runtime consumes the projection and then passes the same fields to the frozen LNR
prompt renderer, preserving the rendered first-user prompt bytes.

## Agent Factory

`AgentFactory` is the only LNR call path to the orchestrator's ScienceAgent
constructor. It gives each construction an explicit role, correlation identifiers,
deterministic per-factory sequence, and a soft-failure build trace. Main,
ResourceArbiter, and ResourceAdmissionArbiter agents now use this boundary. Agent
runtime configuration remains an adapter concern; the factory does not own research
policy, tools, Workspace, or Memory state.

## Correlation Telemetry

`CorrelationJournal` appends versioned, idempotent envelopes under
`module_state/telemetry/correlation.jsonl`. Envelopes correlate run, worker, process,
stage, event, sequence, source, event type, and payload hash. Runtime hook traces,
Stage Lifecycle transitions, and Agent Factory builds publish through soft sinks.

Legacy JSONL files are not replaced or modified: correlation is an additive index.
Telemetry write/sink failures never alter hook, stage, agent, process, or finalization
outcomes. Reopening a journal reconstructs its idempotency set for resume/replay.
