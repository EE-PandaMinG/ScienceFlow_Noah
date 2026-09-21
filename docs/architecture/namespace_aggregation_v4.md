# ScienceFlow V4 namespace aggregation

V4 changes physical Python import paths without changing Runtime, Worker, Stage,
Workspace, Memory, Gate, Evaluator, Assessment, or Finalization semantics. The
source tree is organized into 13 top-level packages so independently evolving
components have a stable owner instead of sharing the former `core` and `utils`
catch-all packages.

## Canonical owners

| Namespace | Responsibility |
|---|---|
| `scienceflow.runtime` | Policy-free orchestration, kernel, process, stage, and parallel execution |
| `scienceflow.research.state` | Workspace facts, memory projections, prompt context, and dataset inspection |
| `scienceflow.research.control` | Admission, execution value, resource policy, and EStra decisions |
| `scienceflow.research.quality` | Evaluation, gate decisions, assessment, and finalization |
| `scienceflow.runtime.observability` | Read-only monitoring, telemetry, logs, and interaction journals |
| `scienceflow.agent` | Agent runtime, factory, LLM clients, tooling, skills, and prompts |
| `scienceflow.interfaces.cli` | Stable command group and focused command modules |

The remaining top-level packages are `architecture`, `config`, `contracts`,
`safety`, `solver`, and `ui`. Organizational `__init__.py` files do not re-export
component implementations. `scienceflow.runtime.composition` remains the
default composition root.

## Import migration

| Removed path | Canonical path |
|---|---|
| `scienceflow.runtime_kernel` | `scienceflow.runtime.core.kernel` |
| `scienceflow.process_runtime` | `scienceflow.runtime.core.process` |
| `scienceflow.stage_lifecycle` | `scienceflow.runtime.core.stage` |
| `scienceflow.parallel` | `scienceflow.runtime.parallel` |
| `scienceflow.workspace` | `scienceflow.research.state.workspace` |
| `scienceflow.memory` | `scienceflow.research.state.knowledge.memory` |
| `scienceflow.prompt_context` | `scienceflow.research.state.knowledge.prompt` |
| `scienceflow.admission` | `scienceflow.research.control.admission` |
| `scienceflow.execution_value` | `scienceflow.research.control.execution_value` |
| `scienceflow.resource_management` | `scienceflow.research.control.resources` |
| `scienceflow.estra` | `scienceflow.research.control.estra` |
| `scienceflow.evaluator` | `scienceflow.research.quality.evaluator` |
| `scienceflow.gate` | `scienceflow.research.quality.gate` |
| `scienceflow.assessment` | `scienceflow.research.quality.assessment` |
| `scienceflow.finalization` | `scienceflow.research.quality.finalization` |
| `scienceflow.monitoring` | `scienceflow.runtime.observability.monitoring` |
| `scienceflow.telemetry` | `scienceflow.runtime.observability.telemetry` |
| `scienceflow.agent_factory` | `scienceflow.agent.factory` |

The deprecated `scienceflow.gates`, `scienceflow.core`, `scienceflow.utils`,
`scienceflow.research.solver.lnr.global_merge`, and solver finalization facades were
deleted. V4 deliberately does not provide `sys.modules` aliases or broad barrel
exports for these internal paths. Downstream code must move to the canonical
owner shown above.

## Stable external behavior

The console entry point remains `scienceflow`, and `python -m scienceflow.interfaces.cli`
continues to expose `prep`, `run`, `repl`, `parallel`, `monitor`,
`monitor-trace`, `resource-summary`, `replay-prepare`, and `agent`. Manifest,
configuration, workspace, journal, evaluator backend, reason-code, artifact,
and prompt formats are unchanged.

Static gates enforce the exact top-level package set, no root business modules,
at most eight direct Python files per top-level package, no old namespace
references, package-data inclusion, and the existing dependency direction
rules. Runtime parity and task-level validation remain mandatory for future
namespace changes.
