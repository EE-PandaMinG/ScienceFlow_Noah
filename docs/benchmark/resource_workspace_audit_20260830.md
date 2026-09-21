# MLEBench 资源管理事件审计（2026-08-30）

## 结论

`mlebench_workspaces` 中已经存在可用于资源管理 Resume bench 的真实事件。最强的
直接候选是 2026-07-27 Jigsaw seed3333：W00 持有重训练 lease，W01 以
`gpu_tt_light` 进入 admission/share 候选，两边各留下一个尚未配对结果的 Bash Tool
Call，旧 W00 owner PID 已死亡。它适合验证 Resume 时的 stale lease 清理、合法准入
分支、pending tool exactly-once 和最终资源归零。

这个现场还不是 stable checkpoint：当前目录仍是运行态，缺少不可变 bundle SHA、
一致性 barrier、环境指纹、secret audit 和两次独立 Resume。因此这里只登记为
`capture_required`，不能把现存目录直接当通过证据。

## 审计范围与口径

定向扫描以下六批高价值 GPU 运行，而不是对整个历史目录做无界全量扫描：

- `0727_run`
- `0802_run`
- `20260719_run`
- `20260721_run`
- `20260722_run`
- `20260724_run`

共解析 48 个 `resource_events.jsonl`、86 个 Worker `lhr_events.jsonl`、39 个任务聚合
`lhr_events.jsonl`、48 个 `resource_state.json` 和 48 个 `gpu_leases.json`；JSONL
坏行数为 0。事件数量是上述样本中的观测次数，不等价于独立故障次数。

## 关键资源管理事件统计

控制面共 74,642 条、56 种事件。以下是直接决定 bench 覆盖面的关键统计：

| 类别 | 事件 | 数量 |
|---|---|---:|
| 监测 | `resource_monitor_heartbeat` | 18,574 |
| 可恢复性 | `resource_recoverable_artifact_scope_registered` | 11,633 |
| 决策输入 | `snapshot` / `arbiter_input` | 6,416 / 6,416 |
| 干预 | `kill_proposal` / `resource_kill_executed` | 4,395 / 119 |
| review | `resource_review_boundary` | 4,129 |
| 执行 | `execution` | 3,802 |
| admission | `admission_granted` / `admission_pending` | 1,030 / 409 |
| 释放 | `resource_release` | 1,041 |
| 预算 | `llm_budget_deferred` / `llm_budget_exhausted` | 1,752 / 466 |
| managed wait | `managed_resource_wait_offered` | 410 |
| startup/observe | `resource_trial_started` / `observe_first_started` | 79 / 79 |
| 共享 GPU | `shared_gpu_lease_granted` / `shared_gpu_lease_consumed` | 71 / 53 |
| 空闲清理 | `resource_idle_lease_released` | 44 |
| 监控异常 | `resource_monitor_gap` / `resource_arbiter_timeout` | 9 / 3 |
| stale intent | `resource_kill_intent_stale` | 9 |

Worker LHR 中与运行时直接相关的事件包括：GPU 采样 23,675 次、lease acquire/release
1,030/997 次、queue wait 407 次、job start/finish 395/379 次、admission deferred
409 次、runtime pressure 71 次、queue heartbeat 57 次、idle release 44 次。

48 个最终 GPU store 中仍有 9 个 active lease、1 个 waiter，并记录 15 个已 reap
lease（13 个 TTL expired、2 个 owner PID dead）。历史日志没有稳定记录
`resource_resume_monitor_event` 或 `resource_gpu_stale_lease_reaped`；store 能证明曾发生
reap，但不能证明新版本 Resume 的观测链。因此新 bench 必须显式要求这两个事件。

## P0：Jigsaw 重训练 + test-time inference admission Resume

来源：

`0727_run/jigsaw-aptos-spooky-deep-pureloop-w2cpu8-gpu0-12h-3seed-serial-20260727/`
`jigsaw-toxic-comment-classification-challenge-deep-w2cpu8-gpu0-12h-noskill-pureloop-`
`seed3333-20260727/jigsaw-toxic-comment-classification-challenge`

现场证据：

- manifest 已启用 Resume；2 Workers，GPU0；CPU 实际分离为 W00 `144-151`、W01
  `152-159`。
- GPU store 有 1 active lease 和 1 waiter：W00 `bash:00144` 为
  `heavy_gpu_train`；W01 `bash:00139` 为 `gpu_tt_light`。
- W00 old owner PID `2557457` 已死亡，不能在 Resume 后继续作为 ownership proof。
- W00/W01 memory 分别以未配对的 `train_v3.py`、`score_ensemble.py` Bash Tool Call
  结束。
- 控制面 cursor 1544：W01 已出现 `managed_resource_wait_offered` 和
  `admission_share_override_candidate`。
