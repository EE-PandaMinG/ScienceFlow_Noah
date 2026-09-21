# Circle Packing 三 Seed 配对效果门禁

## 对比边界

- Baseline：`46e3c61`，另在验证分支仅回移相同门禁基础设施，验证 HEAD 为 `a826385`。
- 优化后：`7872bcb`。
- 模型：同一个本地 OpenAI-compatible vLLM `Qwen3.6-27B`。
- Seed：`2222`、`3333`、`4444`；每个 seed 均为 `worker=2`。
- 六个任务同时运行，共 12 个 Agent worker。
- Baseline 使用物理 CPU `0-47`，优化后使用物理 CPU `56-103`；两边各占一个 NUMA socket 的 48 个物理核。
- 门禁向 Agent 暴露相同的逻辑 CPU 编号，实际 taskset 隔离不变。
- 每任务上限 1200 秒，LNR 预算 900 秒，worker 预算约 600 秒。
- Evaluator 为 Circle Packing task package；指标 `radii_sum`，越高越好。

首次有效启动前有两批不计入样本的启动检查：第一批发现项目 `.venv` 的 `jiter` 二进制为 0 字节，修复包缓存后 OpenAI smoke test 通过；第二批发现物理 CPU 编号进入首条 Prompt，随即停止并增加逻辑 CPU 规范化。两批均未进入最终评估，最终结果全部来自全新的 `retry2` workspace。

## Provider 输入对齐

最终启动后，三组 seed 的 W00/W01 首条 user message 在 Baseline 与优化后之间均 byte-for-byte 相同：W00 为 5281 字符，W01 为 5282 字符，六对 SHA256 全部匹配。

首轮之后，共享 vLLM 的并发调度仍会造成部分生成分叉：seed 3333 的 W00/W01 和 seed 4444 的 W01 在检查时保持完整消息前缀一致；其他 worker 在相同首条请求后于不同轮次分叉。因此本报告使用预先登记的三 seed 配对统计门禁，不把单次轨迹等同于严格 deterministic replay。

## 最终结果

| Seed | Baseline `radii_sum` | 优化后 `radii_sum` | 相对变化 | Baseline 耗时 | 优化后耗时 | 耗时变化 |
|---:|---:|---:|---:|---:|---:|---:|
| 2222 | 2.1106639153 | 2.4784410491 | +17.425% | 987.6 s | 1004.0 s | +1.661% |
| 3333 | 1.8200000000 | 1.8200000000 | 0.000% | 834.3 s | 878.0 s | +5.238% |
| 4444 | 2.0154003333 | 2.0438852729 | +1.413% | 953.5 s | 869.8 s | -8.778% |

汇总：

- 分数：优化后 2 胜 1 平，没有 seed 回退。
- 中位分数：`2.0154003333 -> 2.0438852729`，提升 1.413%。
- 平均分数：`1.9820214162 -> 2.1141087740`，提升 6.664%。
- 最差 seed：两边均为 `1.8200000000`，没有回退。
- 中位耗时：`953.5s -> 878.0s`，降低 7.918%。
- 平均耗时：`925.13s -> 917.27s`，降低 0.850%。
- 每个 seed 的耗时回归均小于预设 10% 上限。
- 六个任务均 `completed`、exit code 0，final evaluator 均 valid 且 selection eligible。
- 任务结束后又直接调用 `tasks/opt_solver/circle-packing/evaluator.py` 独立复验六个 `final_00` artifact；六次均 exit code 0、`valid: true`，分数与 merge `eval_result.json` 完全一致。

自动报告：`three_seed_effect_gate_report_20260822.json`，判定为 `passed: true`，`failures: []`。

## 配置与 Workspace 契约

三组 `resolved_config.yaml` 逐 seed 比较时，仅 `config_source_path` 的绝对 worktree 前缀不同；规范化 workspace/input/config-source 路径后，其余配置一致。

为六个最终 workspace 捕获完整 Manifest，并以 Baseline 为 expected、优化后为 actual 执行 compatible gate：

| Seed | Baseline entries | 优化后 entries | 固定路径契约 | Missing | Mismatch | 结论 |
|---:|---:|---:|---:|---:|---:|---|
| 2222 | 398 | 486 | 193 | 0 | 0 | compatible |
| 3333 | 389 | 388 | 193 | 0 | 0 | compatible |
| 4444 | 391 | 383 | 193 | 0 | 0 | compatible |

seed 2222 优化后多出 `final_01` 等 11 个附加路径，因为该轨迹产生两个有效 final；compatible gate 允许新增能力产物，但没有缺失或改变任何 Baseline 固定路径、kind/mode、symlink 或结构化 shape 契约。

## 门禁结论

Circle Packing 三 seed / worker=2 真实效果门禁为 **PASSED**。在本次并行同服务、同预算、同任务的配对验证中，优化后代码没有功能、最终指标、有效性、Workspace 文件契约或工程耗时退化。

该结论允许继续下一阶段迁移验证，但不单独授权删除 legacy Runtime：默认 Runtime 切换仍需 deterministic replay、其他代表任务、Resume 和完整测试矩阵共同通过。
