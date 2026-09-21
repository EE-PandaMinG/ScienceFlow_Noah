# DeepCraft Tool 整合记录（2026-08-23）

## 本阶段结论

本阶段把领域无关的 Tool 契约和 workspace 文件操作归入 DeepCraft，同时保持
ScienceFlow 科学任务的模型上下文与磁盘效果不变。ScienceFlow 继续保留原 Tool 名称、
Schema、Pydantic 配置、`ToolResult` 类型身份、资源策略和任务反馈文本。

`deepcraft/legacy_packages` 仍不能删除：旧 `BaseAgent` 的 Pydantic 字段要求 legacy
`ToolCollection` 的精确类型，Message、Memory、OnlineLLM 和 `ToolResult` 也仍由历史包
提供。定向测试曾验证仅替换为结构相同的新 Collection 会触发校验错误，因此该类型必须
与 BaseAgent/Memory 一起迁移，不能单独强换。

## 已归入 DeepCraft

- Tool 基础契约：context、result、collection、executor 和兼容的 `to_param()`。
- workspace 基础能力：路径沙箱、额外允许根目录、隐藏前缀、逻辑显示路径、原子写入、
  Python/JSON/YAML 语法检查和文件摘要。
- workspace Tool 实现：read、write、edit、grep、glob、ls 的实际操作函数。
- context 写入保护：识别 interaction log/chat memory 中的压缩占位符，避免被模型误写回文件。
- Bash 通用输出层第一部分：workspace/extra-root/python-env/host 路径稳定化、symlink target
  隐藏和 head/tail 截断。

ScienceFlow 中对应模块现在是 Schema/配置 facade 或兼容 re-export。领域相关的 Bash
资源分类、GPU 边界、LNR feedback、artifact heartbeat、`resource_wait` 和 SkillRegistry
仍留在 ScienceFlow。

workspace 能力统一位于 `deepcraft/src/deepcraft/tools/workspace/`：`paths.py` 管理路径与
原子写，`observe.py` 管理 read/glob/ls，`search.py` 管理 grep，`modify.py` 与 `edit.py`
管理写入和编辑，`write_safety.py` 管理上下文占位符保护。`deepcraft.tools` 继续 re-export
公开对象，因此调用方 import 与运行上下文不变。

## 科学上下文硬门禁

新增 `tests/test_scienceflow_tool_context_contract.py`，固定：

- Tool 顺序：`bash, write, edit, read, grep, glob, ls`；
- 完整 OpenAI Tool Schema 字节长度 5391；
- Schema SHA256：
  `cc0aa04ca49d9f72f2b3ceb87073758650a65427136698568e2421ebdc93635b`；
- write/read/ls/glob 的逐字反馈文本；
- `ToolResult.output/error/system` 语义；
- ScienceFlow 兼容路径与 DeepCraft 规范对象的身份一致性。

迁移期间还直接加载 Git HEAD 中的旧实现，对新旧 read/glob/ls 15 个案例、write 9 个
案例、edit 6 个案例，以及 Bash 路径清洗/截断案例做逐字比较，全部一致。grep 的命令、
错误和结果集合一致；多文件输出顺序由 ripgrep/文件系统决定，旧实现自身也不保证跨进程
顺序，因此没有新增排序行为。

## 规模与规范

| 范围 | 整合前 | 整合后 |
|---|---:|---:|
| `scienceflow/core/tools` | 9,518 行 | 7,342 行 |
| `deepcraft/src/deepcraft/tools` | 约 307 行 | 1,789 行 |
| ScienceFlow Tool facade 最大文件（不含 Bash 领域实现） | 316 行 | 243 行 |
| DeepCraft Tool 最大文件 | 106 行 | 297 行 |

DeepCraft 新文件继续满足单文件不超过 350 行、单函数不超过 120 行，Ruff 全绿。

## 验证结果

- 快速 DeepCraft/Tool/ScienceAgent 定向门禁：221 passed。
- 完整离线矩阵：1675 passed、3 skipped、2 个既有 deprecation warnings。
- 完整离线耗时：169.71 秒。
- 没有运行新的 vLLM/三 seed 实验；真实科学任务放在 ToolResult/BaseAgent 迁移完成后的
  行为检查点，避免纯工程步骤重复消耗实验时间。

## 下一迁移边界

1. Bash 的通用 subprocess 生命周期和输出 reducer 已在后续 Runtime 收口阶段下沉，SF 只
   保留资源/GPU hook 与兼容出口。
2. 下一步同时迁移 `ToolResult`、`ToolCollection` 和旧 BaseAgent 字段，保持 `system` 原始输出不进入
   模型上下文但继续写入 tool artifact。
3. 再迁移 Message/Memory/OnlineLLM，并固定 short-term JSON、conversation JSONL、interaction
   log 和 workspace 路径合同。
4. 完成后删除 `legacy_packages`、路径注入和 `deepcraft[legacy]`，再运行 Circle Packing 三
   seed 与 DeepCraft CLI 实际任务门禁。
