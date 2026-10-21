"""Compose InquiryCraft commands with ScienceFlow's plural endpoint pools."""

from __future__ import annotations

import json
from dataclasses import replace

import click
from inquirycraft.adapters import AskLLMAdapter
from inquirycraft.cli import ChatMonitor
from inquirycraft.cli.chat_profiles import ChatProfile, ProfileStore
from inquirycraft.llm import SameRoundRetryPolicy
from inquirycraft.memory import Conversation, JsonlConversationStore
from inquirycraft.runtime import AgentRuntime
from inquirycraft.tools import (
    ReadTextTool,
    ShellTool,
    ToolCollection,
    WriteTextTool,
    default_tools,
)

from scienceflow.foundation.config.llm.llm_factory import build_stage_llm
from scienceflow.foundation.config.llm.model_registry import default_model_config_path
from scienceflow.foundation.config.runtime.llm_lists import values
from scienceflow.foundation.config.schema.settings import StageConfig


class _ScienceFlowProfileStore(ProfileStore):
    """Keep chat profiles in SF while reading an existing IQ profile on first use."""

    def __init__(self):
        super().__init__(default_model_config_path().with_name("chat_profiles.json"))
        self._legacy = ProfileStore()

    def load(self, key):
        for store in (self, self._legacy):
            if store.path.exists() and key in json.loads(store.path.read_text()):
                return super().load(key) if store is self else store.load(key)
        return ChatProfile(output_reserve=32768).validate()


class _ScienceFlowChatMonitor(ChatMonitor):
    """Expose the effective backend limit with both released and source IQ."""

    @property
    def output_limit(self):
        instances = getattr(self.backend, "_instances", [self.backend])
        return min(int(instance.max_tokens) for instance in instances)

    def _sync_output_limit(self):
        instances = getattr(self.backend, "_instances", [self.backend])
        if self.runtime is not None and instances:
            self.runtime.options = replace(self.runtime.options, max_tokens=self.output_limit)

    def bind(self, runtime):
        bound = super().bind(runtime)
        self._sync_output_limit()
        return bound

    def set_profile(self, index, profile):
        super().set_profile(index, profile)
        self._sync_output_limit()


class PoolRuntimeFactory:
    def _tools(self):
        return default_tools()

    def create_runtime(self, options, *, api_key, base_url, event_sink, tools=None):
        models = values(options.model)
        keys = values(api_key)
        endpoints = values(base_url)
        if not models or not keys:
            raise click.ClickException(
                "models and api_keys must each contain at least one value"
            )
        stage = StageConfig(
            models=models,
            api_keys=keys,
            base_urls=endpoints,
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
        monitor = _ScienceFlowChatMonitor(
            options,
            client.backend,
            endpoints,
            models,
            len(keys),
            store=_ScienceFlowProfileStore(),
        )
        return monitor.bind(
            AgentRuntime(
                llm=client,
                llm_retry_policy=SameRoundRetryPolicy(
                    max_attempts=3,
                    base_delay_sec=1.0,
                    max_delay_sec=4.0,
                ),
                compaction_policy=monitor.policy(),
                provider_observer=monitor,
                options=replace(options, model=models[0]),
                tools=self._tools() if tools is None else tools,
                event_sink=event_sink,
                conversation=store.load() if store else Conversation(),
                conversation_store=store,
            )
        )


class TuiShellTool(ShellTool):
    """Shell execution for ScienceFlow TUI chat and task preparation."""

    description = (
        "Run a shell command as the current user with full host/network access "
        "and no OS sandbox. No default timeout; optionally set a timeout "
        "in seconds (maximum 3600)."
    )


class TuiPoolRuntimeFactory(PoolRuntimeFactory):
    def _tools(self):
        from scienceflow.interfaces.ui.research.control.workspace_tool import (
            WorkspaceInfoTool,
        )

        return ToolCollection(
            (ReadTextTool(), WriteTextTool(), WorkspaceInfoTool(), TuiShellTool())
        )


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
