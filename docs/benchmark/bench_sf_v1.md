# bench_sf V1：ScienceFlow 可恢复长程技术基准

状态：V1 implemented and verified（14 component + 2 physical GPU，全部 stable）

版本：V1

日期：2026-08-30

Canonical 可执行项目现位于工作区级
[`/home/mingming/rsi/codes/bench_sf`](../../../bench_sf/README.md)。本文件保留 V1 规划来源；
registry、case、Resume、oracle 和 scorecard 的执行版本以独立项目为准。

## 1. 定义

`bench_sf` 是 ScienceFlow 真实长程运行的 checkpoint/Resume 基准库。

它不是 pytest 的别名，也不是把 unit test 做得更长。每个 benchmark case 来源于一次真实长程运行，
在关键技术机制触发前保存不可变 checkpoint。后续代码变更从该 checkpoint 的副本 Resume，只运行一段
较短的真实模型窗口，确认这个技术点仍能继承历史状态并正确继续。

核心目的：把“一次 1 小时长跑里偶然走到的关键路径”变成可重复进入的实测入口，避免每次工程重构都从
空 Workspace 开始跑完整任务。

## 2. 与现有验证体系的区别

| 体系 | 输入 | 是否真实模型 | 验证重点 | 常规耗时 |
| --- | --- | --- | --- | ---: |
| `tests/` | synthetic fixture/fake | 通常否 | 单元、合同、边界、确定性机制 | 秒到分钟 |
| runtime parity | 冻结 capture | 否 | context/mechanism/workspace 零漂移 | 秒级 |
| `bench_sf` | 真实长程 Workspace checkpoint | 是 | 历史状态继承、真实 continuation、关键机制可达 | 数分钟到短时段 |
| formal acceptance | 新 Workspace，从零开始 | 是 | 整体任务效果、长预算稳定性、发布验收 | Worker=2、1 小时级 |

`tests/` 回答“函数和合同是否正确”；`bench_sf` 回答“一个已经运行很久的真实任务，升级代码后能否从
关键状态继续，并实际走完目标机制”。两者不能互相替代。

## 3. 基本原则

### 3.1 Checkpoint 位于技术边界之前

每个 case 必须明确一个 `resume_boundary`，例如：

- assistant 已提交单个 Tool Call，但 Tool Result 尚未写入；
- evaluator 已产生权威结果，Stage commit 尚未完成；
- context 已达到阈值，ESTRA/compaction 尚未执行；
- ESTRA 已作出 switch/keep 决策，lineage restore 或 compact 尚未提交；
- main agent 已返回 text-only completion，ESTRA eligibility/decision 尚未执行；
- 多个 worker 已产生不同 Stage，peer context collection 尚未投影到下一次 continuation prompt；
- 两个 worker 已产出候选，global merge 尚未开始；
- TFBind8 query ledger 接近预算终点，terminal query/finalization 尚未发生；
- GPU lease/queue 已持久化，进程中断后的 reconciliation 尚未执行。

Checkpoint 不能保存于目标机制完成之后，否则只能证明读取旧结果，不能证明新代码执行了该机制。

### 3.2 原 checkpoint 永不原地续跑

- checkpoint bundle 是只读、内容寻址的基线。
- 每次运行先恢复到新的临时 workspace，再 Resume。
- benchmark 结束后只保存 report 和候选 workspace manifest，不修改源 bundle。
- 同一 bundle 连续恢复两次必须得到相同的起始 manifest 和 event cursor。

### 3.3 验证框架硬合同，不强求模型逐字节输出

真实模型存在轨迹与分数波动。硬门禁包括：

- Resume action 和 pending operation 正确；
- conversation/tool pairing 不重复、不丢失；
- required event subsequence 出现且顺序正确；
- Stage/Gate/ESTRA/Resource/Merge 状态转换合法；
- Workspace 只产生登记过的增量；
- artifact 结构、SHA、query ledger 和 final selection 合法；
- CPU/GPU 分配与 process cleanup 符合 case 约束；
- 无第二个 factual conversation、重复 Tool 执行或重复 Stage commit。

