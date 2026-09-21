# Admission and Execution Value v3

This phase separates resource facts, policy decisions, decision-source selection,
and effects. Resource Management remains the sole owner of registry, queue, lease,
and effect execution. Admission and Execution Value are pure policy components.

## Ownership and flow

```text
raw resource/process facts
  -> AdmissionObservationBuilder / ExecutionObservationBuilder
  -> immutable versioned observation
  -> pure component policy
  -> component-versus-legacy shadow diff
  -> run-level source router
  -> advisory decision record
  -> Runtime safety validation
  -> validated ResourceEffectCommand (Admission only)
  -> ResourceEffectExecutor
```

`scienceflow/research/control/admission/` owns Admission observation normalization, review policy,
LLM-output normalization, replay records, and the run-level source router. It does
not import resource mechanisms/effects or solver code. Physical startup enforcement
lives under `solver/lnr/resources/runtime/control/admission/`; the former flat
`solver/lnr/resource_runtime/admission.py` path has been removed.

`scienceflow/research/control/execution_value/` owns the scientific/resource observation adapter,
pure continuation-value policy, evidence references, replay records, safety audit,
and source router. It never imports Resource Management or emits resource effects.

## Decision-source switch

Both components accept one run-level source:

- `component`: select the new component decision and archive the legacy diff;
- `legacy`: select the explicit compatibility decision;
- `shadow`: select legacy while computing and archiving the component decision.

The defaults are `component`, configured by
`resource_admission_decision_source` and
`resource_execution_value_decision_source`. Switching either value is a run-level
rollback; it does not require changing queue, lease, process, or workspace state.

Admission replay is stored under
`task_logs/resource/module_state/<worker_id>/admission/decisions.jsonl`; Execution Value replay
is stored under
`task_logs/resource/module_state/<worker_id>/execution_value/decisions.jsonl`. Records use
semantic hashes and deterministic IDs, so duplicate observation/decision replay is
idempotent and archives can be reopened after resume.

## Safety invariants

- An Admission `RUN_NOW` or `OBSERVE_THEN_RUN` proposal is normalized to `PENDING`
  unless an atomic lease-grant path is present.
- The selected Admission proposal still passes through
  `ResourceRuntime.grant_llm_admission_lease`, admission-safety checks, validated
  effects, and atomic lease acquisition. A source switch cannot directly acquire.
- Execution Value is advisory-only. Its result is written to
  `job.execution_value_shadow` and is never consumed by kill/release code.
- Existing hard Safety checks, deliverable-completion guard, near-deliverable veto,
  kill-intent snapshot/revalidation, and Runtime effect validation remain outside
  and downstream of policy selection.
- `medium` or `unknown_protocol` metric metadata is not interpreted as improvement;
  only the explicit legacy boolean `metric_value_useful` may populate
  `metric_improved`.

## Compatibility and rollback

Default component output preserves the previous Execution Value payload shape and
Admission normalized fields. Legacy import paths remain stable. Replay persistence
is soft-failure telemetry: an archive write error cannot change process or resource
control. Rollback consists of setting the run-level source to `legacy`; no durable
mechanism state migration is required.
