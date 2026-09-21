# DeepCraft Agent Runtime 通用机制收口记录（2026-08-23）

## 阶段结论

本阶段继续按“DeepCraft 负责通用 Agent Runtime，ScienceFlow 只保留科学任务策略与兼容
出口”的边界整理代码。迁移没有修改 ScienceFlow 的 Prompt、Tool Schema、ToolResult 文本、
消息追加顺序、Workspace 路径或 JSON/JSONL 格式。

ScienceFlow 主 RunLoop 尚未切换到新的 `AgentRuntime`，`legacy_packages` 也尚未删除。这是刻意
保留的兼容边界：现有 `ScienceAgent` 仍依赖 legacy Pydantic `BaseAgent`、`Memory`、`Message`、
`ToolCollection` 和 `ToolResult` 的对象身份。没有在缺少完整 deterministic backend replay 的
情况下强制换类型。

## 本阶段归入 DeepCraft 的能力

- `deepcraft.tools.dispatch`：Tool bundle 分类和保持输入顺序的并发执行。ScienceFlow 注入
  read-only/mutation 集合与 Bash 安全判断，日志、budget、memory 和 result.md 策略仍在上层。
- `deepcraft.runtime.streaming`：逐 channel 输出软上限与重复检测。隐藏 reasoning 和可见
  content 继续分别计数，ScienceFlow 保留中断反馈和 interaction log 写入时机。
- `deepcraft.runtime.telemetry`：统一抽取 tokens、TTFT、TPOT、endpoint pool 与 failover 指标，
  ScienceFlow 保留原 `on_llm_call` hook 和字段顺序。
- `deepcraft.runtime.subprocess` / `subprocess_sync`：进程组隔离、live PGID registry、异步/同步
  spawn、SIGTERM/SIGKILL tree cleanup 和 SIGUSR1 可恢复停止。
- `deepcraft.tools.shell_reducer` / `shell_traceback`：重复 block 折叠、lossless observation
  head/tail、masked traceback 检测和 Python traceback 精简。

ScienceFlow 的生产调用均直接指向上述 DeepCraft 模块。以下旧路径只保留兼容 re-export，
并与 DeepCraft 对象保持 identity：

- `scienceflow.core.subprocess_utils`
- `scienceflow.core.tools.bash.output`

## 仍留在 ScienceFlow 的内容

- `ScienceAgent` 的科学任务 run policy、LNR、result.md、embedded full-run、budget expansion、
  resource feedback memory 和 workspace interaction log 策略。
- Bash 的资源分类、GPU lease/admission、artifact heartbeat、resource arbiter、deadline/fuse 与
  workspace GPU cleanup。
- 现有 Tool 名称、Pydantic Schema、反馈文本和 compatibility `ToolCollection`。

这些内容直接影响科学任务效果或当前 Workspace 合同，不能仅因目录名为 `agent/`、`tools/`
就机械删除。下一阶段应同时迁移 legacy BaseAgent/Message/Memory/ToolResult 类型并运行 backend
replay，之后才能删除这些兼容入口。

## 规模与代码规范

相对阶段起点 `644a2a2`：

| 范围 | 阶段前 | 阶段后 | 变化 |
|---|---:|---:|---:|
| `scienceflow/core/agent` | 11,717 行 | 11,627 行 | -90 |
| `scienceflow/core/tools` | 7,342 行 | 6,957 行 | -385 |
| `scienceflow/core/subprocess_utils.py` | 411 行 | 30 行 | -381 |
| `deepcraft/src/deepcraft` | 5,159 行 | 6,292 行 | +1,133（权威实现与新 runtime 机制） |

DeepCraft 的正式源码继续满足单文件不超过 350 行、单函数不超过 120 行的 contract；新增
subprocess 和 reducer 在迁移后按职责拆分，最大文件为 306 行。

## 上下文与行为验证

- 完整离线矩阵：`1756 passed, 3 skipped, 2 warnings in 192.82s`。两个 warning 均为既有的
  removed prep config deprecation。
- Tool context contract：顺序仍为 `bash, write, edit, read, grep, glob, ls`，序列化长度仍为
  5391 bytes，SHA256 仍为
  `cc0aa04ca49d9f72f2b3ceb87073758650a65427136698568e2421ebdc93635b`。
- DeepCraft/SF 兼容 identity、文件大小、依赖单向性、Ruff、compileall 和 `git diff --check`
  门禁通过。
- 新增 DeepCraft CLI 多轮 REPL 自动测试，验证两轮输入复用同一 runtime 且退出时调用
  `aclose()`。

## 本机 vLLM 实际 smoke

本阶段没有重复运行 Circle Packing 三 seed，因为本次是纯工程归属迁移，且此前基线已经
保存。使用仍在线的 `Qwen3.6-27B` vLLM 做了两个短行为检查：

1. ScienceFlow `ScienceAgent`：模型按 `write -> read -> final` 执行，最终回答 `DONE`，
   `smoke.txt` 精确为 `deepcraft-sf-ok\n`；Memory role 顺序为
   `user, assistant, tool, assistant, tool, assistant`。Workspace 仍生成
   `.logs/interaction.log`、`.logs/traj_interaction.log`、`.logs/tool_outputs/index.txt` 和逐工具
   artifact。
2. DeepCraft CLI REPL：输入一轮后精确返回 `DEEPCRAFT_CLI_OK`；`session.jsonl` 为 3 行，
   role 顺序 `system,user,assistant`；`events.jsonl` 为 8 行，从 `session.started` 到
   `session.completed` 完整闭合。

临时结果分别保存在 `/tmp/scienceflow_runtime_smoke_kyo2aqje` 和
`/tmp/deepcraft_cli_smoke_048Uv5hx`。

## 下一删除条件

1. 为现有 ScienceAgent 建立 legacy/deepcraft 双 backend，并使用同一 LLM recording 比较逐轮
   request、tool call、Memory 和 Workspace manifest。
2. 同时迁移 BaseAgent 字段、Message/Memory/ToolResult/ToolCollection 对象身份，不做单类型
   强换。
3. 通过非 Circle Packing 代表任务、Circle Packing 三 seed、worker=2、Resume 和性能门禁。
4. 默认 backend 切换并保留一个发布周期的回退开关后，再删除 `legacy_packages` 和 SF 兼容
   re-export。