模型分数、文本和 token 数默认是观测指标。只有 case 明确声明稳定区间并有足够历史样本时，才作为硬门禁。

### 3.4 `unreached` 与 `failed` 分开

- `passed`：目标机制已执行，所有硬 invariant 通过。
- `failed`：目标机制已执行，但框架 invariant 失败。
- `unreached`：模型在规定窗口内没有触发目标机制。
- `environment_error`：模型服务、数据、依赖或主机资源不可用。

`unreached` 不能记作框架回归，也不能记作通过；它提示 checkpoint 离技术边界太远或 case 需要重新取点。

## 4. 已实施目录

Canonical 实现位于独立工作区 `/home/mingming/rsi/codes/bench_sf`，不放入 ScienceFlow
仓库或 `tests/`：

```text
bench_sf/
├── README.md
├── registry.yaml
├── runner.py
├── audit.py
├── schemas/
│   ├── case.schema.json
│   └── report.schema.json
├── cases/
│   └── <case_id>/
│       ├── case.yaml
│       ├── resume.yaml
│       ├── oracle.yaml
│       ├── checkpoint.sha256
│       └── README.md
└── reports/
    └── .gitkeep
```

大型 checkpoint bundle、模型权重和数据集不直接提交 Git。仓库只保存内容 SHA、大小、存储位置、解包
manifest 和数据指纹。小型且无敏感信息的 portable checkpoint 可以单独评审后入库。

## 5. Checkpoint 内容合同

一个可恢复 bundle 至少包含或引用：

- task workspace 与 worker workspace；
- `.agent_memory`/conversation store；
- Stage ledger、snapshot index 和 lineage archive；
- task/worker/global event logs 及各自 cursor；
- `state.json`、resolved config 和 Resume budget 元数据；
- 已生成的候选 artifact 及 SHA；
- evaluator/gate 已提交的权威事实；
- query ledger、resource store 等目标机制需要的持久化状态；
- ScienceFlow、InquiryCraft、任务包和数据集版本指纹；
- provider/model fingerprint，但不得包含 API key 或 credential。

不应直接恢复：

- 旧 PID、PGID 或仍存活进程；
- 旧 socket/临时文件描述符；
- 未经重验证的 GPU 物理占用；
- 主机 credential。

资源类 checkpoint 恢复的是逻辑 lease/queue 状态，由新进程执行 stale-state reconciliation。

## 6. Case 元数据

建议 `case.yaml` 使用以下最小合同：

```yaml
schema_version: 1
case_id: circle_before_global_merge_v1
technology: multi_worker_merge
task_profile: circle_packing
source_run:
  run_id: v5-circle-packing-w2-1h
  scienceflow_commit: 8f6e0576bb56020a04352054c81f91d4cd4bbe64
  inquirycraft_commit: 502b8a48ea42aa00d6e8855f823036edba96daee
checkpoint:
  boundary: workers_finished_before_global_merge
  bundle_uri: artifact://bench_sf/circle_before_global_merge_v1.tar.zst
  sha256: <required>
  workspace_manifest_sha256: <required>
  event_cursors:
    worker_W00: <required>
    worker_W01: <required>
resume:
  budget_sec: 600
  max_attempts: 2
  cpu_cores_per_worker: 8
oracle: oracle.yaml
owner: finalization
```

`oracle.yaml` 至少声明：

- required/forbidden events；
- event partial order；
- pre/post state predicates；
- Workspace allowed delta；
- artifact validators；
- Resume 幂等性要求；
- 超时和资源上限；
- 哪些指标是 hard、warning 或 informational。

## 7. V1 关键记录点

V1 不追求数量多，先覆盖一条长程任务从运行到恢复、评估、切换和收口的关键链路。

