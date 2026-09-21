# DeepCraft / ScienceFlow C1 Runtime Parity 阶段记录（2026-08-23）

## 1. 结论

C1 已完成。当前生产类型和 ScienceFlow 科研策略没有修改；本阶段只建立迁移前的确定性
Runtime Parity Benchmark，并从 Git `2bd63c18c7bf2b715cef8dcbb20cb173e3615b39` 冻结
`baseline_v1`。

日常工程门禁可使用 4 进程并行执行，当前墙钟约 2 秒；性能 Case 独立串行，避免并行调度噪声。

## 2. 固定合同

Benchmark 初版包含 8 个功能 Case；C7/C8 收口复核后，`baseline_v2` 已扩展为 10 个功能
Case 和 1 个性能 Case：

1. ScienceFlow 单轮文本响应；
2. ScienceFlow `write -> read -> final` Tool turn；
3. 同一 round 的 LLM 空流重试与停止；
4. DeepCraft 正式 Runtime Tool turn；
5. recorded LLM 严格 Resume；
6. readonly 并发、mutation 阻断顺序、Tool error 和 stream interrupt；
7. legacy Message/ToolCall/Memory、UUID 去重和 prefix repair；
8. Stage append-only、Gate accept/reject、GPU Resource plan 决策链；
9. worker=2 隔离、ESTRA join packet、Global Merge 与 3 个 final；
10. snapshot/restore、失败恢复、同 Runtime 继续和人工停止；
11. context build、Memory、Tool dispatch 和 event build 性能微门禁。

Workspace 日志、JSON/JSONL、事件和产物合同由每个功能 Case 的 Workspace section 共同覆盖。

每个功能 Case 分别严格比较：

- Context：Memory、provider 请求、Tool schema/arguments、最终响应；
- Mechanism：state/round/retry/dispatch/resume/interrupt/Stage/Gate/Resource 顺序与决定；
- Workspace：相对路径、文件类型、JSON/JSONL/text、日志和 artifact。

唯一允许的归一化字段由
`tests/fixtures/runtime_parity/normalization.yaml` 驱动。Runtime Event UUID 使用稳定 sequence
映射，但 `parent_event_id` 的关系仍严格比较；没有登记的字段或路径差异直接失败。

## 3. 验证结果

执行命令：

```bash
.venv/bin/python scripts/run_runtime_parity.py --suite quick --jobs 4
.venv/bin/python scripts/run_runtime_parity.py --suite full --jobs 4
.venv/bin/python scripts/run_runtime_parity.py --suite performance --jobs 1
.venv/bin/pytest -q tests/test_runtime_parity_benchmark.py
```

阶段结果：

- quick/full：`context_diff_count=0`、`mechanism_diff_count=0`、
  `workspace_unregistered_diff_count=0`、`failed_cases=0`；
- performance：所有 median/P95 均处于登记阈值内；
- Benchmark 自动测试：`5 passed`；其中 quick/full 均以 4 进程执行；
- baseline 只能由显式 `--record-baseline` 写入，要求干净工作树和 manifest commit 一致；
- 候选 Workspace 使用独立临时目录，普通运行不会修改 fixture。

## 4. 已知边界

- 原 `full` 与 `quick` 共享 Case 的覆盖缺口已在 `baseline_v2` 解决。新增 Case 调用真实
  ESTRA join、Global Merge、WorkspaceSnapshotStore 和 HostedAgentRuntime 边界，只替换外部 LLM/
  evaluator 为确定性 executor；没有用空壳断言代替机制验证。
- 本阶段没有连接 vLLM，也没有重复运行 Circle Packing；这是纯测试基础设施阶段，避免长实验消耗。
- Runtime Event 随机 UUID 已记录为 `OBS-008`，本阶段只在 comparator 中稳定映射，不改变生产格式。

## 5. 下一原子边界

下一阶段为 C2：在 DeepCraft 内部一次性迁移 `Message/Role/Function/ToolCall` 类型组。任何
provider payload、ToolCall identity、schema、Memory 文件或 Workspace 差异都会由 C1 门禁阻断。

## 6. Baseline v2 收口补充

- 实现提交：`6821ab7e73fe058c9b6f5e57834aab12641f5b0a`；
- baseline：`tests/fixtures/runtime_parity/baseline_v2`；`baseline_v1` 原样保留；
- 依赖锁 SHA256：`1facabdd0649f4751f3a2df6e5e45d28974ae3da9d4946f72979b65f8582e0bd`；
- 两个新增 Case 在独立、等长 Workspace 中连续捕获两次，strict diff 均为 0；
- 从冻结文件重新验证：quick/full/performance 均为 0 diff，pytest `5 passed`；
- full/quick 并行复验墙钟均约 2 秒，pytest 门禁约 4 秒，没有引入长实验开销。
