"""Raw shell is an explicit opt-in for ScienceFlow's ordinary TUI chat."""

import asyncio
import json

import pytest
from click.testing import CliRunner
from inquirycraft.cli import create_cli
from inquirycraft.events import NullEventSink
from inquirycraft.runtime import CancellationToken
from inquirycraft.tools import ReadTextTool, ShellTool, WriteTextTool, default_tools
from inquirycraft.tools.base import ToolContext

from scienceflow.interfaces.cli import main
from scienceflow.interfaces.cli.commands.run.tui import build_tui_command
from scienceflow.interfaces.ui.llm_cli import PoolRuntimeFactory, TuiPoolRuntimeFactory, TuiShellTool
from scienceflow.interfaces.ui.permission import TuiPermissionInteraction, TuiToolPermissions


def _schema_names(tools):
    return [schema["function"]["name"] for schema in tools.schemas()]


def test_tui_tool_schemas_require_explicit_shell_opt_in():
    factory = TuiPoolRuntimeFactory()
    assert _schema_names(factory._tools()) == ["read_text", "write_text"]
    assert isinstance(factory._tools().get("read_text"), ReadTextTool)
    assert isinstance(factory._tools().get("write_text"), WriteTextTool)
    with factory.permission_session():
        factory.permissions.allow_shell = True
        assert _schema_names(factory._tools()) == ["read_text", "write_text", "shell"]
        assert isinstance(factory._tools().get("shell"), TuiShellTool)
    assert _schema_names(factory._tools()) == ["read_text", "write_text"]
    assert _schema_names(default_tools()) == ["read_text", "write_text", "shell"]
    assert _schema_names(PoolRuntimeFactory()._tools()) == ["read_text", "write_text", "shell"]


@pytest.mark.asyncio
async def test_tui_text_tools_remain_workspace_contained(tmp_path):
    tools = TuiPoolRuntimeFactory()._tools()
    context = ToolContext("session", "run", "agent", tmp_path, NullEventSink(), CancellationToken())
    await tools.get("write_text").execute({"path": "inside.txt", "content": "safe"}, context)
    assert (await tools.get("read_text").execute({"path": "inside.txt"}, context)).output == "safe"
    with pytest.raises(ValueError, match="outside|workspace"):
        await tools.get("write_text").execute({"path": "../outside.txt", "content": "no"}, context)


@pytest.mark.asyncio
async def test_shell_opt_in_is_isolated_across_concurrent_tui_contexts():
    factory = TuiPoolRuntimeFactory()

    async def names(enabled):
        with factory.permission_session():
            factory.permissions.allow_shell = enabled
            await asyncio.sleep(0)
            return _schema_names(factory._tools())

    assert await asyncio.gather(names(True), names(False)) == [
        ["read_text", "write_text", "shell"], ["read_text", "write_text"]
    ]


def test_shell_permission_is_only_available_inside_tui_chat(tmp_path, monkeypatch):
    import inquirycraft.tui

    seen = []

    class FakeRuntime:
        async def aclose(self):
            pass

    class FakeTui:
        def __init__(self, runtime, **kwargs):
            pass

        async def run_async(self):
            pass

        async def shutdown_runtime(self):
            pass

    def create_runtime(self, options, **kwargs):
        seen.append(_schema_names(self._tools()))
        return FakeRuntime()

    monkeypatch.setattr(TuiPoolRuntimeFactory, "create_runtime", create_runtime)
    monkeypatch.setattr(inquirycraft.tui, "InquiryCraftTui", FakeTui)
    monkeypatch.setenv("SCIENCEFLOW_ALLOW_SHELL", "1")
    monkeypatch.setenv("SCIENCEFLOW_TUI_ALLOW_SHELL", "1")
    config = tmp_path / "models.json"
    config.write_text(json.dumps({
        "models": {"fake": {"model": "fake", "endpoints": [{"url": "", "key": "test"}]}},
        "defaults": {"code_models": ["fake"]},
    }))
    args = ["--workspace", str(tmp_path), "--model-config", str(config)]
    result = CliRunner().invoke(build_tui_command(), args)
    assert result.exit_code == 0, result.output
    assert seen == [["read_text", "write_text"]]