| ID 类别 | Checkpoint 边界 | 主要硬验证 | 建议来源 |
| --- | --- | --- | --- |
| `resume_pending_tool` | assistant Tool Call 后、Tool Result 前 | Tool 只执行一次，pairing 正确 | 专门中断的真实 LNR run |
| `stage_commit` | evaluator/gate 通过后、commit 前 | 单次 commit、ledger/event/snapshot 一致 | Circle/TFBind8 |
| `text_only_estra_trigger` | main agent text-only completion 后、ESTRA check 前 | trigger_source、eligibility、去重、pending ESTRA | Circle/Nomad 长程 Workspace |
| `estra_keep_compact` | ESTRA keep/redirect 决策后、compact 前 | 不恢复 archived workspace、保留 terminal ledger、context 收缩、continuation lineage 单次启动 | Circle 长程 Workspace |
| `estra_switch_restore` | ESTRA switch 决策后、restore 前 | 精确 archived node、lineage 切换、memory projection | Circle 长程 Workspace |
| `estra_restore_rollback` | restore 已开始、后续 step 尚未提交 | 失败回滚、active lineage/ledger 不损坏 | Circle 长程 Workspace |
| `snapshot_restore` | lineage archive 已存在、restore 前 | 精确 node UID、ledger rollback、artifact 恢复 | Circle |
| `resource_recovery` | queue/lease 持久化后、进程恢复前 | stale reconciliation、无重复 lease/effect | 独立 GPU 长程 case |
| `multiworker_peer_context` | peer Stage 已聚合、下一次 continuation prompt 前 | worker 集合提示、valid/suspicious 区分、上下文边界 | Circle/Nomad |
| `worker_merge` | workers 完成、merge 前 | CPU 隔离、candidate collection、预算和 fallback | Circle/Nomad |
| `partial_worker_finalization` | 部分 worker 无候选、finalize 前 | failure kind、final count、不得假成功 | Nomad |
| `query_budget_terminal` | query budget 终点前 | ledger 不超额、terminal commit、artifact 合法 | TFBind8 |
| `best_stage_finalization` | 多 Stage 已存在、选择前 | authoritative metric direction、SHA、选择唯一 | TFBind8 |
| `provider_deadline` | 长 streaming turn 已开始 | outer deadline、cancel、terminal event、无残留 | 专门 deadline case |

资源类验证已经建立一个 CPU 状态机 case 和两个互补的物理 GPU point：

| Case | 覆盖点 | 来源 | 状态 |
| --- | --- | --- | --- |
| [`resource_gpu_contention_resume_v1`](../../../bench_sf/cases/resource_gpu_contention_resume_v1/README.md) | strict heavy-heavy 互斥、queue、stale lease | 本机 purpose-built CUDA capture/Resume harness | `stable`（两次真实 CUDA Resume：17.407/17.549 秒，2×100） |
| [`resource_gpu_train_tt_admission_resume_v1`](../../../bench_sf/cases/resource_gpu_train_tt_admission_resume_v1/README.md) | heavy train + `gpu_tt_light` admission/share、dead owner、双 pending Tool Call | Jigsaw seed3333 真实运行现场 | `stable`（两次真实 CUDA Resume：89.267/90.324 秒，2×100） |
| [`resource_state_recovery_logic_resume_v1`](../../../bench_sf/cases/resource_state_recovery_logic_resume_v1/README.md) | dead-owner reap、waiter admission、acquire/release 幂等 | Jigsaw seed3333 真实 GPU store | `stable`（2×100，CPU component） |

这里的 `gpu_tt_light` 是 test-time/推理资源类别，不是 main agent 的 text-only completion；
后者只能由 `text_only_estra_trigger` case 验证。资源工作区统计和选点证据见
[`resource_workspace_audit_20260830.md`](resource_workspace_audit_20260830.md)。GPU point case
均不得在缺少两次物理 Resume 时记为 stable；CPU resource component 的通过也不能
替代 CUDA/process isolation 证据。

