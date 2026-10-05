"""Locate ScienceFlow's pre-workspace TUI sessions for InquiryCraft's picker."""

from hashlib import sha256
from pathlib import Path


def legacy_session_roots(workspace: Path, state_root: Path) -> tuple[Path, ...]:
    workspace_id = sha256(str(workspace.resolve()).encode()).hexdigest()[:20]
    return (state_root.expanduser() / "workspaces" / workspace_id,)
