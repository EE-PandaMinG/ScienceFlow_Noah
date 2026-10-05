"""TUI-only controls for ordinary chat tool permissions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TuiToolPermissions:
    """Mutable permissions shared by one ScienceFlow TUI chat runtime."""

    allow_shell: bool = False


class TuiPermissionInteraction:
    """Handle /permission before forwarding input to the research adapter."""

    def __init__(self, delegate, permissions: TuiToolPermissions) -> None:
        self._delegate = delegate
        self._permissions = permissions

    @property
    def tui_common_commands(self):
        return ("/models", "/permission", *self._delegate.tui_common_commands[1:])

    @property
    def tui_commands(self):
        from inquirycraft.tui import TuiCommandSpec

        return (*self._delegate.tui_commands,
                TuiCommandSpec("/permission", "Show or change chat tool permissions",
                               ("shell", "allow|deny")))

    def tui_completions(self, text):
        prefix = str(text or "")
        if prefix.startswith("/permission "):
            choices = ("shell allow", "shell deny")
            query = prefix.removeprefix("/permission ")
            return [("/permission " + choice, "Change shell permission")
                    for choice in choices if choice.startswith(query)]
        hook = getattr(self._delegate, "tui_completions", None)
        return hook(text) if hook is not None else None

    async def try_handle(self, text, host):
        parts = str(text or "").strip().split()
        if parts and parts[0] == "/permission":
            if len(parts) == 1:
                shell = "allowed" if self._permissions.allow_shell else "denied"
                await host.notice(
                    "Chat tool permissions:\n"
                    "read_text: allowed (workspace restricted)\n"
                    "write_text: allowed (workspace restricted)\n"
                    f"shell: {shell}\n"
                    "Use /permission shell allow|deny to change shell access."
                )
            elif parts[1:] == ["shell", "allow"]:
                self._permissions.allow_shell = True
                await host.notice(
                    "Raw shell allowed for this TUI session. Commands run as your current user "
                    "with full host and network access and no OS sandbox."
                )
            elif parts[1:] == ["shell", "deny"]:
                self._permissions.allow_shell = False
                await host.notice("Raw shell denied for this TUI session.")
            else:
                await host.notice("Usage: /permission [shell allow|deny]")
            return True
        return await self._delegate.try_handle(text, host)

    def is_host_task_prompt(self, content):
        hook = getattr(self._delegate, "is_host_task_prompt", None)
        return hook(content) if hook is not None else False

    async def on_mount(self, host):
        hook = getattr(self._delegate, "on_mount", None)
        if hook is not None:
            await hook(host)

    async def aclose(self):
        await self._delegate.aclose()