V5.1 evidence 可以作为 case 来源索引，但当前 evidence 目录主要保存审计结果、选中 artifact 和部分日志，
未必包含完整可 Resume workspace。只有仍保留的原 workspace 通过 bundle audit 后才能直接转成 checkpoint；
缺失的记录点应进行一次有目的的捕获，不应宣称已经具备。

### 7.1 ESTRA 记录点必须覆盖的状态

ESTRA 不能只保留一个“调用成功”的 case。V1 至少分别保存：

1. `KEEP_CURRENT`/keep-but-redirect：确认不恢复 archived workspace、不创建伪 Stage；保留 terminal
   node/ledger，并且当前实现只启动一次新的 continuation lineage；
2. `SWITCH`：确认 target archived node UID、Stage ledger、snapshot、memory 和 active lineage 一致切换；
3. restore 后续失败：确认 terminal archive、ledger 和 current lineage 原子回滚；
4. context-limit/forced ESTRA：确认触发原因、去重 key 和 decision 次数不会在 Resume 后重复消费。

硬 oracle 应检查 ESTRA decision event、restore event、lineage ID、node UID、Stage 可选集合、memory 边界和
Workspace manifest，而不是只检查最终模型回答。

### 7.2 text-only 触发 ESTRA 必须覆盖的状态

text-only 不是普通终止信号。已有历史 Stage/candidate 时，它应进入 ESTRA check；没有可切换历史状态时，
应安全 no-op 或按连续重复策略注入 continue-search，而不是伪造 Stage 或错误停止。

V1 至少覆盖：

1. 首次 text-only 且存在历史候选：写入 `text_only_estra_check`，`trigger_source=text_only`，产生
   `keep_current` 或 `switch_stage` pending command；
2. 没有 Stage/candidate：只写 `text_only_estra_noop`，不得调用 ESTRA provider；
3. 重复 terminal/goodbye completion：写入 `text_only_completion_duplicate_suppressed`，抑制重复 factual
   memory，并注入 continue-search prompt；
4. 已有 `pending_text_stage_commit`：优先完成 Stage commit，不得被 ESTRA 路由截获；
5. Resume 后 observation key、Stage count 和 pending command 不得被重复消费。

硬 oracle 应检查 assistant text hash、round、candidate node UID、observation key、ESTRA 调用次数、pending
command、memory delta 和后续 restore/compact 事件。

### 7.3 多 Worker 上下文集合提示必须覆盖的状态

多个 worker 独立探索时，下一次 first-user、ESTRA resume 或 keep-current continuation context 可以读取全局
Stage performance projection，形成有界的 `Parallel worker snapshot`。它是 provider context 提示，不是把
其他 worker 的完整 conversation 合并进本 worker factual memory。

V1 至少覆盖：

1. 每个 worker 选择 metric direction 下的 best Stage，而不是简单选择最后一条记录；
2. `validation_ok=false` 的 raw best 标为 suspicious，并同时提供该 worker 的 validation-ok best；
3. 当前 worker 有明确 `(this worker)` 标记，尚无 Stage 的 worker 保留 no-metric 状态；
4. context-limit/ESTRA Resume 后重新读取最新集合，新 peer Stage 可见，旧提示不重复写入 factual memory；
5. 超过字符上限时稳定截断，不泄漏绝对路径、peer raw conversation 或未登记 artifact 内容；
6. worker 数量、worker ID、lineage/stage node 和全局聚合 event cursor 在 Resume 前后保持一致。

硬 oracle 应比较 provider-visible peer block、来源 CSV/event cursor、semantic hash、每个 worker 的 selected
candidate，以及 conversation store 未出现 peer block 的事实性复制。

## 8. 运行档位

### `point`

- 只恢复一个 checkpoint；
- 通常运行 5–15 分钟；
- 用于某个组件切片的日常实测；
- 默认最多两次 attempt，避免把模型随机性变成无限重跑。

### `chain`

