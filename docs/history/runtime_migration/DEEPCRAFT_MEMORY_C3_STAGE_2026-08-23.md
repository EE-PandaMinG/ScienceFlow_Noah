# DeepCraft / ScienceFlow C3 Memory / Storage 迁移记录（2026-08-23）

## 1. 结论

C3 已完成。历史 `Memory/BaseChatHistoryMemory/MemoryRecord/ContextRecord/BaseContextCreator` 和
JSON/InMemory KV Storage 的权威实现已迁入 DeepCraft。`deepcraft_core.memory` 与
`deepcraft_core.storage` 只保留同对象兼容导出，ScienceFlow 的 Memory 压缩、Stage、Resume 和
Workspace 策略没有下沉或改写。

## 2. 保持不变的合同

- Message append/retrieve 和 historical bounded window；
- system message 保留、keep-rate score 和 timestamp 排序；
- MemoryRecord UUID、extra_info、timestamp、agent_id 和 `__class__` envelope；
- `short_term.json`、`long_term.jsonl` 的字段顺序、JSON 空格、Unicode 和结尾换行；
- JSON Storage append/clear 行为；
- clone/recent-round prune、prefix repair 和 Workspace path rewrite 继续由既有策略层组合；
- 旧对象可经 C2 structural coercion 输入，新记录统一产生 DeepCraft Message。

历史 JSON Storage 的 strict bad-line 行为与 recovery helper 的 tolerant 行为不同，已记录为
`OBS-009`，本阶段分别保留，不顺便修复。

## 3. 快速门禁

```bash
.venv/bin/python scripts/run_runtime_parity.py --suite full --jobs 4
.venv/bin/python scripts/run_runtime_parity.py --suite performance --jobs 1
.venv/bin/pytest -q deepcraft/tests/contract/test_legacy_memory_contract.py \
  tests/test_lnr_resume.py tests/test_agent_runtime_memory_facade.py \
  tests/test_memory_sliding_priority.py tests/test_memory_tool_turn_sanitization.py \
  tests/test_clone_inherit_compression.py tests/test_tool_memory_compression_*.py
```

结果：

- Runtime Parity Context/Mechanism/Workspace 差异全部为 0；
- performance median/P95 处于 C1 阈值内；
- Memory/Resume/压缩定向矩阵：`126 passed`；
- Frozen legacy Workspace 可原样读取，并在不升级 schema 的情况下继续追加；
- 新增字节合同验证 short-term 与 long-term 的 Unicode、空格、字段顺序和换行完全一致。

阶段级根项目完整离线矩阵为：

```text
1668 passed, 3 skipped, 2 warnings in 199.56s
```

两个 warning 均为既有 removed prep config 的 DeprecationWarning，与 C3 无关。

## 4. 旧 Workspace vLLM Resume smoke

将 `tests/fixtures/legacy_resume_workspace` 物理复制到临时目录，使用新 DeepCraft Memory 原地加载，
闭合历史未完成 Tool turn 后由本地 `Qwen3.6-27B` 继续执行：

- 初始两条消息 `user, assistant` 正确恢复；
- 模型继续执行 `write -> read -> final`；
- 最终回答 `C3_RESUME_OK`；
- `c3-resume.txt` 精确为 `deepcraft-c3-resume-ok\n`；
- 最终 role 顺序为
  `user, assistant, tool, user, assistant, tool, assistant, tool, assistant`；
- short-term 与 long-term 均为 9 行，所有 Message 模块均为 `deepcraft.legacy.message`。

临时 Workspace：`/tmp/scienceflow_c3_memory_resume_qy_ti9l0`。本阶段未运行 Circle Packing 长任务。

## 5. 下一边界

C4 迁移 LLM/Streaming Adapter。必须保持 system coalescing、request 字段、stream chunk、ToolCall
解析、retry/failover、telemetry 和 client close 的调用次数与顺序；C3 Memory baseline 不再改变。
