# DeepCraft Legacy Memory Store 迁移与 Stage-3 对比记录

日期：2026-08-22

## 结论

本阶段将历史 `short_term.json` / `long_term.jsonl` 的通用记录读取、写入、去重、prefix-safe 窗口修复和恢复窗口评分下沉到 `deepcraft.memory`。ScienceFlow 继续保留 L0 anchor、agentic-route 过滤和日志策略，原有函数入口改为兼容 facade。

该迁移切片通过确定性记录差分、旧 Workspace Resume、三 seed/Worker=2 Circle Packing 效果门禁、独立 evaluator、配置归一化、性能门禁和包含 `scientific-design` extra 的测试验证。它不等于完整 RunLoop 已迁移，也不授权删除旧 Runtime。

## 代码边界

基线：`d9b650b`（Stage-2 记录检查点）。

DeepCraft 新增：

- `read_legacy_records()`：兼容历史 JSONL、JSON list 和单对象文件，保持坏行跳过语义。
- `write_legacy_records()`：保持 compact JSON、一行一对象、UTF-8 和结尾换行格式。
- `dedupe_legacy_records()`：继续优先按 UUID 去重，无 UUID 时使用 canonical message。
- `repair_legacy_record_window()`：保留开头 task prefix，避免窗口以孤立 tool result 开始。
- `legacy_record_window_score()`：保持历史 short/long-term 恢复源评分。

ScienceFlow 特有的 Memory Policy 没有进入 DeepCraft，包括 L0 anchor、agentic route transient record 过滤、最近轮次裁剪和 workspace path hygiene。

## 自动化验证

### 聚焦测试

- DeepCraft Store/Resume、ScienceFlow Resume/Replay、clone inheritance、LNR 长时程回归组合：`255 passed`。
- 新增 DeepCraft 测试覆盖 compact JSONL 字节格式、JSON-list 兼容、坏行跳过、UUID 去重、task prefix 和 tool-call 边界。
- 同一份真实 47-row Memory 经旧实现和新实现选择后：row count 均为 47，序列化 SHA256 均为 `aae6f90a62c7a1cc14d83fba73702066f04d5ed87b9ebd08a44e9773b45b2e44`。

### Optional extra

按 `uv.lock` 安装 `scientific-design` 后，`tests/test_sci_modeling_bench.py` 为 `11 passed, 1 skipped`。此前未安装 extra 而排除的测试已纳入验证；依赖声明和 lockfile 没有修改。

### 完整矩阵

第一次完整运行结果为 `1691 passed, 3 skipped, 2 failed`。两个失败分别是 SIGUSR1 marker 的固定 0.2 秒启动竞态，以及资源队列语义测试把真实 Torch 冷启动计入 5 秒 Bash timeout；均不经过本次 Memory 代码。测试夹具随后改为显式 child-ready handshake，并保留 Torch 分类文本但不执行与队列断言无关的冷导入。两个用例连续 5 轮共 10 次断言通过，最终完整复跑为 `1693 passed, 3 skipped, 2 warnings`，耗时 `169.15s`。生产信号、队列和 Bash timeout 实现未放宽。

## Memory 热路径性能

样本为真实约 95 KB、47-row 的 ScienceAgent Memory；每组 50 次调用，重复 31 轮：

| 实现 | 中位耗时/50 次 | P95/50 次 | 中位单次 |
| --- | ---: | ---: | ---: |
| Legacy | 0.199017 s | 0.212311 s | 3980.347 µs |
| DeepCraft | 0.196277 s | 0.215146 s | 3925.533 µs |

中位耗时改善约 1.38%，P95 回退约 1.34%；两项均满足同机 2% 默认门限。

## Circle Packing 实验设计

为了避免 Stage-2 中 baseline/candidate 共 12 个 Agent worker 同时竞争同一 vLLM，本轮采用：

