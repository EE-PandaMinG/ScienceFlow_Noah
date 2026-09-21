# DeepCraft / ScienceFlow C2 Message 类型组迁移记录（2026-08-23）

## 1. 结论

C2 已完成。`Message/Role/Function/ToolCall` 已作为不可拆分的 Pydantic 类型组由 DeepCraft 自身
维护，ScienceFlow 继续只使用 `deepcraft.legacy` 公共兼容 API。Prompt、Tool schema、provider
payload、Memory JSON/JSONL 和 Workspace 合同均未改变。

## 2. 实现边界

- 权威 Message/Role：`deepcraft.legacy.message`；
- 权威 Function/ToolCall：`deepcraft.legacy.tool.calls`；
- `deepcraft_core.message` 与 `deepcraft_core.tool` 只做同对象兼容导出；
- 旧对象、mapping 和 attribute-based shape 可通过 `coerce_message`、`coerce_function`、
  `coerce_tool_call` 无损转入；
- 历史 Memory 本阶段仍负责持久化，但其 Pydantic Message identity 已指向 DeepCraft 权威对象，
  避免旧 MemoryRecord 拒绝新消息；
- ScienceFlow RunLoop、科研 Hook、Stage/Gate/Resource、日志和 Workspace 路径均未改动。

## 3. 确定性门禁

```bash
.venv/bin/python scripts/run_runtime_parity.py --suite full --jobs 4
.venv/bin/python scripts/run_runtime_parity.py --suite performance --jobs 1
```

结果：

- `context_diff_count=0`；
- `mechanism_diff_count=0`；
- `workspace_unregistered_diff_count=0`；
- `failed_cases=0`；
- 性能 median/P95 均在 C1 登记阈值内；
- ScienceFlow Tool Schema 仍为 5391 bytes，SHA256 仍为
  `cc0aa04ca49d9f72f2b3ceb87073758650a65427136698568e2421ebdc93635b`。

Message/Memory/ToolCall 定向矩阵为 `124 passed, 7 skipped`；C2 新 provider contract、依赖边界和
Tool Schema 定向补充为 `13 passed`。

## 4. 完整离线矩阵

阶段检查点运行一次完整离线矩阵：

```text
1668 passed, 3 skipped, 2 warnings in 197.53s
```

两个 warning 均是既有 removed prep config 的 DeprecationWarning，与本阶段无关。

## 5. 本机 vLLM 短任务

复用在线的本地 OpenAI-compatible `Qwen3.6-27B`，执行一次短 ScienceAgent Tool turn：

- 模型严格按 `write -> read -> final` 执行；
- 最终回答 `C2_MESSAGE_OK`；
- `c2-message.txt` 精确为 `deepcraft-c2-ok\n`；
- Memory role 顺序为 `user, assistant, tool, assistant, tool, assistant`；
- 所有 Memory message 的实际模块均为 `deepcraft.legacy.message`；
- `.logs/interaction.log` 和 `.logs/tool_outputs/index.txt` 均生成。

临时 Workspace：`/tmp/scienceflow_c2_message_smoke_x5xjhsqc`。本阶段未重复运行 Circle Packing，
因为这是类型归属迁移，真实长任务留在 C7 最终效果门禁。

## 6. 下一边界

C3 将迁移 Memory/MemoryRecord/ContextRecord/Storage。必须继续原地读取 C1 旧 Workspace，保持
JSON/JSONL 字节格式、坏行处理、bounded window、UUID、prefix repair 和 Resume 顺序完全一致。
