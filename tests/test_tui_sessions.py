"""ScienceFlow TUI shares InquiryCraft's catalog, not its physical namespace."""

import json

from click.testing import CliRunner
from inquirycraft.cli import create_cli
from inquirycraft.cli.sessions import SessionCatalog
from inquirycraft.memory import JsonlConversationStore, Message

from scienceflow.interfaces.cli import main
from scienceflow.interfaces.cli.commands.run.tui import build_tui_command
from scienceflow.interfaces.ui.llm_cli import PoolRuntimeFactory


def test_scienceflow_chat_entries_share_sessions_and_standalone_iq_is_separate(tmp_path, monkeypatch):
    import inquirycraft.tui

    workspace = tmp_path / "workspace"
    old = workspace / ".scienceflow" / "sessions" / "old" / "session.jsonl"
    old.parent.mkdir(parents=True)
    JsonlConversationStore(old).append(Message(role="user", content="earlier"))
    models = tmp_path / "models.json"
    models.write_text(json.dumps({
        "models": {"fake": {"model": "fake", "endpoints": [{"url": "", "key": "test"}]}},
        "defaults": {"code_models": ["fake"]},
    }))
    chosen = []

    class FakeRuntime:
        def __init__(self, session_log):
            self.session_log = session_log

        async def run(self, task):
            JsonlConversationStore(self.session_log).append(Message(role="user", content=task))
            return task

        async def aclose(self):
            pass

    class FakeTui:
        def __init__(self, runtime, **kwargs):
            self.runtime = runtime

        async def run_async(self):
            if self.runtime.session_log == old:
                await self.runtime.run("continued")

        async def shutdown_runtime(self):
            pass

    def create_runtime(self, options, **kwargs):
        chosen.append(options.session_log)
        return FakeRuntime(options.session_log)

    monkeypatch.setattr(PoolRuntimeFactory, "create_runtime", create_runtime)
    monkeypatch.setattr(inquirycraft.tui, "InquiryCraftTui", FakeTui)
    runner = CliRunner()
    args = ["--workspace", str(workspace), "--model-config", str(models)]
    tui = runner.invoke(build_tui_command(), [*args])
    agent = runner.invoke(main, ["agent", "run", *args, "hello"])
    iq_app = create_cli(runtime_factory=PoolRuntimeFactory(), model_config_default=models)
    standalone = runner.invoke(
        iq_app, ["run", *args, "independent"],
    )

    assert tui.exit_code == 0, tui.output
    assert agent.exit_code == 0, agent.output
    assert standalone.exit_code == 0, standalone.output
    assert len(chosen) == 3
    assert chosen[0].parent.parent == workspace / ".scienceflow" / "sessions"
    assert chosen[1].parent.parent == workspace / ".scienceflow" / "sessions"
    assert chosen[2].parent.parent == workspace / ".inquirycraft" / "sessions"
    listed = runner.invoke(build_tui_command(), [*args, "--resume"])
    assert listed.exit_code != 0 and "old" in listed.output
    agent_list = runner.invoke(main, ["agent", "sessions", "list", "--workspace", str(workspace)])
    assert agent_list.exit_code == 0 and "old" in agent_list.output
    top_list = runner.invoke(main, ["sessions", "list", "--workspace", str(workspace)])
    assert top_list.exit_code == 0 and top_list.output == agent_list.output
    assert "UTC" in top_list.output
    assert chosen[0].parent.name not in agent_list.output  # TUI exited before the first turn.
    assert chosen[1].parent.name in agent_list.output
    iq_list = runner.invoke(iq_app, ["sessions", "list", "--workspace", str(workspace)])
    assert iq_list.exit_code == 0 and chosen[2].parent.name in iq_list.output
    assert "old" not in iq_list.output
    resumed = runner.invoke(build_tui_command(), [*args, "--resume", "--session", "old"])
    assert resumed.exit_code == 0, resumed.output
    assert chosen[-1] == old
    agent_resumed = runner.invoke(
        main, ["agent", "run", *args, "--resume", "--session", "old", "agent continuation"]
    )
    assert agent_resumed.exit_code == 0, agent_resumed.output
    assert chosen[-1] == old
    no_task = runner.invoke(main, ["agent", "run", *args, "--resume", "--session", "old"])
    assert no_task.exit_code == 0 and "no turn ran" in no_task.output
    assert "scienceflow agent repl --resume --session ID" in no_task.output
    assert [message.content for message in JsonlConversationStore(old).load().messages] == [
        "earlier", "continued", "agent continuation"
    ]
    assert {item.id for item in SessionCatalog(workspace, ".scienceflow").list()} == {
        "old", chosen[1].parent.name
    }
    assert {item.id for item in SessionCatalog(workspace, ".inquirycraft").list()} == {
        chosen[2].parent.name
    }


def test_public_tui_has_resume_and_session_but_no_session_log():
    result = CliRunner().invoke(main, ["tui", "--help"])
    assert result.exit_code == 0, result.output
    assert "--resume" in result.output and "--session" in result.output
    assert "--session-log" not in result.output
    agent = CliRunner().invoke(main, ["agent", "--help"])
    assert agent.exit_code == 0, agent.output
    assert "run" in agent.output and "repl" in agent.output
    assert "tui" not in agent.output.split()
    agent_run = CliRunner().invoke(main, ["agent", "run", "--help"])
    assert agent_run.exit_code == 0, agent_run.output
    assert "--resume" in agent_run.output and "--session" in agent_run.output
    assert "--session-log" not in agent_run.output
    assert "sessions" in CliRunner().invoke(main, ["--help"]).output
    assert "chat" in CliRunner().invoke(main, ["resume", "--help"]).output.lower()
