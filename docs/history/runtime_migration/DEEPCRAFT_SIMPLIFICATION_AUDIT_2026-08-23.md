# DeepCraft 精简与代码规范审计（2026-08-23）

## 结论

DeepCraft 正式 Runtime 的问题不是总代码量失控，而是少数函数职责过长、CLI 命令注册
集中、兼容 shim 写法不统一，以及没有固定静态规范。历史包则确实包含大量 ScienceFlow
和 MCP 均不可达的集成源码。

本阶段保持 ScienceFlow 的 Prompt、Tool Schema、Memory JSON/JSONL、workspace 路径和
运行策略不变，只整理通用 Runtime 和不可达历史能力。

## 规模变化

| 范围 | 整理前 | 整理后 | 说明 |
|---|---:|---:|---|
| `src/deepcraft` Python 行数 | 3,489 | 3,631 | 提取职责、显式 shim 和规模门禁增加少量结构行 |
| 正式/兼容区最大文件 | 308 行 | 344 行 | 低于新增的 350 行合同上限 |
| 正式/兼容区最大函数 | 127 行 | 56 行 | Runtime、pool、CLI 均已拆分 |
| `legacy_packages` Python 行数 | 9,341 | 6,310 | 减少 3,031 行，约 32% |
| Git 总变化 | — | 净删除超过 5,000 行 | 包含集成源码、资源和结构/规范调整 |

文件行数不是越少越好。`runtime/engine.py` 和 legacy pool 在拆函数后文件略长，但每个
职责可独立测试；继续强拆成更多微型文件只会增加跳转和 import 复杂度。因此门禁采用
“单文件 350、单函数 120”，并把函数复杂度控制在 Ruff C901 默认阈值内。

## 已精简的热点

- Runtime：把主循环拆成 completion request、provider 调用、单轮执行、session 启动、
  pending tool resume 等独立步骤；事件顺序和 hook 顺序由 replay/runtime 测试锁定。
- Legacy LLM pool：拆出 success state、rate-limit、soft retry、endpoint attempt 和等待
  策略，删除无意义的 `__setattr__`。
- CLI：`run`、`repl`、`tools`、`events` 分别注册，`create_cli` 只负责组装。
- Memory records：拆出 JSON value 与 JSONL row 解析，减少分支集中度。
- Compatibility shim：改为显式 re-export，旧路径与规范路径仍指向同一对象。

## 删除的不可达历史能力

生产路径和测试可达性审计确认下列代码不被 ScienceFlow 使用，也不属于要求保留的 MCP：

- `deepcraft_tool_ext` 整个旧 distribution，包括 Browser、WebSearch、代码执行和文件工具；
- LiteLLM client；
- Chroma/vector storage、sentence embedding 和完整向量检索实现；
- 依赖 tool-ext 的旧 CodeAct agent；
- 未暴露且无调用者的 Redis/Web API adapter；
- `full`、`litellm`、`retrieval`、`legacy-langchain`、`code` 等失效 extras。

为避免 ScienceFlow 的旧 `BaseAgent` Pydantic shape 漂移，vector retrieval 的禁用配置字段
仍由一个轻量 compatibility mixin 保留；启用已删除能力会明确报错，不再隐式加载重依赖。
保留能力为 OnlineLLM、Memory/Message/Tool 基类、BaseAgent/ReAct、通用 request、token
估算和 MCP。

## 代码规范

- `deepcraft[dev]` 增加 Ruff；固定 Python 3.11、100 字符行宽、import/unused/error 规则。
- `src/deepcraft` 与 `deepcraft/tests`：Ruff lint、format、C901 全绿。
- 合同测试自动拒绝超过 350 行的正式源码文件和超过 120 行的函数。
- 冻结的 `legacy_packages` 不做全文件机械格式化，避免大面积无行为价值的 diff。目前已
  消除 undefined name 和重复 method；剩余 49 项均为 import 顺序、历史 re-export、
  `== True/False` 和 import placement 等样式债务，不影响运行。

## 验证

- DeepCraft + retained legacy-core：90 passed。
- ScienceFlow 迁移相关定向套件：149 passed。
- OnlineLLM、Memory、Message、BaseAgent、ReAct、MCPReAct、MCP client 导入 smoke 通过。
- Ruff lint、format、C901、lock check 和 diff check 通过。

本阶段属于纯工程整理，沿用上一结构检查点已经完成的 Circle Packing 与 CLI 真实任务
门禁，不重复运行耗时的 vLLM 实验。