- W00 曾观测约 735 MB 的模型文件，但两个 run 目录均缺 `run_state.json`，说明当前
  现场还不能直接晋升 stable case。

推荐验证到以下最小边界后立即停止，不必跑完整模型训练：

1. 恢复 memory/resource cursor，reap dead owner；
2. 两个 pending Tool Call 各最多执行一次；
3. 进入一个合法 admission 分支，并连续取得至少两个 monitor sample；
4. 执行 cleanup，确认 lease、waiter、benchmark process、CUDA context 全部归零。

框架/provider 可能给出不同但都合法的调度结果，所以 oracle 不绑定唯一顺序。允许：

1. W00 重新获得训练 lease，W01 获得显式 shared grant 后运行；
2. 一方独占，另一方保持 durable waiter；
3. W01 先获 lease，W00 等待。

不论采用哪一分支，都禁止把 stale owner 当存活、禁止无 share grant 的不兼容重叠、
禁止重复 side effect，并要求 CPU 集不重叠。

对应定义：[`bench_sf/cases/resource_gpu_train_tt_admission_resume_v1/`](../../../bench_sf/cases/resource_gpu_train_tt_admission_resume_v1/README.md)。

## 其他适合的阶段

### P1：Aptos shared lease grant/consume

同一 `0727_run` 的 Aptos seed3333 中，W01 S01 snapshot 后发起 `gpu_tt_light`
`predict.py`，随后出现 `shared_gpu_lease_granted`（cursor 286）和
`shared_gpu_lease_consumed`（cursor 288）。适合短程复采“test-time 推理触发共享 GPU”分支，
但原 S01 snapshot 位于 Tool Call 之前，且缺少同点 resource store，不能直接作为精确
checkpoint。

### P1：BMS review → kill → replan → cleanup

`0802_run` 的 BMS repaired seed2222 有 8,149 个控制事件、17 次 kill、167/140 次
pending/grant、45 次 checkpoint guard、37 个 stage snapshot。W01 S08 后约 69.6 秒
发生 `active_intervention:sm_timebox_expired` kill，适合复采 arbiter 干预、恢复规划和
清理链路。

### P2：stale lease reaping 与模型 warm-start

CDiscount、Alaska parent/recovery/DCTD8 的最终 store 分别保留 6、5、2、2 个 reaped
lease，可用作 oracle 设计证据，但 post-reap 状态不能替代“新代码实际执行 reap”的
验证。Alaska recovery bundle 有 Stage S12、checkpoint SHA 和 parent provenance，且
明确标为 `model_warm_start`，适合验证模型产物恢复，不应冒充完整 runtime Resume。

## 建议的 bench 分层

- tests：fake store、synthetic process、单函数/单状态机快速回归。
- `bench_sf` point Resume：从真实不可变 checkpoint 恢复，只运行到目标技术点和清理
  oracle，通常 5-20 分钟。
- 长程验收：仅在 point Resume 无法覆盖跨小时性能/收敛性质时运行。

优先落地顺序为：冻结 Jigsaw P0 bundle → 两次独立 Resume → 晋升 stable；然后复采
Aptos shared grant 和 BMS intervention 两个短边界。这样资源管理的关键机制可由真实
Resume 继承验证，不再要求每次全量长程重跑。

## 2026-08-30 执行更新

- `resource_state_recovery_logic_resume_v1` 已冻结 Jigsaw seed3333 的真实
  `gpu_leases.json`，并在两个物化副本中调用当前 `GPULeaseStore`。两次均验证 dead W00
  heavy owner reap → W01 TT waiter admission → duplicate acquire/release 幂等 → final
  lease/waiter 为 0，得分 100。它是 CPU component case，不触碰物理 GPU。
- mixed GPU case 的 228 MB 不可变 bundle 已在两个独立 workspace 完成 89.267/90.324 秒
  真实 CUDA Resume；两次均为 100 分，到达 durable waiter 合法分支，provider 0、CPU 分离、
  heartbeat 去重与 cleanup 全过，并晋升 `stable`。
- strict heavy-heavy harness 已形成 5,227-byte canonical bundle，并在两个独立 workspace
  完成 17.407/17.549 秒真实 CUDA Resume；两次均为 100 分。真实 `GPULeaseStore`、InquiryCraft
  双 pending Tool、事件 partial order、benchmark-owned heavy process 互斥、幂等和 cleanup 全过，
  并晋升 `stable`。
- GPU0 上的外部 Ray PID 4044945 未被终止或接管。显式 external-baseline 模式只统计本 bench
  拥有的 process 并要求其资源归零；未显式允许时仍执行 clean-GPU preflight。
- canonical registry 最终为 16/16 `stable`，工具测试 25/25；资源 P0 的实际落地已关闭。
