# DeepCraft Tool 兼容合同迁移阶段记录（2026-08-23）

## 阶段结论

ScienceFlow 主 Agent 使用的历史 `ToolResult`、`ToolCollection`、compatibility `BaseTool`
和 `ToolChoice` 已由 DeepCraft 自身维护，不再从 `deepcraft_core.tool` 获取实现。此次工作是
实现归属迁移，没有切换 ScienceFlow RunLoop，没有改变工具 schema、工具反馈文本、Memory
消息内容或 Workspace 文件布局。

ScienceFlow 的具体工具基类此前已接入正式 `deepcraft.tools.BaseTool`；本阶段内置的
compatibility `BaseTool` 用于保持旧 DeepCraft API，而 ScienceFlow 仍保留自己的 Pydantic
schema facade。

## 实现变化

- 新增 `deepcraft.legacy.tool.result`，内置历史 Pydantic `ToolResult`、`CLIResult`、
  `ToolFailure` 和 `ToolError` 合同。
- 新增 `deepcraft.legacy.tool.collection`，保持 tuple 顺序、`tool_map`、动态增添工具、顺序执行
  和 `ToolError -> ToolFailure` 行为。
- `deepcraft.legacy.tool.base` 内置 compatibility `BaseTool` 与 `ToolChoice`。
- `deepcraft.legacy.agent.BaseAgent.availableTools` 改为 DeepCraft 自有 ToolCollection 类型。
- ScienceFlow 的七个 tool-exec/recovery 边界统一使用 `coerce_tool_result`；历史
  `deepcraft_core.ToolResult` 或第三方同形对象会逐字段迁移 `output/error/system`，不会退化为
  `str(object)`。
- 三份本地历史 Circle Packing launcher baseline 日志加入项目 `.gitignore`；分析报告继续由
  `docs/history/runtime_migration/` 中的版本化记录承担。

## 上下文不变合同

以下合同在迁移前后保持一致：

- `ToolResult` 字段顺序、默认值、Pydantic `model_dump()`、布尔值、错误渲染和 `replace()`；
- `output/error/system` 三元组，其中 `system` 继续作为 lossless raw artifact，不注入模型文本；
- ToolCollection 的工具顺序和 model-facing `to_params()` 输出；
- ScienceFlow 工具 schema 编码长度 `5391`，SHA256
  `cc0aa04ca49d9f72f2b3ceb87073758650a65427136698568e2421ebdc93635b`；
- write/read/ls/glob 的反馈文本与 Workspace 相对路径；
- Memory 中 `user -> assistant -> tool` 消息结构和 `.logs/tool_outputs` 文件布局。

## ToolCall / Message 边界

`Function` 和 `ToolCall` 本阶段有意保留原对象身份。定向门禁证明：历史 `Message.tool_calls`
的 Pydantic 字段绑定原 `ToolCall` 类；只迁移 ToolCall 而不迁移 Message 会造成同结构异类的
校验失败。因而二者必须在 Message/Memory 阶段一起迁移，并先建立 JSON/JSONL golden。

当前 DeepCraft Tool compatibility 层对 `deepcraft_core.tool` 只剩这两个明确的 Message 绑定
类型，不再依赖旧 ToolResult、ToolCollection、BaseTool 或 ToolChoice 实现。

## 验证

- ToolResult、Tool guard、edit/read guard 首批兼容门禁：`41 passed`。
- ToolCall/Memory/clone/resume/write-nudge 定向矩阵：`127 passed`。
- Tool schema、Workspace feedback、CLI、stream/retry 与消息清洗矩阵：
  `42 passed, 7 skipped`。
- 完整离线矩阵：`1664 passed, 3 skipped in 201.99s`。
- `compileall`、`git diff --check` 与 Ruff 门禁通过。

## vLLM 实际验证

本机 `.env` 配置的 `Qwen3.6-27B` 上执行短 ScienceFlow Agent 任务：

- 模型按 `write -> read -> final` 执行；
- 最终回答为 `TOOL_CONTRACT_OK`；
- `tool-contract.txt` 精确为 `deepcraft-tool-contract-ok\n`；
- Memory role 顺序为 `user, assistant, tool, assistant, tool, assistant`；
- `.logs/interaction.log` 与 `.logs/tool_outputs/index.txt` 均正常生成。

成功验证 Workspace：`/tmp/scienceflow_tool_contract_smoke_520fu9e8`。

## 下一阶段建议

1. 固定 Message、ToolCall、Memory short-term JSON 与 long-term JSONL 的逐字节 golden。
2. 将 `Message + Function + ToolCall` 作为一个原子类型组迁移，禁止拆开替换对象身份。
3. 再内置 Memory storage/context creator，并对旧 Workspace 做原地读取和续跑 replay。
4. 完成 replay 前保留 `deepcraft-core`；MCP compatibility 继续作为 optional extra 独立处理。