- baseline 和 candidate 分侧顺序运行；每侧内部仍同时运行 seed `2222/3333/4444`。
- 每个 seed 为 Worker=2，每侧共 6 个 Agent worker。
- 两侧复用物理 CPU `0-47`，消除不同 NUMA/CPU 集合影响。
- 两侧使用同一个 vLLM `Qwen3.6-27B` 和相同 deterministic-gate provider 参数。
- 每个续跑段 LNR 预算 300 秒，task 上限 600 秒。
- 两侧起点均从相同三个已完成 Workspace 复制；启动前逐文件、目录和软链接比较完全一致。
- 配置使用 `resume: false` 关闭 ParallelRunner 的 completed-task skip；LNR 仍检测并恢复 `.agent_memory`。

实验入口：

- `scripts/circle_packing_3seed_memory_stage3_baseline_20260822.yaml`
- `scripts/circle_packing_3seed_memory_stage3_candidate_20260822.yaml`

该实验验证“从同一历史 Workspace 继续时不丢失已有质量且恢复行为兼容”，不把已继承 final 当作一次全新搜索质量样本。

## Resume 入口对齐

baseline 与 candidate 的 6/6 worker 均产生 Resume 事件：

| seed | W00 尾部 | message count | 两侧结果 |
| ---: | --- | ---: | --- |
| 2222 | assistant complete | 39 | 一致 |
| 3333 | tool result | 47 | 一致 |
| 4444 | assistant complete | 40 | 一致 |

所有事件均为 `continue_llm`、`executed_tool=false`；没有重复 task message、JSON decode error 或 Memory repair failure。

## 严格三 seed 效果门禁

| seed | Legacy final | Candidate final | Legacy 本段耗时 | Candidate 本段耗时 | 变化 |
| ---: | ---: | ---: | ---: | ---: | --- |
| 2222 | 2.1660226194 | 2.1660226194 | 259.5 s | 251.5 s | 分数相同，耗时 -8.0 s |
| 3333 | 2.3801381751 | 2.3801381751 | 333.3 s | 331.5 s | 分数相同，耗时 -1.8 s |
| 4444 | 2.4916996200 | 2.4916996200 | 259.6 s | 251.5 s | 分数相同，耗时 -8.1 s |

汇总：

- 三个 seed 全部 completed、exit code 0、validation valid 且 selection eligible。
- 每个 seed、三 seed 中位数和最差 seed 分数均完全相同。
- 中位耗时 `259.6s -> 251.5s`，下降约 3.12%。
- `memory_stage3_effect_gate_report_20260822.json`：`passed: true`，`failures: []`。
- 任务 evaluator 独立复评两侧全部 6 个 `final_00`，均 `valid: true` 且分数逐项一致。

## 配置与 Workspace 检查

将 task workspace、input data 和 config source identity 归一化后，三组 `resolved_config.yaml` 全部相同。

完整 Workspace compatible comparator 的结果没有被篡改为通过：三组均 missing 0、additional 0，但分别有 9、11、9 个 mismatch。全部 29 个 mismatch 都是复制旧 Workspace 后，Merge/Submission 软链接仍解析到同一个 Stage-2 原始 snapshot，而 baseline worktree 与 candidate worktree 深度不同，导致相对软链接文本不同。没有 Memory、JSON/JSONL shape、目录、普通文件或 worker count mismatch。

因此：

- 可以判定本次 Memory schema/path 没有回归。
- 不能把本轮完整 Workspace comparator 记为 passed。
- 后续完整 Workspace A/B 应在相同物理 workspace path 上顺序恢复快照，避免复制后的外部 snapshot 相对链接污染比较。

## 阶段判定

通用 Legacy Memory Record Store 下沉切片通过，可以保留并作为 ScienceFlow 恢复 facade 的实现。以下事项仍未完成：

- ScienceFlow 主 RunLoop 和完整 Memory Policy 尚未迁移到 DeepCraft backend。
- 完整 Workspace comparator 仍需在无复制软链接歧义的实验设计下通过。
- 默认 Runtime 切换仍需非 Circle Packing 真实任务和完整 backend replay 门禁。

在这些条件完成前，继续保留 Legacy Runtime 和立即回切能力。
