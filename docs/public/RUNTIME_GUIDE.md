# Runtime guide / 运行指南

[Quick start](../../README.md) · [中文快速开始](README_CN.md)

## Tasks, workspaces, and sessions

`scienceflow run [TARGET]` is the single command-line entry point for managed
research. `TARGET` may be a built-in task ID, a local task folder, or a new task
description:

The main `scienceflow --help` page shows everyday commands. Advanced commands
such as `scienceflow parallel` and `scienceflow monitor-trace` remain available
directly and have their own `--help` pages.

```bash
scienceflow run circle-packing --workspace "$PWD/sf_workspace"
scienceflow run "optimize a new packing problem" --workspace "$PWD/sf_workspace"
```

Keep chat sessions and the task board in the management workspace while placing
one task on another **local** disk:

```bash
scienceflow run circle-packing --workspace "$PWD/sf_workspace" --execution-root /data/experiments
```

In TUI use `/long-research circle-packing workspace=/data/experiments`, or describe
the execution directory in natural language. The explicit option needs no model
call to resolve its location. Natural-language location extraction runs without
tools before allocation; ambiguous requests can be retried with `workspace=...`.
Each explicit root gets a unique task subdirectory. Relative roots and input data
paths resolve against the management workspace; datasets are not copied. Without
an override the existing directory layout is unchanged. `--execution-root` cannot
be combined with `--manifest`. Cancel preparation and start a new task to change
its directory; resume always reuses the recorded directory. SSH execution is not
implemented in this phase. Preparation uses a separate runtime in the task
directory, with shell available without changing the chat session.
These host capabilities are included in the pinned InquiryCraft 0.9.2 dependency.

CLI and TUI starts and resumes share the same CPU/GPU reservation checks.
With `--manifest`, set workers, duration, CPU/GPU, data and configuration in the
manifest; combining it with those CLI options is rejected. The TUI detects
external starts/resumes through lightweight registry changes without rescanning
completed experiment directories.

On an interactive terminal, `scienceflow run` with no target lists built-in and
workspace-local tasks and includes a new-description option. In a pipe or other
non-interactive process, provide `TARGET` or `--manifest`; the command exits
immediately instead of prompting. The TUI uses the same catalog when
`/long-research` is entered without an argument.

<p align="justify">
Chat normally in the TUI, or enter <code>/long-research</code> to configure and launch a
managed task. Closing the TUI detaches from research without terminating its workers.
Research defaults to your selected chat model; use <code>/models</code> to switch.
Use <code>/compact</code> to condense Chat context without deleting saved records.
<code>scienceflow tui --resume</code> restores the latest workspace chat session and
its concise ScienceFlow activity timeline; <code>/resume N</code> resumes research
task N. Read-only slash queries remain visible now but are omitted from saved
ScienceFlow activity.
Ordinary chat receives a short snapshot of the task panel state for the current
request; this snapshot is not added to the saved conversation.
</p>

TUI chat and task preparation provide workspace-contained `read_text`, `write_text`,
and `workspace_info` (current directory, bounded listing and file metadata).
Shell is available by default and runs as your user with host/network access and
no OS sandbox. There is no default timeout. Use Esc to cancel the active chat or
exit TUI to stop foreground commands and their child processes. An explicit shell
timeout can be set up to 3600 seconds. Long-research workers retain their separate
execution controls.

## Task controls

| Command | Purpose |
| --- | --- |
| `/tasks`, `/status N` | List tasks or inspect one task. |
| `/stop N`, `/resume N`, `/attach N` | Stop, resume, or locate a task. |
| `/models` | Select the chat model. |
| `/web`, `/web stop` | Start or stop the Web monitor. |

## 本机工作目录

聊天和任务列表保留在启动工作区；单个任务可指定另一处**本机**执行根目录：

```bash
scienceflow run circle-packing --workspace "$PWD/sf_workspace" --execution-root /data/experiments
```

TUI 中输入 `/long-research circle-packing workspace=/data/experiments`，也可用自然语言
说明执行目录。显式参数不调用模型解析目录；自然语言先进行禁用工具的位置提取，再分配目录。
每次指定根目录都会创建独立任务子目录，不覆盖已有实验，不复制数据集。相对执行根目录、
相对数据路径均以管理工作区解释；不配置时保留现有默认目录布局。
`--execution-root` 不可与 `--manifest` 混用。准备后要换位置，请 `/cancel` 后重新发起任务；
恢复始终使用原目录。准备工具使用独立任务目录，shell 默认可用；普通聊天的目录和
session 不变。本阶段不支持 SSH；宿主接口由锁定的 InquiryCraft 0.9.2 提供。

## 运行注意

- MLE-bench 任务需要数据根、任务 `exp_id`、`submission.csv` contract 对齐。
- 不同任务 profile 的旧 workspace 不应混用 resume，否则可能继承错误 prompt、dataset 或 artifact 维度。
- CLI 与 TUI 的启动、恢复统一执行 CPU/GPU 资源预留检查。使用 `--manifest` 时，worker、时间、CPU/GPU、数据和配置在 manifest 中设置，混用对应 CLI 参数会明确报错。
- TUI 通过轻量注册表变更感知其他终端的启动和恢复，不重新扫描已结束实验目录。
- `stopped_by_user` 表示人为停止的可恢复终态，不等价于失败；后续 resume 应从 `state.json` 的累计预算和 workspace stage 继续。
- TUI 底部资源栏显示本机资源概况；任务卡和 `/status N` 展示任务及 worker 的资源与用量。
- `scienceflow tui --resume` 恢复本工作区聊天会话及简短研究事件；TUI 内 `/resume N` 恢复编号为 N 的研究任务。`/status` 等查询只即时显示，不写入研究事件历史。
- 普通聊天只在当前模型请求中读取任务面板的简短状态摘要，不把这份摘要写入聊天记录或影响研究 worker。

## 验证

```bash
.venv/bin/pytest -q \
  tests/test_inquirycraft_dependency_boundary.py \
  tests/test_inquirycraft_cli_composition.py \
  tests/test_long_research_interaction.py
```

发布 workflow 仅接受与项目版本一致的 tag；它会构建并检查 wheel 与源码包，在干净环境中
安装 wheel，运行公共依赖契约，再通过 PyPI Trusted Publishing 上传。完整回归命令为
`uv run --locked pytest -q`。ML、GPU、MLE-bench 与 scientific-design 测试需要对应的可选依赖。

TUI 聊天和任务准备默认可执行 shell（当前用户权限，无操作系统沙箱），无默认超时。
Esc 取消当前聊天，退出 TUI 回收前台命令及子进程；长程 worker 的执行控制保持独立。

### 任务收尾与报告

研究结束、失败或停止后，托管任务会进入独立的报告阶段，默认预算 300 秒，
不占研究预算；提前完成即结束。manifest 顶层 `report_budget_sec` 可设置该预算。
报告先生成本地证据版，再在剩余预算内补充模型分析。任务目录包含
`report.md`、`report.html`、`report.json` 和 `report_assets/`，各次运行归档位于
`task_logs/reports/attempt-NNN/`。Web 打开 HTML 后可通过浏览器打印保存 PDF，
不安装服务端 PDF 引擎。

报告生成失败时，对已结束的研究执行原有 `resume` 只重试报告，不重新探索、
不占用研究 CPU/GPU 配额；仍有研究预算的暂停任务继续原有恢复流程。报告发布使用
原子版本切换，中断时保留上一个完整版本；历史版本暂不自动清理。