- 选择同一 owner 的 2–4 个 checkpoint 并行恢复；
- 通常 15–30 分钟墙钟时间；
- 用于 coordinator、resource 或 finalization 阶段收口。

### `release`

- 运行全部稳定 checkpoint；
- 仍然以 Resume 短窗口为主；
- 发布候选另外运行 Circle、Nomad、TFBind8 从零开始的正式 Worker=2、1 小时验收。

因此，`bench_sf release` 也不替代正式验收；它负责快速覆盖技术边界，正式验收负责发现长时间累积问题。

## 9. 变更到记录点的映射

`registry.yaml` 必须维护 owner/path → case 的映射。例如：

| 变更范围 | 必跑 checkpoint |
| --- | --- |
| Agent session、IQ Runtime hook、tool pipeline | `resume_pending_tool`、`provider_deadline` |
| Stage/Evaluator/Gate | `stage_commit`、`best_stage_finalization` |
| Memory/Context/ESTRA | `text_only_estra_trigger`、`estra_keep_compact`、`estra_switch_restore`、`estra_restore_rollback`、`snapshot_restore` |
| Resource observer/runtime/Bash monitor | `resource_recovery`、`provider_deadline` |
| Multi-worker/context projection | `multiworker_peer_context`、`worker_merge`、`partial_worker_finalization` |
| Query budget/task package | `query_budget_terminal`、`best_stage_finalization` |
| Finalization/Merge | `worker_merge`、`partial_worker_finalization`、`best_stage_finalization` |

同一个技术点只能有一个 canonical owner；可以由多个 case 覆盖，但不得出现无人负责的 checkpoint。

## 10. 捕获流程

1. 从真实任务启动一次有明确目标的长程运行。
2. 由事件条件而不是固定 sleep 判断技术边界。
3. 在边界处停止新 provider/tool effect，flush memory、events、ledger 和 snapshot。
4. 终止所有运行中进程，记录 cleanup 结果。
5. 生成 workspace manifest、event cursor、版本和数据指纹。
6. 打包、计算 SHA，并验证解包后 manifest 一致。
7. 从 bundle 副本 Resume 两次；两次都能触发目标技术点后才登记为 stable。
8. 保存 oracle、首次报告和人工说明。

如果系统不能在一致边界安全 flush，则应先实现显式 checkpoint barrier，不能依赖复制一个正在写入的目录。

## 11. 候选运行与判定

一次候选 benchmark 的顺序为：

1. 校验代码、依赖、模型、数据和 bundle fingerprint；
2. 解包到全新 workspace；
3. 重写允许变化的绝对路径，但不改 conversation、Prompt 或事实内容；
4. 清理并重建 ephemeral process/resource 状态；
5. 按 Resume manifest 运行限定预算；
6. 从起始 cursor 之后审计新增事件和 Workspace delta；
7. 输出机器可读 report，并标记 `passed/failed/unreached/environment_error`；
8. 删除运行副本或按显式选项保留，源 checkpoint 永不变更。

禁止为了让候选通过而自动刷新 checkpoint、扩大 normalization 或改写 oracle。

## 12. V1 实施顺序

### B0：Registry 与 schema

- 建立独立 `bench_sf/` 项目、case/report schema 和只读 bundle 规则。
- 定义 workspace manifest、event cursor 和 secret audit。
- 实现 `list`、`inspect`、`verify-bundle`，暂不启动模型。

完成状态：独立项目已实现 registry、schema、`list`、`inspect`、`audit`、
`capture --register`、`promote`、`verify-bundle`、`materialize`、`run` 和 `score`；capture 会执行
secret audit、生成内容寻址 bundle、workspace manifest/event cursor，register 会在重新验证后
以可回滚原子转换写回代码/数据/provider 指纹；promote 会重新评分两个独立 Resume 报告。
`fetch-artifact` 已实现显式
SHA-pinned 远端解析：下载通过 SHA/size 后进入只读 CAS，并用
`artifact://sha256/<digest>` 引用；普通 audit/run 不会隐式联网。当前 V1 canonical bundle 仍全部在本机。

