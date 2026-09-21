# Memory and EStra ownership (V3-7)

## Canonical owners

`scienceflow.research.state.knowledge.memory` owns rebuildable stage-memory projection, memory-record
compaction, semantic replay hashes, and the narrow protected-context adapter.
Workspace stage records and the InquiryCraft memory context remain external
sources/capabilities; Memory does not own either implementation.

`scienceflow.research.control.estra` owns response parsing, decision normalization, model-port
planning, safe fallback, replay envelopes, and pure Runtime-command
mapping. It does not restore a Workspace, compact Memory directly, apply a
Runtime command, or bypass Safety.

The old `scienceflow.research.solver.lnr.lifecycle.records.stage_memory` and
`scienceflow.research.solver.lnr.transitions.estra` paths are import-compatible facades only.

## Production flow

```text
Workspace stage facts
  -> Memory StageMemoryCard projection
  -> deterministic/folded StageMemoryView

legacy prompt adapter
  -> EstraPlanRequest
  -> EstraPlanner primary model port
  -> optional isolated fallback port
  -> EstraDecision
  -> EstraDecisionEnvelope archive
  -> EstraRuntimeCommand proposal
  -> legacy pending-EStra adapter (temporary effect path)

prepared resume/continue prompt + source memory
  -> MemoryCompactionRequest
  -> prefix-safe/minimal-prefix selection
  -> InquiryCraft-compatible record files
  -> semantic projection hash
```

The command proposal is deliberately effect-free. Until the generic Runtime
command/effect switch is complete, the legacy pending-EStra adapter remains the
only compatibility effect path. The archive records the proposed command so
the later switch can be replayed and audited without changing the current
decision.

Periodic Stage-triggered decisions retain their Stage-count and observation
deduplication gates. A context-limit signal bypasses those periodic gates and
always uses the isolated model port with a bounded Stage-memory evidence view;
it must not copy the already full main-agent context into the controller call.
The absence of a historical switch candidate does not skip planning because
`current_workspace + redirect` remains a valid decision.

If every model attempt errors, times out, or returns an invalid envelope, the
planner emits the single safe route fallback: `current_workspace + continue`
(`keep_current`) with compaction. Fallback never ranks metrics or restores a
historical Stage. Every effective result, including this fallback, is recorded
as one canonical `estra_decision`; `decision_mode=safe_fallback` distinguishes
the protection result from a model-selected route.

## Persistence and replay

- Stage-memory cache remains under `.agent_memory/stage_memory` with its
  existing prompt version and files.
- EStra decision envelopes are stored below the worker control-log directory at
  `module_state/estra/decisions.jsonl`; Workspace snapshot restore cannot erase
  them.
- Envelope IDs and input/output hashes are deterministic. Re-appending an
  envelope is a no-op.
- Memory compaction hashes semantic role/message/extra-info content, excluding
  generated record UUIDs and timestamps, so equivalent replay has the same
  hash while the on-disk InquiryCraft format remains unchanged.

## Compatibility and rollback

- Existing prompts, legacy EStra JSONL events (including standalone
  `estra_deterministic_fallback` records), stage-memory rendering, context
  budget defaults, protected-prefix labels, and agent memory files are kept.
- The composition root is the source switch. Reverting it to the old facade
  disables the new planner/archive without rewriting a Workspace.
- Old Workspace memory remains readable; the new archive is additive and is not
  required to resume an old run.

## Residual legacy adapters

The solver still assembles task-specific prompt evidence, converts a planned
decision into the existing `pending_estra` structure, and performs the current
Workspace restore. These are explicit V3-9/V3-10 migration points; parsing,
normalization, compaction mechanics, protected-context mutation, archive, and
command mapping must not move back into the solver.
