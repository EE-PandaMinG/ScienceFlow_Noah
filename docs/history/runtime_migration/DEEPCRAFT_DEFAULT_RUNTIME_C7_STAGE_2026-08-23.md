# C7 DeepCraft 默认 Runtime 发布门禁记录

日期：2026-08-23

## 结论

ScienceFlow 默认 `repl.runtime_backend` 已切换为 `deepcraft`，`legacy` 开关继续保留用于一个发布
周期内回滚。确定性上下文、机制、Workspace 和性能门禁无差异；真实 vLLM CLI、三 seed
worker=2、旧 Workspace continuation、非 Circle 优化任务和 scientific-design 任务均已覆盖。

## 确定性门禁

- 根完整测试：`1675 passed, 3 skipped`（默认 backend 切换后的阶段全量结果）。
- DeepCraft 完整测试：`116 passed`。
- `runtime_parity quick --jobs 4`：`failed_cases=0`、`context_diff_count=0`、
  `mechanism_diff_count=0`、`workspace_unregistered_diff_count=0`。
- Runtime performance suite：全部 case 通过，登记比较项差异为 0。
- 历史 baseline 与本轮新鲜 Circle 运行的首条 user context：3 seeds × 2 workers 共 6 项，
  长度和 SHA-256 全部相同（W00 5281 bytes，W01 5282 bytes）。

## DeepCraft 独立 CLI 实机

通过 `deepcraft run` 直连本机 Qwen3.6-27B vLLM：

- 输出严格等于 `C7_DEEPCRAFT_CLI_OK`；
- session JSONL 的角色顺序为 `system,user,assistant`；
- event JSONL 为 8 条，sequence `1..8` 连续，末事件为 `session.completed`；
- 退出码为 0。

## Circle Packing 三 seed / worker=2

### 新鲜运行观察

清空的新 Workspace 使用与历史门禁相同的 3 seeds、每 seed 2 workers、900 秒 LNR/1200 秒
外层预算并行运行。六个 worker 的入口 context 逐项等同；但本轮模型探索具有随机结果：

- seed 2222 得到有效 Stage `2.3212703038`，随后外层在 final merge 前达到 1200 秒预算；
- seed 3333 两个候选程序均在单次重型计算中超时，没有形成 Stage/final；
- seed 4444 形成有效 final，但仅为 `1.3`。

该尝试如实保留为不合格运行，不纳入通过报告，也未通过放宽 score/status 断言掩盖。日志显示
Runtime、Memory、Tool、资源超时和停止机制正常执行，失败源于本轮生成的候选算法效果/耗时，而非
上下文或迁移机制差异。

### 精确 Workspace continuation 门禁

为隔离迁移等效性与模型重新探索随机性，将已通过的 2026-08-22 optimized 三 seed Workspace
以 reflink 副本保留，在副本上明确使用当前 `deepcraft` backend 并行继续 300 秒。历史证据未修改。

严格 effect gate（不使用 `--ignore-runtime`）结果：

| seed | baseline metric | DeepCraft continuation metric | baseline sec | continuation sec |
|---:|---:|---:|---:|---:|
| 2222 | 2.1106639153 | 2.4784410491 | 987.6 | 326.3 |
| 3333 | 1.8200000000 | 2.5158387449 | 834.3 | 339.3 |
| 4444 | 2.0154003333 | 2.0438852729 | 953.5 | 248.3 |

- 三项均 `status=completed`、`validation_ok=true`、`selection_eligible=true`；
- 每 seed quality/runtime、aggregate median、worst seed 均通过；
- candidate metric median `2.4784410491` 对 baseline `2.0154003333`；
- candidate elapsed median `326.3s` 对 baseline `953.5s`。

机器可读报告：
`docs/baselines/circle_packing/c7_deepcraft_resume_effect_gate_report_20260823.json`。

## 代表任务

- `ratio-minimization`：当前 DeepCraft backend continuation 形成有效 Stage S01 并完成 final，
  `inv_ratio_squared=0.0678325632`，`metric_validity=high`、gate accept、artifact ready；最终状态
  `completed`，正式 final evaluation 的 validation/selection 均为 true。
- `sci-modeling-bench-tfbind8`：正式 task-package evaluator 接受 Stage S01，
  `best_k_mean=0.973832`，`metric_validity=high`、gate accept、final success；同时记录
  `best_k_mean_regret=0.0250814`、`global_ndcg=0.914861`。

两项第一 segment 都曾把剩余 Bash budget 消耗在过长候选计算中；短 exact-workspace continuation
读取原 Memory/代码后成功完成评估，验证了非 Circle 和 scientific-design 的 Resume、Stage、Gate、
Evaluator 与 final selection。

## 发布判定

C7 通过，允许进入 C8 的零消费者 legacy 清理。该结论不代表整个规划已经完成：独立仓发布、
ScienceFlow 改用已发布 DeepCraft 版本，以及仍承载冻结 streaming 行为的 historical core 迁移仍是
C8 的后续边界。
