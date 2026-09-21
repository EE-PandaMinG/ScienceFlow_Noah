# Runtime Parity Baseline v2 阶段记录（2026-08-23）

## 结论

`baseline_v2` 已把原 full suite 的机制覆盖缺口变成独立 benchmark case。该阶段只增加确定性
捕获与门禁，没有修改 ScienceFlow 生产 Prompt、Tool schema、运行策略或 Workspace 格式。

## 新增合同

- `worker2_estra_merge`：两个独立 worker Workspace、两个 ESTRA join packet、候选/worker result
  顺序、Global Merge executor 输入、manifest、3 个 final 和最终 Workspace；
- `snapshot_stop_resume_recovery`：snapshot 捕获、运行失败、Workspace 恢复、`.logs` 保留、同一
  Hosted Runtime 继续、预取消人工停止、lifecycle 与 Runtime Event JSONL。

外部 LLM 和 evaluator 被替换为确定性 executor，但 ESTRA、Merge、Snapshot 和 Runtime 均调用生产
实现。所有未知 Context、Mechanism 或 Workspace 差异仍直接失败。

## 冻结信息

- 实现提交：`6821ab7e73fe058c9b6f5e57834aab12641f5b0a`；
- Python：`3.12.13`；
- `uv.lock` SHA256：`1facabdd0649f4751f3a2df6e5e45d28974ae3da9d4946f72979b65f8582e0bd`；
- 历史 `baseline_v1` 未修改；新增捕获位于 `baseline_v2/captures`；
- baseline 生成和迁移实现保持为不同 Git 提交。

## 验证

```bash
.venv/bin/python scripts/run_runtime_parity.py --suite quick --jobs 4
.venv/bin/python scripts/run_runtime_parity.py --suite full --jobs 4
.venv/bin/python scripts/run_runtime_parity.py --suite performance --jobs 1
.venv/bin/pytest -q tests/test_runtime_parity_benchmark.py
```

结果：quick/full/performance 的 Context、Mechanism、Workspace 和 failed case 计数均为 0；pytest
`5 passed`。两个新增 Case 在不同等长临时根目录连续运行两次，strict diff 均为 0。

功能门禁使用 4 进程，当前 quick/full 单次约 2 秒；性能门禁继续单独串行，避免调度噪声。
