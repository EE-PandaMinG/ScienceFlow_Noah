# TUI shell monitoring (TODO)

Ordinary TUI chat shell commands now have no default timeout. They remain foreground
commands: leaving the TUI stops them, and they are not resumable research runs.

Later, reuse the long-research monitor's lightweight, asynchronous presentation
approach to show process state, elapsed time, time since last output, resource
usage, and links to the existing shell output logs. Keep the shell lifecycle separate from managed research runs. Shell is available
by default; Esc and TUI shutdown cancel foreground execution. A silent command is not
necessarily stalled; only report a network or process failure when execution
provides evidence. Monitor sampling must not delay stdout/stderr streaming or
command cancellation.
