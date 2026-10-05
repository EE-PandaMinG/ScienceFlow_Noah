"""Compose InquiryCraft commands with ScienceFlow's plural endpoint pools."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace

import click
from inquirycraft.adapters import AskLLMAdapter
from inquirycraft.cli import ChatMonitor
from inquirycraft.memory import Conversation, JsonlConversationStore
from inquirycraft.runtime import AgentRuntime
from inquirycraft.tools import (
    ReadTextTool,
    ShellTool,
    ToolCollection,
    WriteTextTool,
    default_tools,
)
from inquirycraft.tools.base import ToolResult

from scienceflow.foundation.config.llm.llm_factory import build_stage_llm
from scienceflow.foundation.config.runtime.llm_lists import values
from scienceflow.foundation.config.schema.settings import StageConfig
from scienceflow.interfaces.ui.permission import TuiToolPermissions


class PoolRuntimeFactory:
    def _tools(self):
        return default_tools()

    def create_runtime(self, options, *, api_key, base_url, event_sink):
        models = values(options.model)
        if not models or not values(api_key):
            raise click.ClickException(
                "models and api_keys must each contain at least one value"
            )
        stage = StageConfig(
            models=models,
            api_keys=values(api_key),
            base_urls=values(base_url),
            max_tokens=options.max_tokens or 32768,
            http_timeout=options.timeout or 300,
            api_routing_mode=options.model_routing,
        )
        try:
            client = AskLLMAdapter(build_stage_llm(stage))
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        store = (
            JsonlConversationStore(options.session_log) if options.session_log else None
        )
        monitor = ChatMonitor(
            options,
            client.backend,
            values(base_url),
            models,
            len(values(api_key)),
        )
        return monitor.bind(
            AgentRuntime(
                llm=client,
                compaction_policy=monitor.policy(),
                provider_observer=monitor,
                options=replace(options, model=models[0]),
                tools=self._tools(),
                event_sink=event_sink,
                conversation=store.load() if store else Conversation(),
                conversation_store=store,
            )
        )


class TuiShellTool(ShellTool):
    """Shell opt-in for ordinary ScienceFlow TUI chat only."""

    description = (
        "Run a shell command as the current user with full host/network access "
        "and no OS sandbox. Default timeout: 120 seconds."
    )
    input_schema = {
        **ShellTool.input_schema,
        "properties": {
            **ShellTool.input_schema["properties"],
            "timeout": {
                **ShellTool.input_schema["properties"]["timeout"],
                "description": "Optional timeout in seconds; defaults to 120 (maximum 3600).",
            },
        },
    }

    def __init__(self, permissions: TuiToolPermissions | None = None):
        self.permissions = permissions or TuiToolPermissions()

    async def execute(self, arguments, context):
        if not self.permissions.allow_shell:
            return ToolResult(
                error="Raw shell is denied. Use /permission shell allow to enable it."
            )
        task = asyncio.current_task()
        if task is None:  # pragma: no cover - execute always runs in an event loop
            return await super().execute({"timeout": 120, **arguments}, context)
        self.permissions.track_shell(task)
        try:
            return await super().execute({"timeout": 120, **arguments}, context)
        finally:
            self.permissions.untrack_shell(task)


class TuiToolCollection(ToolCollection):
    """Keep shell dispatchable for enforcement while hiding its schema when denied."""

    def __init__(self, tools, permissions: TuiToolPermissions):
        super().__init__(tools)
        self.permissions = permissions

    def schemas(self):
        schemas = super().schemas()
        if self.permissions.allow_shell:
            return schemas
        return tuple(
            schema for schema in schemas if schema["function"]["name"] != "shell"
        )


class TuiPoolRuntimeFactory(PoolRuntimeFactory):
    def __init__(self):
        self._permissions = ContextVar(
            f"scienceflow_tui_permissions_{id(self)}", default=None
        )
        self._default_permissions = TuiToolPermissions()

    @property
    def permissions(self):
        return self._permissions.get() or self._default_permissions

    @contextmanager
    def permission_session(self):
        permission_state = TuiToolPermissions()
        permissions_token = self._permissions.set(permission_state)
        try:
            yield
        finally:
            self._permissions.reset(permissions_token)

    def _tools(self):
        permissions = self.permissions
        tools = (ReadTextTool(), WriteTextTool(), TuiShellTool(permissions))
        return TuiToolCollection(tools, permissions)


def plural_cli_options(command):
    """Keep the plural model alias flag on composed InquiryCraft commands."""
    aliases = {
        "model": ("--models", "--model"),
    }
    for param in command.params:
        if param.name in aliases:
            param.opts = list(aliases[param.name])
            param.help = (
                "Comma-separated aliases from models.json; defaults to code_models."
            )
    if isinstance(command, click.Group):
        for child in command.commands.values():
            plural_cli_options(child)
    return command