### B1：首批六个 checkpoint

- `resume_pending_tool`；
- `stage_commit`；
- `worker_merge`；
- `text_only_estra_trigger`；
- `estra_switch_restore`；
- `multiworker_peer_context`。

六者分别覆盖 Agent Runtime、核心科研状态提交、多 worker 收口、text-only 路由、ESTRA lineage 和
peer context collection。

完成状态：六个 checkpoint 均已完成两次独立 100 分 Resume 并晋升 stable。

### B2：长程策略 checkpoint

- `estra_keep_compact`；
- `estra_restore_rollback`；
- `snapshot_restore`；
- `partial_worker_finalization`。

完成状态：四个 checkpoint 均已完成两次独立 100 分 Resume 并晋升 stable。

### B3：科学任务与资源 checkpoint

- `query_budget_terminal`；
- `best_stage_finalization`；
- `resource_recovery`；
- `provider_deadline`。

完成状态：query、best-stage、provider deadline、CPU resource recovery 与两个物理 GPU point
均已完成两次独立 100 分 Resume。strict contention 使用真实 CUDA process 验证 benchmark-owned
heavy workload 互斥；mixed admission 到达 durable waiter 合法分支，并验证 heartbeat 去重、CPU
分离、provider 0 和 cleanup。

后续资源 checkpoint 的扩展顺序：

1. 保持两个 stable physical point 的 bundle、报告和 history 审计；
2. 再复采 Aptos shared grant/consume 与 BMS review→kill→replan→cleanup 边界，按是否形成
   新 canonical owner 决定新增 case 或作为现有 oracle 的扩展证据。

### B4：自动选择与历史趋势

- 根据 Git diff/owner 自动给出建议 case，但运行者仍可显式覆盖。
- 保存框架 invariant、耗时、token、模型轨迹可达率和 artifact 指标趋势。
- 不把不同模型或服务负载下的分数直接混为同一回归序列。

完成状态：`bench-sf select` 按 path/owner 返回 1–3 个建议 case；`bench-sf history` 按
ScienceFlow commit、InquiryCraft commit、provider fingerprint 和 bundle SHA 分隔序列，并记录
classification、hard gate、耗时、token、机制可达性和 artifact 大小；`bench-sf chain` 以互不
重叠 CPU affinity 并行运行同 owner 的 2–4 个 stable case；`bench-sf release` 运行 stable suite，
但不会替代正式长程验收。ESTRA 四 case chain 已实跑，CPU `0-15/16-31/32-47/48-63`，均 100 分。

## 13. V1 完成定义

1. `bench_sf` 与 `tests/`、runtime parity、formal acceptance 的职责在文档和命令上清楚分离。
2. 至少 10 个 stable checkpoint，覆盖 Runtime、Stage、Resume、text-only ESTRA、peer context、Resource、Merge 和 Finalization。
3. 每个 checkpoint 都有不可变 bundle SHA、event cursor、owner、oracle 和两次恢复验证记录。
4. 任意一次运行不会修改源 checkpoint。
5. 能按组件变更选择 1–3 个相关记录点，而不是默认执行全量长程任务。
6. 框架失败、模型未触发和环境错误可以机器判定并分别报告。
7. 发布验收仍保留从零开始的长程任务，但普通组件重构不再重复消耗该成本。

2026-08-30 最终审计结果：registry 共 16 个 case，全部 stable。14 个 V1 component 技术定义和
两个物理 GPU point 均有同一不可变 bundle 的两次独立 Resume 证据；两项物理运行使用真实 CUDA，
并在保留外部 GPU baseline 的情况下只统计和清理 benchmark-owned process。详见独立
`bench_sf` 项目的 `docs/coverage_matrix_v1.md` 和 `docs/verification_audit_20260830.md`。
