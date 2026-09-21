# DeepCraft / ScienceFlow C4 LLM / Streaming Adapter 记录（2026-08-23）

## 1. 结论

C4 已完成。ScienceFlow `_build_llm()` 默认直接构造
`deepcraft.llm.legacy_compat.OpenAICompatibleLegacyClient`，不再直接实例化
`deepcraft_core.OnlineLLM`。Pooled endpoint 也通过 `deepcraft.legacy.OnlineLLM` 获得同一个正式
adapter 类型，原有 monkeypatch 和回滚入口继续可用。

## 2. 零行为变化策略

为保持既有 request/stream 行为，正式 adapter 在回退窗口内继承历史 OpenAI-compatible 实现：

- system message coalescing；
- model、temperature、top_p、max_tokens、frequency_penalty、seed 和 timeout；
- text、reasoning、ToolCall argument streaming；
- StreamHandle queue、stop、interrupt 和 EOS；
- empty stream retry、provider error、pool failover 和 cooldown；
- tokens、cached tokens、TTFT、TPOT 和 finish reason；
- OpenAI SDK 与共享 httpx client close。

没有把 500/1500 行历史实现直接搬入正式源码，也没有放宽 350 行规范门禁。大实现的后续模块化
已记录为 `OBS-010`，在 C8 使用 replay 单独处理。

## 3. 门禁结果

```bash
.venv/bin/python scripts/run_runtime_parity.py --suite full --jobs 4
.venv/bin/python scripts/run_runtime_parity.py --suite performance --jobs 1
.venv/bin/pytest -q deepcraft/tests deepcraft/legacy_packages/core/tests
.venv/bin/pytest -q tests/test_deepcraft_dependency_boundary.py \
  tests/test_llm_system_message_compat.py tests/test_reasoning_stream_guard.py \
  tests/test_llm_usage.py deepcraft/legacy_packages/core/tests
```

结果：

- Runtime Parity Context/Mechanism/Workspace 差异全部为 0；
- performance median/P95 在 C1 阈值内；
- DeepCraft 与历史 LLM contract：`132 passed`；
- ScienceFlow consumer 与 streaming contract：`40 passed`；
- DeepCraft 正式源码文件 ≤350 行、函数 ≤120 行门禁继续通过；
- Tool Schema、Memory 和 Workspace baseline 未改变。

根项目完整矩阵首次收集到 2 个 factory monkeypatch 兼容失败：历史测试会替换
`scienceflow.core.agent_runtime.OnlineLLM`。最终实现保留该同名扩展点，但值改为正式 adapter；失败
定向复验 `9 passed`，随后完整 last-failed 集合为空。其余根项目结果保持
`1668 passed, 3 skipped, 2` 个既有 DeprecationWarning。

## 4. 本机 vLLM smoke

复用本地 `Qwen3.6-27B`，在最终 adapter 结构上一次覆盖四个行为：

- 纯文本精确返回 `C4_FINAL_OK`；
- 单 ToolCall 为 `c4_probe({"value":"stable"})`；
- streaming 收到首 chunk 后主动 interrupt，任务正常结束；
- OpenAI SDK client 完成 `aclose`，closed 状态为 true；
- 实际实例模块为 `deepcraft.llm.legacy_compat.adapter`。

本阶段没有运行 Circle Packing 长任务；provider 的短真实行为与 deterministic full replay 均已通过。

## 5. 下一边界

C5 为 ScienceAgent 双 Runtime backend。legacy backend 继续作为回滚路径；deepcraft backend 必须用同一
recording 逐轮比较 provider payload、ToolCall、Memory、Hook/Stage/Resource 顺序和 Workspace，不能
只比较最终答案。