@pytest.mark.asyncio
async def test_tui_shell_defaults_to_120_seconds_without_changing_global_tool(monkeypatch):
    from inquirycraft.tools import shell_execution
    from inquirycraft.tools.base import ToolResult

    timeouts = []

    async def run_shell(arguments, context):
        timeouts.append(arguments.get("timeout"))
        return ToolResult(output="ok")

    monkeypatch.setattr(shell_execution, "run_shell", run_shell)
    permissions = TuiToolPermissions(allow_shell=True)
    await TuiShellTool(permissions).execute({"command": "true"}, None)
    await TuiShellTool(permissions).execute({"command": "true", "timeout": 33}, None)
    await ShellTool().execute({"command": "true"}, None)
    assert timeouts == [120, 33, None]
    assert TuiShellTool.input_schema["properties"]["timeout"]["maximum"] == 3600
    assert ShellTool.input_schema["properties"]["timeout"]["maximum"] == 3600


@pytest.mark.asyncio
async def test_tui_shell_keeps_existing_explicit_timeout_bounds():
    result = await TuiShellTool(TuiToolPermissions(allow_shell=True)).execute(
        {"command": "true", "timeout": 3601}, None
    )
    assert "between 0.1 and 3600 seconds" in result.error


def test_allow_shell_is_not_an_agent_or_inquirycraft_option():
    runner = CliRunner()
    tui_help = runner.invoke(main, ["tui", "--help"])
    assert tui_help.exit_code == 0, tui_help.output
    assert "--allow-shell" not in tui_help.output
    for command in (["agent", "run", "--help"], ["agent", "repl", "--help"]):
        assert "--allow-shell" not in runner.invoke(main, command).output
    assert "--allow-shell" not in runner.invoke(create_cli(), ["tui", "--help"]).output
    assert runner.invoke(main, ["agent", "tools", "list"]).output.splitlines() == [
        "read_text", "write_text", "shell"
    ]


class _PermissionHost:
    def __init__(self):
        self.messages = []

    async def notice(self, text):
        self.messages.append(text)


class _Delegate:
    tui_common_commands = ("/models", "/help")
    tui_commands = ()

    async def try_handle(self, text, host):
        return False

    async def aclose(self):
        pass


@pytest.mark.asyncio
async def test_permission_command_shows_tools_and_toggles_shell():
    factory = TuiPoolRuntimeFactory()
    with factory.permission_session():
        permissions = factory.permissions
        tools = factory._tools()
        interaction = TuiPermissionInteraction(_Delegate(), permissions)
        host = _PermissionHost()
        assert await interaction.try_handle("/permission", host)
        assert "read_text: allowed" in host.messages[-1]
        assert "write_text: allowed" in host.messages[-1]
        assert "shell: denied" in host.messages[-1]
        assert _schema_names(tools) == ["read_text", "write_text"]
        assert await interaction.try_handle("/permission shell allow", host)
        assert permissions.allow_shell is True
        assert _schema_names(tools) == ["read_text", "write_text", "shell"]
        assert "no OS sandbox" in host.messages[-1]
        assert await interaction.try_handle("/permission", host)
        assert "shell: allowed" in host.messages[-1]
        assert await interaction.try_handle("/permission shell deny", host)
        assert permissions.allow_shell is False
        assert _schema_names(tools) == ["read_text", "write_text"]
        assert "denied" in host.messages[-1]


@pytest.mark.asyncio
async def test_denied_shell_is_not_executed_and_schema_tracks_permission(monkeypatch, tmp_path):
    from inquirycraft.tools import shell_execution
    from inquirycraft.tools.base import ToolResult

    called = []
    async def run_shell(arguments, context):
        called.append(arguments)
        return ToolResult(output="ok")
    monkeypatch.setattr(shell_execution, "run_shell", run_shell)
    factory = TuiPoolRuntimeFactory()
    with factory.permission_session():
        tools = factory._tools()
        assert _schema_names(tools) == ["read_text", "write_text"]
        result = await tools.execute(
            name="shell", tool_input={"command": "true"},
            context=ToolContext("s", "r", "a", tmp_path, NullEventSink(), CancellationToken()),
        )
        assert "denied" in result.error
        assert not called
    with factory.permission_session():
        factory.permissions.allow_shell = True
        assert _schema_names(factory._tools()) == ["read_text", "write_text", "shell"]
    assert not called


def test_permission_command_is_in_tui_completion():
    wrapper = TuiPermissionInteraction(_Delegate(), TuiToolPermissions())
    assert "/permission" in wrapper.tui_common_commands
    assert wrapper.tui_completions("/permission shell") == [
        ("/permission shell allow", "Change shell permission"),
        ("/permission shell deny", "Change shell permission"),
    ]
