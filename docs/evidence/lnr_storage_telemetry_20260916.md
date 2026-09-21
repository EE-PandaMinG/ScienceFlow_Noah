# LNR storage telemetry verification — 2026-09-16

## Automated checks

- 99 focused ScienceFlow tests passed across storage telemetry, TUI accounting,
  workspace snapshots, snapshot fallback, workspace layout, LNR runtime,
  runtime kernel, and registered-task preparation.
- 25 managed-run and final-report tests passed.
- The InquiryCraft presentation check passed with approximate storage styling.
- 76 final ScienceFlow storage/task-panel/managed-run/report tests passed after
  compact task-row integration.
- 40 InquiryCraft TUI integration tests passed, including one-line dynamic
  Top-K names, responsive progress bars, resize alignment, and expanded rows.
- `git diff --check` and Python bytecode compilation passed.

The storage tests use guarded directory access: entering `dataset`, the explicit
input root, or an external symlink target raises immediately. The terminal
measurement completed without entering any of them. A hard-linked artifact was
also counted once in allocated bytes.

## Existing-run sample

Read-only measurement of the generated task root for `task-0014` produced:

| Field | Value |
|---|---:|
| Allocated bytes | 36,828,672 |
| Apparent bytes | 38,369,269 |
| Files | 677 |
| Directories | 509 |
| Symlinks | 79 |
| Excluded dataset directories | 2 |
| Scan errors | 0 |
| Scan duration | 911.64 ms |

The sample only called the measurement function; it did not modify the existing
run. The result establishes the current small-task cost and is not a general
latency guarantee. Large input datasets are excluded before traversal, while a
task with many generated files can still take longer to enumerate at exit.
