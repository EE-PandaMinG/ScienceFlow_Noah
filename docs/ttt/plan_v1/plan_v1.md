# ScienceFlow TTT Plan V1：异步训练、Workspace Resume 与 Online Agentic 自主迭代

状态：设计完成，尚未实现

版本：V1；日期：2026-08-31

基线：ScienceFlow `747d6329f12c0b914dd8ca97b21787acb788b374`；TTT-Discover
`6c40e82dab9d5de7416ac873ad5cd3106084aaed`。

## 1. 决策摘要

ScienceFlow 可以引用 [TTT-Discover](https://github.com/test-time-training/discover) 的问题环境、连续奖励、
PUCT 状态档案、组内优势估计、KL 约束和 LoRA test-time RL 思路，实现长程科研任务中的自主迭代。
但不能把上游同步训练函数直接插入当前 Agent loop。V1 采用以下结构：

1. ScienceFlow Agent/Worker 是使用不可变策略版本的 Actor；
2. Stage、Evaluator 和 Gate 只把已验证经验提交到 append-only Experience Store；
3. H200 上的独立 Learner 异步消费经验，训练新的任务级 LoRA；
4. Candidate Policy 通过 shadow evaluation 和 `bench_sf` Resume 门禁后才能晋升；
5. 策略只在新 Stage 或 lineage 边界切换，不在 Tool Call、turn 或 Stage transaction 中途热切；
6. Workspace、Memory、事件、探索 archive、模型权重和 optimizer 通过复合 checkpoint barrier 关联。

V1 的“基模型自主迭代”是冻结 Qwen base，加上自动生成、验证、晋升和回滚的任务级 LoRA。
全量 base 权重合并属于后续离线 consolidation，不属于 V1 在线热路径。

## 2. 目标与非目标

### 2.1 目标

- Agent 正常探索期间异步训练，不阻塞 Tool、Evaluator 或多 Worker 调度；
- 从真实 evaluator/gate 构造可审计 reward，不以模型自评作为唯一信号；
- 支持进程、主机或服务中断后的精确 Resume，不重复 Tool effect、Stage commit、optimizer step 或 promotion；
- trajectory 可追溯到 policy、prompt、Tool、Workspace snapshot、Stage、reward contract 和代码版本；
- 多 Worker 并行产生经验，同时保持 worker/lineage 隔离和有界 policy lag；
- 用 `bench_sf` 的短窗口真实 Resume 覆盖训练边界，普通变更不重新跑一小时全量任务；
- 保持 ScienceFlow、InquiryCraft、训练后端和模型服务分层，不建立第二个 Agent Runtime。

### 2.2 非目标

- V1 不在线更新全量 Qwen base；
- 不在未完成的 Agent turn、Tool Call 或 Stage 中途切换 policy；
- 不允许未经 Gate 的 raw conversation 自动进入训练；
- 不把不同任务、reward 定义或数据许可的经验静默混合；
- 不以 vLLM 充当训练器；vLLM 仍是推理服务层；
- 不以最终单次高分代替可恢复性、资源清理和无重复 effect 门禁。

## 3. 上游审计与引用边界

TTT-Discover 面向单个问题执行 test-time reinforcement learning，目标是找到当前问题的极佳解，而非优化
跨任务平均表现。可复用机制包括：

- `Environment`、`State`、`RewardEvaluator` 抽象；
- group rollout、连续 reward、mean/entropic/adaptive advantage；
- 对 base policy 的 KL penalty；
- PUCT state archive、parent lineage、top-k child 和去重；
- LoRA training/sampling client、optimizer checkpoint；
- sampler state 按 step 保存和恢复；
- Ray/Submitit 资源调度思路。

检查的上游版本存在这些不能直接继承的假设：

- `discover_impl` 当前只允许 GPT-OSS 120B/20B；
- 训练依赖 Tinker `TrainingClient`，不能直接驱动现有 Qwen/vLLM；
- 主循环仍是 batch 级 `rollout → train → new sampling client`；
- rollout 组内并行不等于完整 actor--learner 异步；
- `WrappedTrajectoryGroup.sampling_client_step` 预留陈旧轨迹字段，但没有完整消费协议；
- checkpoint 未覆盖 ScienceFlow Workspace、Tool effect、Memory、Stage、resource、reward 与 registry；
- checkpoint JSONL 不是跨状态域事务。

因此 V1 引用算法和合同，替换训练后端并增加复合 Resume，不复制上游训练编排。上游为 MIT License；
实施时固定 commit、保留许可证头和 NOTICE，并引用论文 *Learning to Discover at Test Time*，
arXiv:2601.16175。

## 4. 术语与五类状态

| 术语 | V1 定义 |
| --- | --- |
| Base model | 冻结 Qwen 权重及 tokenizer/config 指纹 |
| Adapter | 可独立训练、加载、回滚的 LoRA |
| Policy version | base + adapter + renderer + sampling config 的不可变内容标识 |
| Actor | 固定使用一个 policy version 执行 rollout 的 ScienceFlow Worker |
| Experience | 经过 effect 对齐、格式校验和 reward 提交的 trajectory |
| Learner | 在 H200 消费经验并产生 candidate policy 的独立进程/服务 |
| Promotion | candidate 通过门禁后成为新 Stage 可用的 active policy |
| Policy lag | behavior policy 与 learner target policy 的版本距离 |

必须分离：Workspace 状态、Agent 状态、Research 状态、Exploration 状态、Learning 状态。任何只保存其中
一部分的 checkpoint 都不能声明为精确可恢复。

## 5. 总体架构

```text
ScienceFlow Actors (policy vN)
  └─ Tool/Workspace ─ Stage ─ Evaluator ─ Gate
                                 │ authoritative reward
                                 ▼
Append-only Experience Store ─ eligibility/dedup/replay cursor
                                 │ finalized batch
                                 ▼
Async Learner on H200 ─ TTT objective ─ LoRA candidate vN+1
                                 │
                                 ▼
Policy Registry ─ Shadow Eval ─ bench_sf ─ Promote/Rollback
                                 │ stage/lineage boundary
                                 └────────────► Actors use vN+1

Cross-cutting: Composite Checkpoint Barrier + Event Journal + Resource Manager
```

### 5.1 Agentic Plane

现有 ScienceFlow/InquiryCraft Runtime 继续拥有 conversation、Tool execution、Memory 和 Workspace effect。
TTT 只通过窄观察口读取 provider input hash、assistant action、Tool Result/effect ID、Stage/evaluator/gate、
artifact SHA、snapshot ID、resource usage 和 termination reason。TTT 不得补写 factual memory、模拟 Tool Result
或直接修改 Stage ledger。

### 5.2 Experience Plane

Experience Store 是 append-only、内容寻址、幂等的训练投影，不是第二份 conversation 事实源。每条记录至少有：

```yaml
schema_version: 1
trajectory_id: sha256:<canonical-record>
run_id: ...
worker_id: W00
lineage_id: ...
stage_id: S03
behavior_policy_version: policy:qwen+adapter-v7
prompt_contract_hash: sha256:...
reward_contract_hash: sha256:...
workspace_snapshot_id: ...
workspace_manifest_sha256: ...
event_cursor_start: ...
event_cursor_end: ...
transition_refs: [...]
sampled_logprobs_ref: artifact://...
terminal_reward: 0.71
gate_status: accepted
artifact_sha256: ...
eligibility: accepted
```

大 token/logprob 使用对象存储；记录只保存 SHA、大小和 URI。credential、私有绝对路径和无许可数据不得进入。

### 5.3 Learning Plane

建议定义 `TrainingBackendPort`：创建/恢复 learner、训练 batch、checkpoint、导出 adapter、关闭。首个 backend
可用 PyTorch + PEFT，按需要接 TRL/verl。ScienceFlow 领域层只依赖 typed port；vLLM 只加载已导出的
immutable adapter 并提供推理。

### 5.4 Policy Control Plane

Policy 状态机：

```text
training → candidate → validating → promoted → retired
                    └→ rejected
promoted ── regression ──► rolled_back
```

Version ID 由 base、adapter、tokenizer、renderer 和 sampling config 决定；promote/rollback 使用幂等
operation ID；active pointer 用 compare-and-swap；旧版本在所有引用 run 完成前不能清理；每次 provider call
记录实际 policy version。

## 6. 异步训练语义

### 6.1 V1：有界半异步

1. Actor 在一个 Stage 内固定使用 `vN`；
2. 多 Worker 并行产生 `vN` experience；
3. Learner 后台训练 `candidate vN+1`；
4. Actors 可继续使用 `vN`，不等待训练；
5. `vN+1` 通过门禁后只对新 Stage/lineage 可见；
6. 默认 `max_policy_lag=1`，超限经验不进入当前 on-policy batch。

这已经获得执行与训练墙钟并发，同时避免 turn 内热切。

### 6.2 后续完全异步

启用多版本 Actor queue 前必须有 behavior version、逐 token sampled logprob、target logprob 重算、importance
ratio clipping/off-policy objective、最大 lag/age、stale discard/requeue、backpressure，以及 learner crash 后
不重复 optimizer step 的 batch commit。不能因上游 loss 名称是 `importance_sampling` 就假定任意旧轨迹安全。

### 6.3 Batch Commit

```text
batch_id = H(reward_contract, behavior_policy,
             sorted(trajectory_ids), objective_config)

prepared → gradients_computed → optimizer_applied
         → checkpoint_saved → committed
```

Resume 只承认 `committed`。若 backend 不能证明 optimizer step 幂等，就回到上一个 committed checkpoint，
重算整个 batch，而不是猜测半步状态。

## 7. Reward、Advantage、KL 与 PUCT

Reward 优先来自 authoritative evaluator metric、Gate 合法性和资源/安全 penalty。没有外部 evaluator 时才允许
版本化 learned judge，且必须标记非权威。assistant 自述“成功”不能直接变成正 reward。

同一 advantage group 必须共享 task、reward/evaluator version、metric direction、prompt contract、behavior
policy family 和 dataset fingerprint。V1 支持 mean baseline 与上游 entropic adaptive advantage；常量 reward
组记录后丢弃。

KL reference 默认是 candidate 的 parent promoted policy，同时监控相对最初 base 的累计 drift。单步 KL、累计
drift 或 held-out regression 超阈值均可拒绝晋升。

TTT State 只引用 Stage node UID、lineage、Workspace manifest SHA、artifact SHA、metric、parent 和 bounded
observation。PUCT 决定从哪个科学状态继续；真正 restore 仍通过 ScienceFlow snapshot/lineage port。

## 8. Composite Checkpoint

### 8.1 Manifest

```yaml
schema_version: 1
checkpoint_id: sha256:<canonical-manifest>
barrier_id: ttt-barrier-...
status: committed
workspace:
  snapshot_id: ...
  manifest_sha256: ...
  git_checkpoint: ...
agent:
  memory_cursor: ...
  provider_event_cursor: ...
  pending_tool_effect_ids: [...]
research:
  stage_ledger_cursor: ...
  active_stage_id: ...
  lineage_id: ...
  evaluator_cursor: ...
  gate_cursor: ...
  resource_store_cursor: ...
exploration:
  archive_sha256: ...
  replay_cursor: ...
  committed_trajectory_cursor: ...
learning:
  backend: ...
  optimizer_checkpoint_uri: ...
  optimizer_checkpoint_sha256: ...
  committed_batch_id: ...
  rng_state_sha256: ...
policy:
  behavior_policy_version: ...
  active_policy_version: ...
  candidate_policy_version: ...
  registry_cursor: ...
fingerprints:
  scienceflow_commit: ...
  inquirycraft_commit: ...
  discover_commit: ...
  task_package: ...
  dataset: ...
  reward_contract: ...
  evaluator: ...
```

### 8.2 Barrier

1. 请求 barrier，停止接受新 provider/tool/train batch；
2. 已开始 effect 完成或进入可恢复 pending；
3. flush Memory、Stage、Gate、resource、experience；
4. capture Workspace snapshot；
5. Learner 完成 batch commit，或回到前一 committed batch 后 checkpoint；
6. Registry 返回 cursor 和所有引用版本；
7. 写 provisional manifest；
8. audit SHA、cursor、对象可读性和旧进程依赖；
9. 原子写 `checkpoint_committed`；
10. 解除 barrier。

超时写 `checkpoint_aborted`，不得留下貌似可恢复的 manifest。

### 8.3 Resume

选择最后完整 committed manifest；校验代码、数据、reward、evaluator、model；恢复到新的 Workspace 副本；
恢复 Agent/Research projection；reconcile PID、GPU lease、pending Tool；加载 exploration/replay；恢复 learner；
恢复 registry routing 但不重复 promotion；裁决 pending effect/batch/promotion；写 `ttt_resume_completed` 后才允许
新 provider call。

Tool effect 依靠 effect ID 达到语义 exactly-once；Journal 和 Experience 可以 at-least-once 加去重；optimizer
从 committed checkpoint 重放整个 batch；promotion 用 CAS + operation ID exactly-once。

## 9. 晋升、Routing 与回滚

Candidate 依次经过 adapter 可加载验证、deterministic provider contract、held-out shadow evaluation 和真实
`bench_sf` Resume。晋升至少要求：主 reward 提升或非劣、artifact/Tool/Workspace/effect 全通过、安全和资源
penalty 为零、held-out 无超阈回归、同一只读 bundle 两次独立 Resume、全部版本指纹齐全。

```yaml
policy_routing:
  mode: stage_boundary
  scope: task
  active_version: policy:...
  max_policy_lag: 1
  pin_for_stage: true
  pin_for_tool_transaction: true
  allow_mid_stage_switch: false
```

ESTRA switch 创建新 lineage 时可解析最新 promoted policy；keep-current 只有创建新 continuation lineage 后才
重新解析。Rollback 只更新 routing pointer，不删除失败 policy；由失败 policy 产生的经验默认 quarantine。

## 10. Qwen、H200 与 vLLM

```text
H200 storage
  ├── frozen Qwen base
  ├── learner checkpoints (optimizer + LoRA)
  └── immutable exported adapters

Training: PyTorch/PEFT/TRL/verl
Serving:  vLLM/OpenAI-compatible endpoint
Control:  ScienceFlow registry/routing
```

训练不能覆盖 vLLM 正在读取的目录。adapter 导出使用临时目录、SHA 校验和原子 rename；promotion 前执行
readiness probe。Agent inference、Evaluator GPU 任务和 Learner 分别声明 resource class；Learner 优先级低于
交互式 inference，显存不足时 checkpoint/pause learner。远端保存大对象，本地 Workspace 保存 manifest/SHA。

## 11. 组件落点

不增加新的 `scienceflow/` 顶层目录：

```text
scienceflow/
  foundation/contracts/learning/  # records and ports
  research/learning/
    experience/                   # eligibility, record, store
    objective/                    # advantage, KL, batch decision
    policy/                       # registry, promotion, routing
    resume/                       # composite checkpoint
    service.py                    # narrow composition
  runtime/learning/
    backend/                      # trainer adapters
    execution/                    # learner process/client
    serving/                      # vLLM readiness/switch
    resources/                    # lease/admission adapter
  interfaces/cli/commands/        # ttt inspect/train/resume/promote
```

每级直接子目录/业务模块仍不超过 5。领域算法位于 `research/learning`，外部 effect 位于
`runtime/learning`；Agent/LNR 只依赖 typed ports。核心类型包括 `TrajectoryRecord`、`RewardContract`、
`TrainingBatch`、`PolicyVersion`、`PromotionDecision`、`CompositeCheckpointManifest` 及相应 Store、Backend、
Registry、Serving、CheckpointParticipant ports。

## 12. 配置草案

```yaml
ttt:
  enabled: false
  mode: semi_async
  scope: task
  upstream_commit: 6c40e82dab9d5de7416ac873ad5cd3106084aaed
  policy:
    base_model: Qwen3.6-27B
    adapter_type: lora
    lora_rank: 32
    switch_boundary: stage
    max_policy_lag: 1
  experience:
    accept_gate_status: [accepted]
    require_authoritative_reward: true
    redact_credentials: true
    max_queue_items: 4096
  objective:
    advantage: entropic_adaptive_beta
    kl_parent_coef: 0.1
    remove_constant_reward_groups: true
    loss: importance_sampling
  learner:
    backend: peft
    host_profile: H200
    checkpoint_every_batches: 1
    max_inflight_batches: 1
  promotion:
    require_shadow_eval: true
    require_bench_sf_attempts: 2
    allow_mid_stage_switch: false
  resume:
    composite_checkpoint: true
    barrier_timeout_sec: 300
```

`Qwen3.6-27B` 是本轮用户指定的运行标识；实施前必须记录服务端返回的精确 model ID、权重 SHA、tokenizer
SHA 和 serving revision，不能只依靠简称。

## 13. 失败模式

| 失败 | 正确裁决 | 禁止行为 |
| --- | --- | --- |
| Tool Call 后 Actor 崩溃 | pending effect reconciliation | 重新生成整个 turn |
| Experience 重复投递 | trajectory ID 去重 | 重复入 batch |
| backward 后 Learner 崩溃 | 回前一 committed checkpoint 重算 | 猜 optimizer 状态 |
| Adapter 导出不完整 | reject，active 不变 | 覆盖 active adapter |
| Promotion 后崩溃 | operation ID/CAS 判断已提交 | 重复版本/切换 |
| Reward contract 改变 | 旧经验 quarantine | 静默混训 |
| Policy lag 超限 | discard/requeue | 当作当前 on-policy |
| H200 不可达 | 继续 current promoted policy | 阻塞 Agent |
| vLLM readiness 失败 | 保持 parent endpoint | 晋升不可服务版本 |
| Cursor 不一致 | 拒绝 composite checkpoint | 各取“最新”状态 |
| GPU owner 死亡 | stale reconciliation | 继承旧 PID |
| Reward 异常升高 | hacking/held-out audit | 只看最高分晋升 |

## 14. 验证体系

Unit/contract 覆盖 schema/hash、eligibility/redaction/dedup、advantage/KL、registry CAS、barrier、stale trajectory、
contract drift 和 package boundary。TTT 默认关闭时 runtime parity 的 provider context、Tool schema、event ordering
与 Workspace effect 必须零漂移；capture-only 只允许新增登记的 learning telemetry/object。

新增 `bench_sf`：

| Case | Resume 边界 | 硬 oracle |
| --- | --- | --- |
| `ttt_experience_commit_resume_v1` | Gate accepted、append 前 | 单次提交、reward/source 一致 |
| `ttt_learner_batch_resume_v1` | optimizer step 周边 | committed 不重做、半步不误认 |
| `ttt_workspace_policy_atomic_resume_v1` | provisional barrier 后 | 五域 cursor 同一 barrier |
| `ttt_stale_trajectory_rejection_v1` | old item 已排队 | lag 裁决确定、不得训练 |
| `ttt_policy_promotion_resume_v1` | validated、CAS 前 | 单次 promotion、pointer 正确 |
| `ttt_stage_boundary_switch_v1` | 新版 promoted、旧 Stage 未结束 | 旧 Stage pin，新 Stage 切换 |
| `ttt_policy_rollback_resume_v1` | regression、回滚前 | parent 恢复、candidate 可审计 |
| `ttt_reward_contract_drift_v1` | reward version 更新 | 旧经验 quarantine |
| `ttt_h200_learner_recovery_v1` | remote learner 中断 | lease 清理、checkpoint 可加载 |
| `ttt_vllm_adapter_readiness_v1` | 导出后、服务切换前 | readiness 失败不影响 active |

每个 stable case 需要同一只读 bundle 的两次独立 Resume。发布候选再执行 Circle、Nomad、TFBind8 从零长程
矩阵，对比 frozen parent、capture-only、train-no-promotion 和 auto-promotion。必须报告无效/未触发/环境错误、
训练成本、延迟、GPU 和资源泄漏，不能只报告最高分。

## 15. 实施阶段

### V1-0：合同与 Capture

实现 typed contracts、canonical hash、capture-only projector、reward/eligibility audit、NOTICE 和 disabled/capture
runtime parity。完成条件：不训练也能从真实 Stage 生成脱敏、来源完整、effect pairing 正确的 Experience。

### V1-1：离线 Learner

实现 Qwen + PEFT backend、advantage/KL、deterministic batch、optimizer/adapter checkpoint 和固定经验 replay。
不连接 online routing。

### V1-2：Composite Checkpoint

实现 participants、prepare/commit/abort barrier、experience/learner/registry cursor、audit CLI 和前三个 bench case；
Tool、experience、optimizer、promotion 边界中断都不得重复 effect/step。

### V1-3：H200 半异步

实现 remote learner、resource pause/checkpoint/recovery、immutable export、vLLM readiness 和 backpressure。
Agent 使用 vN 时后台产生 vN+1；Learner 不可达不阻塞 Agent。

### V1-4：Shadow Eval 与人工晋升

实现 registry、held-out runner、bench integration、manual promote/reject/rollback CLI 和 Stage router。晋升后仅新
Stage 使用新版本。

### V1-5：自动晋升与 Agentic Loop

实现 versioned promotion policy、automatic evaluation、online regression/rollback、ESTRA/new-lineage routing
和完整 bench chain。只在 allowlisted profile 自动运行。

### V1-6：受控 Full Async（可选）

实现多版本 queue、off-policy correction、bounded lag scheduler、dynamic batch 和 cross-run retention。
不自动包含 base merge。

## 16. Definition of Done

1. 上游许可、commit、引用和算法差异记录完整；
2. Qwen LoRA learner 在 H200 实际训练并 checkpoint/resume；
3. Agent 与训练真实异步，Learner 故障不停止 active policy；
4. Composite checkpoint 覆盖五类状态，所有中断 case 通过；
5. policy version 在 provider call、Stage、trajectory、artifact 可追踪；
6. promotion/rollback 幂等且只在允许边界发生；
7. reward 来源权威，contract drift/reward hacking 有硬门禁；
8. TTT bench cases 各通过两次独立 Resume；
9. TTT disabled runtime parity 零漂移；
10. 至少一个真实任务无人工完成 experience→train→validate→promote/rollback；
11. Circle、Nomad、TFBind8 发布矩阵完成并报告负面结果；
12. 文档、配置、操作、清理和回滚说明齐全。

## 17. P0 风险与实施前决策

P0 风险包括 reward hacking、Workspace/policy 错配、重复 optimizer step、数据泄漏、灾难性遗忘和 GPU 争用。
V1 分别使用 held-out verifier、composite checkpoint、committed batch、provenance、冻结 base 和 resource safe
preemption 控制。

实施前确认：Qwen3.6 27B 精确 checkpoint/tokenizer；训练 backend；vLLM LoRA readiness；首个 task/reward；
promotion 非劣阈值；experience 保留/许可；adapter 对象存储；自动 promotion 的 allowlist。

## 18. 推荐第一步

先做 V1-0，不直接启动训练：建立 `TrajectoryRecord`、`RewardContract`、`PolicyVersion`、
`CompositeCheckpointManifest` 四个合同，并从 Circle 或现有 `bench_sf` checkpoint capture 真实 Experience。
通过来源、脱敏、effect pairing 和 runtime parity 后，再接 H200 离线 Learner。

## 19. 参考资料

1. M. Yuksekgonul et al., “Learning to Discover at Test Time,” arXiv:2601.16175, 2026.
2. TTT-Discover repository, commit `6c40e82dab9d5de7416ac873ad5cd3106084aaed`.
3. TTT-Discover `ttt_discover/rl/train.py`、`tinker_utils/sampler.py`、`discovery.py`。
4. ScienceFlow [`bench_sf_v1.md`](../../benchmark/bench_sf_v1.md)。
5. ScienceFlow [`plan_v5.2.md`](../../plans/current/plan_v5.2.md)。
6. ScienceFlow [`memory_estra_v3.md`](../../architecture/memory_estra_v3.md)。
7. ScienceFlow [`resource_management_v3.md`](../../architecture/resource_management_v3.md)。

## 20. 证据边界

本文是源码与现有架构上的设计，不是完成声明。截至 2026-08-31，尚未在 H200 执行 Qwen TTT 训练；尚未
实现 Experience Store、Learner、Registry 或 composite checkpoint；尚无 TTT 专属 stable bench；性能、
收敛、显存和 reward 提升都没有实验数据。后续“自主迭代已实现”必须满足第 16 节，不能由接口存在或单次
训练成功代替。
