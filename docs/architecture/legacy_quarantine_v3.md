# Legacy removal and migration contract (V3.1)

## Outcome at 0.2.0

ScienceFlow 0.2.0 removes the expired legacy LNR import facades and their
compatibility switch. There is one canonical public import for each component;
no runtime policy or environment variable can reactivate the removed paths.

## Deprecation window

The following replacements were announced for ScienceFlow `>=0.1,<0.2` and are
required at 0.2.0:

- `scienceflow.research.solver.lnr.legacy_solver` -> `scienceflow.research.solver.lnr.orchestration.solver`
- `scienceflow.research.solver.lnr.resources.runtime.observer.legacy_controller` ->
  `scienceflow.research.solver.lnr.resources.runtime.observer.controller`

The old paths now raise `ModuleNotFoundError`. The replacement paths retain the
public class identities used by supported callers.

## Coordinator residual register

The temporary `scienceflow.foundation.architecture.coordinator_residual` register was
removed after both `solver_core.py` and `observer_core.py` were decomposed. The
public facades now contain only explicit descriptor bindings to responsibility
modules; no residual implementation core remains.

## Removed compatibility surface

- `scienceflow.research.solver.lnr.legacy_solver`
- `scienceflow.research.solver.lnr.resources.runtime.observer.legacy_controller`
- `LnrConfig.legacy_backend_mode`
- `SCIENCEFLOW_LEGACY_BACKEND_MODE`
- `scienceflow.legacy_quarantine`

## Required release gate

The canonical runtime must pass the full local test suite, runtime parity, legacy
workspace/resume replay, and the Circle Packing plus Nomad2018 Deep H200
2-worker/1-hour cases. The case audit must also prove no worker/process, lease,
waiter, transaction, or final-artifact leak.
