# DeepCraft BaseAgent 迁移阶段记录（2026-08-23）

## 阶段结论

ScienceFlow 使用的 Pydantic `BaseAgent` 与 `AgentState` 已改由 DeepCraft 自身维护，不再要求
默认安装独立的 `deepcraft-agent` distribution。此次迁移只替换兼容基类的实现归属，没有
切换 ScienceFlow 主 RunLoop，也没有替换现有 `Message`、`Memory`、`ToolResult` 或
`ToolCollection` 对象，因此模型上下文和 Workspace 文件合同不变。

`deepcraft-agent` 暂未从仓库物理删除：保留的 MCPReAct compatibility 仍依赖它，故它只存在
于 `deepcraft[mcp]` optional extra。ScienceFlow 的 `deepcraft[legacy]` 和弃用别名
`deepcraft[scienceflow]` 现在只安装 `deepcraft-core[online]`。

## 实现变化

- `deepcraft.legacy.agent.BaseAgent` 成为 DeepCraft 内部权威实现。
- BaseAgent 保留历史 19 个 Pydantic 字段、字段顺序、默认值、`extra="allow"`、Memory 更新、
  one-step run、tool execution 和已移除 vector retrieval 配置行为。
- `AgentState` 提升为正式 `deepcraft.runtime.AgentState` 契约；旧
  `deepcraft.legacy.agent.state` 只做 re-export。
- ScienceFlow run-loop 直接从 `deepcraft.runtime` 使用 `AgentState`。
- `uv.lock` 已更新；`deepcraft-agent` 只在 MCP extra 中出现。

## 不变合同

新旧 BaseAgent 的以下内容已逐项比较一致：

- 字段名称与顺序；
- 所有字段默认值；
- ToolChoice 与 state 运行时值；
- 任意额外构造参数的保存语义；
- user/assistant Memory 追加顺序；
- LLM chunk queue 的 run 后重置行为；
- vector retrieval 默认关闭及显式启用时的失败语义。

ScienceAgent 仍使用 legacy `Memory`、`Message`、`ToolResult`、`ToolCollection` 和
`OnlineLLM`，避免在一个阶段同时改变多个上下文变量。

## 验证

- BaseAgent、ScienceAgent、Memory、Tool、stream/retry、clone/resume 和 LHR 定向矩阵：
  `586 passed`。
- 完整离线矩阵：`1762 passed, 3 skipped, 2 warnings in 183.21s`。
- DeepCraft 单向依赖、minimal extras、文件/函数规模、Ruff、compileall 和 diff-check 门禁通过。
- Tool Schema/context SHA256 继续保持
  `cc0aa04ca49d9f72f2b3ceb87073758650a65427136698568e2421ebdc93635b`。

## vLLM 实际任务

本机 `Qwen3.6-27B` 上执行短 ScienceFlow 任务：

- 新 BaseAgent 模块为 `deepcraft.legacy.agent.base`，`ScienceAgent` 实例继承关系正确；
- 模型按 `write -> read -> final` 执行；
- 最终回答为 `BASEAGENT_OK`；
- `baseagent.txt` 精确为 `deepcraft-baseagent-ok\n`；
- Memory role 顺序为 `user, assistant, tool, assistant, tool, assistant`；
- `.logs/interaction.log` 与 `.logs/tool_outputs/index.txt` 均正常生成。

临时 Workspace：`/tmp/scienceflow_baseagent_smoke_2csdxw4z`。

## 下一阶段

1. 设计 legacy/formal `Message` 与 `ToolResult` 的无损边界，先固定 model dump、tool-call JSON、
   `system` raw artifact 和 Memory JSON/JSONL golden。
2. 将 ScienceFlow `ToolCollection` 的 model-facing schema facade 与底层 executor 分离，保持
   Schema 字节完全一致。
3. Message/Memory/ToolResult/ToolCollection 一组完成后，再提供主 RunLoop 双 backend replay；
   未通过 replay 前不删除 `deepcraft-core`。
4. 将 MCP client adapter 迁入正式 DeepCraft MCP extra 后，才能物理删除
   `legacy_packages/agent`。
