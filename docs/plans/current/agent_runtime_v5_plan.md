# ScienceFlow V5：Agent Runtime 所有权收口与 InquiryCraft 下沉计划

状态：本地实现与发布门禁完成；远端三个 1h case 待验收  
日期：2026-08-29  
最近实施刷新：2026-08-29（Agent/Runtime 所有权收口）  
ScienceFlow 实施分支：`multi_modules_v3_2`  
ScienceFlow 基线提交：`72b2ec478ebd7cbeff4cd77822bc1525890ba7a6`  
InquiryCraft 实施分支：`agent_runtime_v5`  
InquiryCraft 锁定提交：`46329a41702ad667f13f248ca8bd964baf13e3e6`

## 0. 实施快照

V5 的本地代码迁移已经完成，远端功能验收仍按本计划第 11.4 节执行：

- InquiryCraft `AgentRuntime` 已成为唯一的 model/tool turn loop；`HostedAgentRuntime`、
  `BaseAgent` 和旧 executor package 已删除；
- ScienceFlow 通过 `AgentSessionSpec`、typed Hook、Tool/Turn/Exhaustion Policy 和 ordered
  context transformer 注入领域行为；Single/Multi Worker 复用同一 session 构造；
- `scienceflow.agent` 从基线 99 个 Python 文件、20,104 行降至 19 个文件、3,318 行；
- SF 自有 run-loop、LLM stream/retry、通用 tool executor、process session、legacy backend 和
  `runtime/orchestrator.py` 已物理删除；Workflow Runtime、State/Workspace、Safety、Quality、
  Gate/Evaluator 与 LNR 领域行为仍由 ScienceFlow 拥有；
- InquiryCraft 已补齐 tool choice、typed turn/exhaustion decision、same-round retry、动态 tool
  bundle、managed hooks、provider observation、pending-tool resume、ephemeral completion 和 typed
  process session，并维护在 `HOST_EXTENSION_API.md`；
- full runtime parity 的 context/mechanism/workspace 差异均为 0；未修改 prompt、stage、gate、
  evaluator、资源策略或评分算法；
- 本地证据：InquiryCraft `225 passed, 1 skipped`；ScienceFlow `1834 passed, 3 skipped`；
  InquiryCraft wheel/sdist inventory 与 installed-wheel smoke 通过；
- ScienceFlow 已精确锁定已推送的 InquiryCraft commit。剩余工作只有 H200 上的 Circle、Nomad
  和 TFBind8 三个 `w2-1h` case 及其 evidence 回填。

## 1. 结论先行

V4 只完成了 ScienceFlow 内部的功能族聚合。V5 现已完成 Agent Runtime 所有权迁移：
InquiryCraft 执行唯一 turn loop，ScienceFlow 只注入科学工作流领域扩展。

V5 的核心目标是：

1. InquiryCraft 成为唯一的通用 Agent Runtime；
2. ScienceFlow Runtime 只负责科学工作流，而不再维护第二套 agent loop；
3. ScienceFlow 通过 typed Hook、Policy、Context Transformer 和 Tool Policy 注入领域语义；
4. Single Worker 与 Multi Worker 使用同一个 InquiryCraft Agent Runtime，差异只存在于
   ScienceFlow 的 worker 外部协调层；
5. 完成迁移后删除 `HostedAgentRuntime` 迁移桥用法、`runtime_backend=legacy`、
   `_run_scienceflow_policy_loop` 及 ScienceFlow 内通用 Agent Runtime 实现；
6. Prompt、Memory、Tool、Stage、Gate、Evaluator、Resource、EStra 和最终 artifact 的可观察
   行为保持不变，本轮不做算法优化。

V5 不是继续移动文件，而是重新确认代码所有权并删除重复执行核心。

## 2. 实施前事实审计（基线）

本节保留 2026-08-29 实施前快照，用于解释迁移范围；“当前”均指基线提交 `72b2ec4`，
实施后的事实以第 0 节和第 11 节验收证据为准。

### 2.1 `scienceflow.agent`

当前规模：99 个 Python 文件、20,104 行。

| 子域 | 文件数 | 行数 | 当前判断 |
|---|---:|---:|---|
| `context` | 19 | 5,660 | 大部分是通用上下文、压缩、source/provider projection，应下沉 |
| `runtime` | 19 | 3,108 | 第二套 agent loop，应由 InquiryCraft `AgentRuntime` 替代 |
| `tooling` | 9 | 2,227 | 通用工具执行与恢复应下沉，ScienceFlow 仅保留领域 policy |
| `llm` | 6 | 714 | pool/retry/usage/stream 属于 InquiryCraft，ScienceFlow 只保留配置映射 |
| `components` | 11 | 2,015 | construction、path、compaction、workspace 行为混合，需要拆 owner |
| `policies` | 6 | 2,010 | 通用 guard 与 ScienceFlow 领域判断混合，需要拆分 |
| `run_control` | 2 | 1,429 | MLEBench/full-run 领域逻辑，应移至 `solver`/`quality`，不属于 Agent |
| `memory` | 4 | 749 | replay/消息处理应下沉，resource feedback 属于 ScienceFlow State/Control |
| `skills` | 7 | 629 | 通用 registry/tool 应下沉，任务 allowlist 留在 ScienceFlow |
| `prompts` | 3 | 421 | ScienceFlow prompt 与 write coaching 保留为领域组件 |
| `io` | 3 | 392 | 通用 interaction event 归 IQ，ScienceFlow 格式/关联信息归 Observability |
| `factory` | 3 | 131 | 应保留并变成薄 composition adapter |
| 根目录其他 | 5 | 559 | agent facade、registry、callback ports、run policy 逐项消除或迁移 |

至少 `context + runtime + tooling + llm` 共 11,709 行处在 InquiryCraft 已声明拥有的
通用能力域，但这些文件内部混有 LNR、result.md、solution.py、Resource/EStra 和 stage 语义，
不能按目录整体搬迁。按 2026-08-29 复核，预计有 8,000--12,000 行可以通过“由 IQ 替代、
下沉通用机制、或迁回 SF 领域 owner”移出 `scienceflow.agent`；其中真正新增到 IQ 的代码量会
明显小于移出量，因为 IQ 已经具备 Message、Memory、ToolExecutionEngine、ContextPipeline、
AgentRuntime、journal、queue 和 process primitives。最终数字以 V5-0 逐文件矩阵为准。

### 2.2 当前并没有真正使用 InquiryCraft `AgentRuntime`

当前调用链是：

```text
ScienceFlow Orchestrator / AgentFactory
  -> ScienceAgent
  -> InquiryCraft HostedAgentRuntime.run(callback)
  -> ScienceFlow _run_scienceflow_policy_loop()
  -> ScienceFlow context / LLM / tool / recovery / memory
```

`HostedAgentRuntime` 只管理 state、cancellation 和 lifecycle event。它是迁移桥，不执行
InquiryCraft 自己的 `AgentRuntime._complete_turn()`、context pipeline 或 tool pipeline。
因此 `runtime` 与 `legacy` backend 目前主要是同一 ScienceFlow loop 外是否包一层 lifecycle，
并不代表两个独立实现已经完成切换。

真实代码证据：

- `scienceflow/agent/runtime/run_loop_components/completion.py` 在 `runtime` backend 下调用
  `HostedAgentRuntime.run(lambda: self._run_scienceflow_policy_loop(...))`；
- `scienceflow/agent/components/construction_runtime.py` 构造的是 `HostedAgentRuntime`，不是
  `AgentRuntime`；
- IQ `runtime/hosted.py` 的模块说明明确称其为 migration bridge，domain callback 仍独占 prompt、
  memory 和 workspace effects；
- 现有 `tests/test_runtime_backend_switch.py` 因而验证的是生命周期包装前后的行为等价，而不是
  ScienceFlow loop 与 IQ `AgentRuntime` 两套实现的独立等价。

### 2.3 跨仓依赖与重复实现审计

ScienceFlow 当前共有 97 条 `inquirycraft` import，分布在 66 个 Python 文件中，说明公共能力
下沉已经开始，但 owner 收口没有完成。主要现象如下：

1. **直接 facade/adapter**：`agent/llm/reasoning_compat.py`、`agent/tooling/base.py`、
   `runtime/process/utils.py` 等只是在转发 IQ 能力；
2. **带默认配置的薄 wrapper**：`agent/llm/key_pool.py` 在 IQ `KeyPool/PooledLLM` 外注入 SF logger、
   env/default retry；应改为 factory/options，而不是保留继承层；
3. **部分下沉**：`agent/llm/runtime.py` 已调用 IQ 的 message record、repair、rewrite、prune、
   workspace prefix 和 LLM factory，但仍保留 SF stage/route/workspace clone 规则；
4. **机制已下沉、执行仍重复**：SF 已调用 IQ `SameRoundRetryPolicy`、
   `classify_tool_call_bundle`、`ToolExecutionEngine`，但 same-round retry loop、bundle dispatch 和
   execution side effects 仍在 SF；
5. **private implementation import**：仍存在 `inquirycraft.llm.online` 和
   `inquirycraft.memory.kv_storage` 的直接依赖；V5 必须改成 IQ public export/contract；
6. **通用机制夹带领域策略**：`tooling/execution/single.py`、`parallel_bash.py`、context clone/
   compaction、guards 同时包含通用执行和 result.md/solution/LNR 语义，需要先切 decision port，
   不能整体复制到 IQ；
7. **IQ 内的反向领域泄漏风险**：IQ `GuardManager` 中存在依赖特定 guard 名称的 no-progress
   行为，应改为通用 capability/decision，不继续增加名称魔法。

本轮审计没有修改代码。使用两个仓库锁定的 `uv` 环境完成定向基线：

- InquiryCraft runtime/tool/process：49 passed；
- ScienceFlow runtime backend parity：5 passed；
- 两个工作树均 clean；
- 本结果仅是本地 contract baseline，不替代 V5 完成后的三个远端 case。

### 2.4 `scienceflow.runtime`

当前规模：43 个 Python 文件、5,798 行。

| 子域 | 文件数 | 行数 | V5 owner 决策 |
|---|---:|---:|---|
| 根模块 | 7 | 1,275 | `orchestrator` 拆除；composition/environment/task package 保留 |
| `parallel` | 14 | 1,828 | ScienceFlow 工作流所有，保留 |
| `process` | 10 | 1,005 | 通用 session/stream/lifecycle 下沉 IQ；SF 只留领域 adapter/policy |
| `kernel` | 4 | 809 | dispatcher/engine 机制与领域 Run/Worker 状态拆分 |
| `stage` | 4 | 562 | ScienceFlow stage transaction，保留 |
| `support` | 4 | 319 | 按 Workspace/Resource/Artifact owner 重新归位 |

这里必须区分两种 Runtime：

- **Agent Runtime（InquiryCraft）**：一个 agent session 内的 model turn、provider、tool、
  context、memory、resume、cancellation 和 agent event；
- **Workflow Runtime（ScienceFlow）**：Run、Worker、Stage、candidate transaction、deadline、
  resource lease、Gate/Evaluator/Finalization 与多 worker 协调。

V5 只下沉前者。不能把 MLEBench、LNR stage、资源分配或 Gate 规则放入 InquiryCraft。

## 3. 所有权原则

采用以下判定顺序：

1. 不知道 ScienceFlow、LNR、MLEBench、Stage、Gate、Evaluator 或 Resource lease 也能成立的
   Agent 能力，归 InquiryCraft；
2. 描述一次科学任务如何分 stage、产生 candidate、评估和提交 artifact 的能力，归
   ScienceFlow；
3. 通用机制与领域 enum/payload 混在一起时，机制下沉，领域 schema 留在 ScienceFlow；
4. ScienceFlow 只通过 InquiryCraft 公共 API 依赖它，禁止 private import；
5. InquiryCraft 绝不依赖 ScienceFlow；
6. Hook 负责提供领域决策，Runtime 负责按确定顺序执行，不允许 Hook 复制主循环；
7. Memory、Resource、Gate、Evaluator、EStra 可以独立演化，但必须通过 versioned contract
   接入，不得反向侵入 InquiryCraft engine；
8. 迁移不能借机修改 prompt 内容、上下文优先级、停止策略或评分逻辑。

## 4. 目标架构

```text
ScienceFlow CLI / Solver / Parallel Coordinator
                 |
                 v
        ScienceFlow Workflow Runtime
        Run -> Worker -> Stage -> Finalization
                 |
          AgentSessionPort
                 |
                 v
        InquiryCraft AgentRuntime
   +-------------+-------------+-------------+
   | LLM pipeline| Tool runtime| Conversation|
   | retry/stream| exec/replay | context/mem |
   +-------------+-------------+-------------+
                 ^
                 |
       ScienceFlow typed extensions
   Prompt | Context Transformer | Hooks | Policies
   LNR/Resource/Workspace/Telemetry/Gate observations
```

关键约束：

- InquiryCraft `AgentRuntime` 是唯一 turn loop；
- ScienceFlow 不再继承一组 execution mixin 组成第二个 Agent；
- Agent Runtime 只返回 typed result 和 event，不直接调用 Gate/Evaluator；
- Stage coordinator 决定何时创建 agent session、何时评估 candidate；
- Single/Multi Worker 的 agent session 构造完全一致；Multi Worker 只额外拥有进程、CPU/GPU、
  deadline、汇合和 finalization 协调。

## 5. 通用 Agent Runtime 能力清单与下沉设计

### 5.1 Session 与 turn loop

InquiryCraft 统一拥有：

- session start/resume/complete/fail/cancel；
- round/turn 状态；
- provider request -> assistant message -> tool execution -> tool message；
- max-turn 与 Stop Policy；
- steer/follow-up queue；
- operation lock、终态提交和 exactly-one terminal record。

ScienceFlow 提供：

- `ScienceFlowStopPolicy`，表达 LNR budget、no-progress、stage reserve 等领域条件；
- `ScienceFlowAgentHooks`，注入 stage/resource/workspace/telemetry 事件；
- task/stage prompt 和 typed metadata。

删除目标：`_run_scienceflow_policy_loop`、`RunLoopMixin`、round-loop components 以及
`runtime_backend` 双路径。

### 5.2 LLM provider、stream 与 retry

InquiryCraft 统一拥有：

- OpenAI-compatible adapter；
- endpoint/key pool、sticky routing 与 failover；
- tool-call streaming decode；
- reasoning replay compatibility；
- empty stream、timeout、repetition 的同轮 retry；
- usage/cached-token/TTFT/TPOT 观测；
- client close 生命周期。

ScienceFlow 只保留 `Config -> InquiryCraft LLM options` 映射，以及把 provider observation
转为 ScienceFlow time trace 的 observer。不得保留第二份 HTTP/pool/retry 实现。

当前缺口：IQ 已有 `SameRoundRetryPolicy`，但 `RuntimeLLMPipeline` 尚未执行 SF 当前具备的
same-round retry、empty tool stream retry、reasoning replay 注入和 repetition nudge。因此迁移
顺序必须是先把通用 retry executor 接入 IQ pipeline，再删除 SF `llm_retry.py`；不能只删除
SF wrapper 或只复用 policy 对象。

### 5.3 Conversation、Memory 与 resume

InquiryCraft 统一拥有：

- `Message`/tool-call schema；
- factual conversation store；
- append、load、resume point inspection；
- pending tool 的安全恢复；
- operation journal 与 provider-context checkpoint；
- reasoning/tool result 的通用持久化。

ScienceFlow 保留：

- Workspace stage cards、candidate facts 和 resource observation；
- 将这些事实投影为 protected/pinned context 的 transformer；
- stage 间允许继承哪些事实的领域规则。

原则：Workspace/Stage record 是 ScienceFlow 事实源，Conversation 是 InquiryCraft 事实源；
两者通过稳定 ID 和 hash 关联，不能互相偷偷改写。

### 5.4 Context projection 与 compaction

InquiryCraft 统一拥有：

- source conversation 到 provider context 的 pipeline；
- ordered transformer；
- token estimate/provider usage 校准；
- protected prefix、retained tail 与 deterministic compaction；
- source/provider 双视图 checkpoint；
- tool-call/tool-result 完整性约束；
- provider-specific system-message projection。

ScienceFlow 保留 transformer：

- task description、environment 和 stage prompt；
- LNR fresh-workspace/stage hints；
- Resource/EStra/Workspace facts；
- hidden path 和 artifact visibility 的领域规则；
- clone/fork 时的 stage inheritance policy。

现有 `scienceflow.agent.context` 不整体搬家。先将通用算法与 IQ 现有 `ContextPipeline` 对齐，
再把剩余 ScienceFlow 规则改写为无状态或显式状态的 transformer。

### 5.5 Tool runtime

InquiryCraft 统一拥有：

- tool schema、argument validation 与 dispatch；
- sequential/concurrent execution；
- preflight/postprocess Hook；
- cancellation、timeout、stream update；
- interrupted tool replay policy；
- lossless raw output store、reducer、dedupe、traceback/size hygiene；
- file `PathPolicy`、write/edit safety 与通用 stale-read guard；
- tool result 到 conversation 的规范化。

ScienceFlow 保留：

- 哪些工具对某个 task/stage 可见；
- bare solution run、quick test、full run 的领域分类；
- candidate artifact 捕获；
- Resource observer、GPU policy 和 execution-value observation；
- safety veto 的领域配置。

现有 `single/sequential/parallel_*` mixin 必须由 IQ ToolExecutionEngine 替代，不能只改 import。

当前缺口：IQ `RuntimeOptions.tool_execution` 只有全局 `sequential/parallel`，而 SF 每个 tool-call
bundle 需要动态区分 `single`、`parallel_readonly`、`parallel_bash`、
`blocked_write_edit_bundle` 和 `sequential`。IQ 已有 `classify_tool_call_bundle`，V5 应新增
`ToolBundleExecutionPolicy` 并由 `RuntimeToolPipeline` 统一执行；SF 只提供 readonly/mutation tool
集合、bash-safe predicate 和 result.md pending 时的领域 veto。

### 5.6 Guard 与 Policy

需要拆成两层：

- IQ：重复失败、输出 mimicry、通用 write/edit/path/shell safety、retry/terminate decision；
- SF：未生成有效 solution、quick-test 价值、stage budget、artifact readiness、MLEBench
  submission 和资源约束。

IQ 提供通用 `ToolPreflightDecision`、`ToolPostprocessDecision` 和 Stop Policy contract；
ScienceFlow 的策略只返回 decision，不直接执行工具或修改 Runtime 内部状态。

### 5.7 Skills

若 skill discovery、registry、matching、injection 和 `SkillTool` 不引用 ScienceFlow task schema，
则作为可选 `inquirycraft.skills` 能力下沉。ScienceFlow 只保留 task-type allowlist、stage 可见性
和默认 skill library 配置。

若审计发现某项只服务 LNR stage，则保留在 ScienceFlow prompt/state，而不是为追求目录缩小
强行通用化。

### 5.8 Event、Hook、Telemetry 与 cancellation

InquiryCraft 统一拥有 agent lifecycle event、ordered hook execution、cancellation propagation、
provider/tool correlation 和 event sink。

ScienceFlow 继续拥有 Run/Worker/Stage event、Gate/Evaluator/Resource observation 与最终 audit。
两层事件通过 `session_id/run_id/worker_id/stage_id` 关联，但保持各自 schema owner。

ScienceFlow 当前 `runtime.kernel.HookDispatcher` 的 priority、timeout、failure mode、idempotency 和
trace 机制具有通用价值。V5 将其机制合入 IQ 的 Composite Hooks；`HookPoint.RUN_*`、Worker/Stage
payload 仍留在 ScienceFlow Workflow Runtime。

## 6. `scienceflow.runtime` 逐模块决策

| 当前模块 | 目标处理 | 原因 |
|---|---|---|
| `runtime/orchestrator.py` | 拆分并删除 | 混合 prompt、LLM、memory、agent factory 与 solver dispatch |
| `runtime/composition.py` | 保留 | ScienceFlow 领域 composition root |
| `runtime/environment.py` | 保留或归 Config | Host 环境映射，不属于 Agent engine |
| `runtime/message_bus.py` | 用 IQ queue/event 替代后删除 | 通用 agent 消息机制重复 |
| `runtime/events.py` | 拆成 IQ agent event adapter + SF workflow event | 避免双 event truth |
| `runtime/task_package.py` | 保留 | ScienceFlow task/evaluator provider 领域能力 |
| `runtime/parallel/*` | 保留并收紧 owner | 多任务/多 worker 科学工作流协调，不下沉 IQ |
| `runtime/stage/*` | 保留 | Candidate transaction 和 stage lifecycle 是 SF 领域逻辑 |
| `runtime/process/contracts.py` | 通用 contract 下沉 IQ | 文件自述即为 domain-neutral |
| `runtime/process/session.py` | 下沉 IQ | spawn/stream/timeout/cancel/cleanup 是通用执行 session |
| `runtime/process/streams.py` | 下沉 IQ | 通用 stdout/stderr sequencing/pump |
| `runtime/process/lifecycle.py` | 下沉 IQ | 通用 process lifecycle；SF 只订阅 observation |
| `runtime/process/adapters/*` | IQ 接管后删除 | 适配自身公共 API 的 SF wrapper 没有长期价值 |
| `runtime/process/commands.py` | 拆分 | 通用 shell 分类归 IQ；solution/quick-test 分类归 SF Control/Quality |
| `runtime/kernel/hooks.py` | 机制下沉，领域 hook schema 保留 | 通用 dispatcher 与 Run/Worker HookPoint 分离 |
| `runtime/kernel/state_machines.py` | engine 可复用；Run/Worker enum 留 SF | 状态机机制与领域状态分离 |
| `runtime/kernel/journal.py` | 与 IQ journal 对齐，SF projection 留 SF | 不能混淆 agent operation 与 workflow transaction |
| `runtime/support/node_paths.py` | 归 State/Workspace | 路径 owner 不是 Runtime |
| `runtime/support/system_resources.py` | 归 Control/Resources | CPU/GPU 选择是资源组件 |
| `runtime/support/artifact_io.py` | 归 State/Workspace 或 Quality | artifact 稳定性检查是产物 contract |

V5 完成后，`scienceflow.runtime` 表示 Workflow Runtime，而不再是通用代码收容目录。

## 7. InquiryCraft 需要补齐的公共扩展面

实施前先用现有公共 API 做最小适配。只有确有缺口时才新增以下能力：

1. 每轮或首轮 `ToolChoicePolicy`；当前 `_completion_request()` 固定使用 `auto`；
2. versioned `TurnDecision/StopPolicy`，能够表达 continue、terminate、inject、suppress、route 和
   typed termination reason；
3. `SameRoundRetryExecutor`，把 retry policy、reasoning replay、empty stream、repetition guard、
   timeout/cancellation 与 journal/event 组合进 IQ LLM pipeline；
4. `ToolBundleExecutionPolicy`，按一次 provider response 动态选择 parallel/sequential/block；
5. provider call observation，包括 route、usage、retry、TTFT/TPOT 和 failover；
6. typed `ContextProjectionRequest/CompactionDecision`，携带 source/provider view、token estimate、
   protected segments、compaction reason 和 checkpoint metadata；
7. protected/pinned context、tool-call pairing integrity 和可重放 compaction checkpoint；
8. clone/fork conversation projection，但不能复制 Workspace、LNR 或 stage 领域逻辑；
9. Hook dispatcher 的 priority、timeout、failure mode、idempotency 和 trace；
10. process execution session 的 typed request/outcome/stream observation；
11. 可选的通用 skill registry/tool；
12. tool execution record 中稳定的 replay、raw artifact 与 termination metadata；
13. workspace 切换不通过修改活动 Runtime 内部状态实现；clone/teleport 默认创建新
    `AgentRuntime`，显式继承 Conversation projection 和 ScienceFlow stage metadata。

### 7.1 公共接口实施结果

| IQ 公共接口 | 当前状态 | 阻塞的 SF 删除项 | 完成条件 |
|---|---|---|---|
| `ToolChoicePolicy` | 已完成 | first-round tool choice、model turn glue | fixture 与 full parity 通过 |
| `TurnDecision/StopPolicy` | 已完成 typed decision 与 exhaustion policy | text-only handling、loop completion | reason、注入与终态 contract 通过 |
| `SameRoundRetryExecutor` | 已接入 IQ LLM pipeline | SF `llm_retry.py`、reasoning facade | retry/usage/event contract 通过 |
| `ToolBundleExecutionPolicy` | 已接入 IQ tool pipeline | SF parallel/sequential mixins | bundle mode 与副作用顺序 parity 通过 |
| Rich context decision | IQ ordered pipeline 完成；SF 仅保留领域 projection | SF context manager/compaction loop | source/provider/workspace parity 通过 |
| Managed Hook dispatcher | 已完成 priority/timeout/failure/idempotency | SF 通用 dispatcher | managed-hook contract 通过 |
| Process execution session | 已完成 typed session/stream/outcome | SF `runtime/process` 通用主体 | timeout/cancel/drain/cleanup contract 通过 |
| Provider observation | 已完成 route/attempt/usage/latency observation | SF usage/route/monitor glue | telemetry contract 通过 |

这些接口已由 InquiryCraft 公共 API 提供，ScienceFlow 不再维护临时的通用执行实现。

新增 API 必须：

- 位于 `inquirycraft.runtime`、`inquirycraft.llm`、`inquirycraft.memory`、
  `inquirycraft.tools` 或明确的可选 package；
- 写入 `HOST_EXTENSION_API.md` 和 `ARCHITECTURE.md`；
- 有 unit/integration/contract tests；
- 保持 IQ 文件不超过 350 行、函数不超过 120 行的现有门禁；
- 不出现 `scienceflow`、LNR、MLEBench、Gate 或 evaluator 名称；
- 先提交并推送 IQ，再由 ScienceFlow 精确 pin 对应 commit。

## 8. ScienceFlow 最终 Agent 形态

建议目标结构：

```text
scienceflow/agent/
├── __init__.py
├── factory.py                 # 构造 IQ AgentRuntime
├── session.py                 # AgentSessionPort adapter
├── options.py                 # Config -> IQ options
├── hooks/
│   ├── lifecycle.py           # LNR/stage hook
│   ├── resource.py            # resource observation
│   ├── telemetry.py           # ScienceFlow trace bridge
│   └── workspace.py           # workspace facts/checkpoint bridge
├── context/
│   ├── task.py                # task/environment projection
│   ├── stage.py               # stage/resource/EStra projection
│   └── inheritance.py         # clone/fork domain policy
├── policies/
│   ├── stop.py                # ScienceFlow stop decision
│   ├── tools.py               # task/stage tool visibility
│   └── artifacts.py           # candidate capture policy
└── prompts/
    ├── system.py
    └── coaching.py
```

这是 owner 示意，不要求机械保持文件名。硬目标是：

- 不含 agent loop；
- 不含 LLM client/pool/retry 实现；
- 不含 tool executor；
- 不含通用 Memory/Context 实现；
- 不含 MLEBench full-run executor；
- 不通过大量 mixin 重新组装 Runtime；
- 只包含可解释的 ScienceFlow adapter、Hook、Policy、Transformer 和 prompt。

目标规模：不超过 24 个 Python 文件、4,000 行；如果领域 Hook 能进一步归入其 owner 组件，
应降至 3,000 行左右。规模只是结果门禁，不能通过搬到别的 ScienceFlow catch-all 伪造达标。

## 9. 分阶段实施

### V5-0：冻结行为基线和 owner 清单（完成）

产物：

- 99 个 agent 文件和 43 个 runtime 文件的逐文件 owner/migration matrix；
- provider-visible request、tool call/result、conversation、compaction、callback 顺序 fixture；
- Circle/Nomad 已有 workspace 的 replay 基线，以及 SciModelingBench TFBind8 的 provider、
  query-budget、artifact contract fixture；
- 三个不可变的 V5 验收 manifest：
  `scienceflow/foundation/config/profiles/acceptance/v5/circle_packing_w2_1h.yaml`、
  `nomad2018_deep_w2_1h.yaml`、`tfbind8_w2_1h.yaml`；三者统一设置
  `lnr.wall_clock_budget_sec=3600`、`num_workers=2`、`seed=2222`，不得复用现有 15 分钟、
  2 小时或 12 小时示例；
- Single Worker、Multi Worker、REPL、resume、clone/fork 的调用图；
- 明确哪些差异允许 normalize：仅 UUID、墙钟时间、临时绝对路径和进程号。

新增 `AgentRuntimeTrace@1`，至少记录：

- source conversation hash；
- provider messages hash；
- system/user/tool message 顺序；
- tool name/arguments/result hash 与执行顺序；
- context checkpoint hash；
- hook/stop/retry decision；
- token/route observation；
- workspace source/artifact hash；
- terminal reason。

### V5-1：InquiryCraft 补公共 API（完成）

只在 IQ 仓库实施通用能力和 contract tests，不改 ScienceFlow 算法。优先复用现有
`AgentRuntime`、`AgentHooks`、`ContextPipeline`、`RuntimeToolPipeline`、operation journal、
queue、process 和 event 能力。

实现优先级固定为：

1. `ToolChoicePolicy + TurnDecision`，先让 IQ loop 能表达 SF 当前轮次语义；
2. `SameRoundRetryExecutor + provider observation`，收口 LLM 生命周期；
3. `ToolBundleExecutionPolicy`，收口 single/sequential/parallel 执行骨架；
4. rich context/compaction decision，承接 protected/pinned/clone projection；
5. managed Hook dispatcher 和 process session；
6. public export、文档、contract tests 和 release artifact。

其中 1--4 未完成前，不允许开始物理删除 SF run-loop components。

完成后：

- 更新 IQ Host API 文档；
- 构建 wheel/sdist 并做 installed-package smoke；
- 推送 IQ commit；
- ScienceFlow pin 精确 commit 并更新 lock。

### V5-2：构造 ScienceFlow typed extensions（完成）

新增薄层：

- `ScienceFlowAgentSessionFactory`；
- `ScienceFlowAgentHooks`/Composite hooks；
- task/stage/resource/workspace context transformers；
- Stop Policy、Tool Visibility/Artifact Policy；
- telemetry/provider observation adapter。

使用 scripted LLM 和 recorded replay 做新旧 trace 对比。禁止为了 shadow validation 对真实
vLLM 请求执行两遍，避免成本和非确定性污染。

领域扩展按以下 owner 落位：

- LNR/result.md/solution.py/quick-test/full-run decision：SF Control/Quality；
- Resource/EStra observation 和 budget decision：SF Resources/Control；
- task/stage/workspace/clone inheritance：SF State/Workspace transformer；
- candidate readiness、Gate/Evaluator 调用：SF Quality/Workflow Runtime；
- 通用 hook 执行、LLM/tool/context/process lifecycle：IQ Agent Runtime。

### V5-3：切换 REPL 与 Single Worker（完成）

先切 REPL/single session 到 IQ `AgentRuntime`：

- provider-visible prompt byte parity；
- tool call/result parity；
- memory load/resume parity；
- write/edit/bash/path safety parity；
- cancellation、timeout、retry 和 close parity；
- candidate artifact 与 workspace hash parity。

临时开关只服务迁移测试，不能作为长期双 backend 产品接口。

### V5-4：切换 Multi Worker、clone、resume 与 stage handoff（完成）

确认所有 worker 复用同一 Agent Session Factory：

- worker 差异通过 immutable `AgentSessionSpec`/metadata 表达；
- coordinator 不进入 agent loop；
- clone/fork 只通过 conversation projection 与 ScienceFlow inheritance policy；
- stage handoff、resource observation、deadline 和 callback 顺序保持；
- Multi Worker 的 process isolation/lease/merge/finalization 仍由 ScienceFlow 管理。

### V5-5：删除 ScienceFlow 第二套 Agent Runtime（完成）

在同一 V5 完成窗口删除：

- `HostedAgentRuntime` 的 ScienceFlow 使用；
- `_run_scienceflow_policy_loop` 与 run-loop components；
- `runtime_backend` 配置、环境变量和 backend parity tests；
- `SingleToolExecMixin`、`SequentialRecoveryMixin`、`ParallelToolExecMixin`；
- ScienceFlow LLM pool/http/retry/usage 重复实现；
- 通用 context/memory/skill/guard 实现；
- callback legacy fallback 和 barrel mixin composition；
- 仅为旧私有路径存在的测试与 facade。

测试不能因删除实现而简单删除：有价值的行为断言迁到 IQ contract test 或 SF extension test。

### V5-6：清理 `scienceflow.runtime`（完成）

- 拆除 `orchestrator.py`，factory/prompt/solver dispatch 各归 owner；
- 下沉通用 process session；
- 用 IQ event/queue/hook 机制替代重复设施；
- 保留并命名清楚 Workflow Runtime 的 Run/Worker/Stage/Parallel；
- 将 support helper 归 Workspace/Resource/Artifact owner；
- 加 AST dependency 和 namespace gate，防止通用 Agent Runtime 回流。

### V5-7：完整验证与远端三个 case（本地完成，远端待执行）

本地与远端分别完成第 11 节门禁。远端继续使用独立 checkout、精确 commit 和远程 vLLM API；
不在本机运行模型服务。固定执行 Circle Packing、Nomad2018 Deep 和 SciModelingBench
TFBind8 三个 case。

### V5-8：文档、发布物与提交（IQ 完成，SF 待远端 evidence 收口）

- 更新 ScienceFlow 架构说明和 IQ Host API；
- 生成 V5 migration map、API inventory、wheel inventory 和 evidence manifest；
- 两仓分别原子提交并推送；
- 最终 ScienceFlow lock 只指向已推送的 IQ commit；
- 删除迁移开关，确认工作树干净。

## 10. 提交和依赖顺序

建议提交序列：

1. `InquiryCraft: add generic runtime extension contracts`
2. `InquiryCraft: add process session and hook/context gaps`
3. `InquiryCraft: document and validate host API`
4. `ScienceFlow: pin InquiryCraft runtime contract commit`
5. `ScienceFlow: add typed agent extensions and trace parity`
6. `ScienceFlow: switch REPL and single worker to AgentRuntime`
7. `ScienceFlow: switch multi worker, clone and resume`
8. `ScienceFlow: remove hosted/legacy agent loop`
9. `ScienceFlow: consolidate workflow runtime ownership`
10. `ScienceFlow: add V5 evidence and migration docs`

每个提交应可独立测试。跨仓修改不能依赖未推送 commit，也不能依赖本地 editable package。

## 11. 验收门禁

### 11.1 静态结构

- `scienceflow.agent` <= 24 个 Python 文件、<= 4,000 行；
- 不存在 `_run_scienceflow_policy_loop`、`RunLoopMixin`、execution mixin；
- 不存在 ScienceFlow `runtime_backend` 或 `legacy/runtime` agent 切换；
- 不存在 ScienceFlow 自有 LLM pool、通用 tool executor、通用 context compactor；
- `scienceflow.runtime/orchestrator.py` 删除；
- ScienceFlow 只 import InquiryCraft public symbols；
- InquiryCraft source 不出现 ScienceFlow 领域名；
- 不新增 `core`、`utils`、`common`、`misc` 等 catch-all；
- IQ 与 SF 都通过源码规模和 dependency AST gate。
- ScienceFlow 不直接 import `inquirycraft.llm.online`、`inquirycraft.memory.kv_storage` 或其他
  未列入 Host Extension API 的 implementation module；
- IQ Guard/Runtime 不通过 guard 名称、ScienceFlow metadata key 或其他字符串魔法触发领域行为；
- Single/Multi Worker 不出现两套 AgentRuntime service/factory，只允许 immutable session spec 不同。

### 11.2 确定性行为

- frozen system prompt、task prompt 和 stage prompt byte-identical；
- provider-visible message role/order/tool pairing 一致；
- tool arguments、result normalization、raw artifact SHA 一致；
- context protected prefix、compaction boundary、checkpoint/replay 一致；
- retry、recovery、stop reason 与 callback order 一致；
- workspace/candidate/final artifact contract 一致；
- Full runtime parity 的 context/mechanism/workspace diff 全部为 0；
- 任何批准差异必须进入 versioned normalization manifest，不能写模糊 ignore。

### 11.3 两仓测试与发布物

- InquiryCraft full pytest、Ruff、contract tests、wheel/sdist smoke 全通过；
- ScienceFlow full pytest、Ruff、dependency check、runtime parity 全通过；
- ScienceFlow source checkout 和 installed wheel 都能运行 CLI/agent/runtime imports；
- wheel 不包含已删除的旧 agent loop/facade；
- 新 IQ 公共 API 在 Host API 文档和 `__all__` 中一致；
- ScienceFlow `uv.lock` 的 IQ commit 与远端 origin 精确一致。

### 11.4 远端功能验证

固定三个 case：

- Circle Packing：2 workers、`wall_clock_budget_sec=3600`、seed 2222；
- Nomad2018 Deep：2 workers、`wall_clock_budget_sec=3600`、seed 2222；
- SciModelingBench TFBind8：`sci-modeling-bench-tfbind8`，2 workers、
  `wall_clock_budget_sec=3600`、seed 2222、`gpu_list=cpu`、`omp_threads_cap=4`；专用 manifest
  include `scienceflow/foundation/config/sci_modeling_bench.yaml` profile；
- 三个 case 均使用远端 vLLM API，不在本机启动模型；CPU 分区互斥。

时间口径统一如下：

- “1 hour”只指 agent 可用于探索、训练、验证和产出 candidate 的 wall-clock budget，三个 case
  均精确为 3,600 秒；
- launcher/scheduler 可设置最多 4,200 秒的外层 watchdog，仅用于启动、Stage commit、
  deterministic finalization、evidence 落盘和进程清理；这 600 秒不得暴露给 agent，也不得增加
  LLM/tool/实验预算；
- manifest 和 evidence 必须同时记录 `experiment_budget_sec=3600` 与外层 watchdog，报告实验
  时统一标记为 `w2-1h`；
- 不直接修改或复用当前 15 分钟 Circle、12 小时 Nomad 和 2 小时 TFBind8 配置，避免历史配置
  名称与实际预算不一致。

执行分两波，避免三个任务争用同一 CPU/LLM 预算：

1. 第一波并发运行 Circle（CPU 0--15）与 Nomad（CPU 16--31）；
2. 第一波清理门禁通过后，第二波运行 TFBind8（CPU 0--15，CPU-only evaluator）；
3. 每个 case 使用独立 checkout 下的新 workspace/run id，不允许 resume V4 或旧实验目录。

TFBind8 运行前增加数据准备门禁：

```bash
uv sync --frozen --extra scientific-design
uv run python tasks/sci_modeling_bench/_shared/prepare_data.py \
  --task-id sci-modeling-bench-tfbind8 \
  --output-dir /home/mingming/miing_data/sci_modeling_bench/tfbind8
```

数据已于 2026-08-29 使用精确 ScienceFlow 提交 `72b2ec4` 完成准备并通过静态完整性检查。
正式稳定副本为：

```text
/home/mingming/miing_data/sci_modeling_bench/tfbind8/public
```

checkout 内同时保留一份内容完全一致的 preparation cache，但 V5 新 checkout 的 manifest
必须显式把 `input_data_dir` 指向上述稳定 public 路径，不能依赖旧 checkout。正式运行前只读
复核以下内容；若全部匹配则不得无理由重新下载或覆盖：

- public input 位于稳定路径，且只有 `dataset_manifest.json`、`dataset_files.json`、
  `task_contract.json`、`views/observations.parquet` 四个文件；
- Dataset revision 精确为 `d8b9ea3c78ed33edf0869a427940a0651eb49f52`；
- protocol 为 `design-bench/tfbind8-bottom-percentile-v1`；
- observations parquet 为 32,768 行，列严格为 `sequence, normalized_e_score`，SHA-256 为
  `b2d7f7308a48f76e47ec1dfb71e3282045f89c732e78a3402e664d07230b98f5`；
- 32,768 个 sequence 全部唯一，均为只含 `A/C/G/T` 的合法 8-mer；
- validation submission 为 32 个唯一合法 8-mer；
- hidden outcomes、evaluator state 和 lookup cache 不暴露在 agent-visible `public/` 中。

必须满足：

- launcher exit 0；
- worker 无 framework crash；
- Stage transaction 合法、无重复 commit；
- correlation journal 无 malformed/duplicate ID；
- resource job/waiter/GPU lease 在退出后为 0；
- 无残留 ScienceFlow task/process；
- provider/system-message 配置显式记录；
- merge-agent timeout 可由既有 deterministic finalization 收口，但 agent status 与 task status
  必须分开记录。

Case-specific artifact/evaluator 门禁：

- Circle：3/3 valid finals；每个 artifact 含 26 个 finite、non-negative circles，SHA 和
  manifest 一致，几何约束在 evaluator tolerance 内，并重新计算 `radii_sum`；
- Nomad：3/3 valid final CSV；每份 240 行，列、ID、finite/non-negative 和 SHA 校验通过；
- TFBind8：`artifacts/submission.json` 含且仅含 32 个互异大写 DNA 8-mer，只允许
  `A/C/G/T`；至少一个 high-validity、candidate-ready、evaluation-eligible 的 best-stage final，
  artifact SHA 与 manifest 一致，authoritative `best_k_mean` 为 finite 且方向为 maximize；
- TFBind8 每 worker 最多 10 个不同 candidate batch 获得 official evaluation；相同 canonical
  candidate batch 必须命中 query cache 且不重复扣减；query ledger 的 owner/scope 必须保持
  worker 隔离；
- TFBind8 profile 必须保持 `merge_enabled=false`、`final_artifact_mode=best_stage`，不能套用
  Circle/Nomad 的 global-merge 与 3-finals 验收规则。

分数只记录，不设相对 V4 的性能提升门槛；本轮验证结构与行为，不归因算法性能。

## 12. 风险与控制

### 12.1 上下文细微漂移

风险最高。模型对 system/user 分层、tool pairing、压缩边界和 hidden path 很敏感。

控制：provider request hash、逐轮 role sequence、source/provider 双视图和 byte-level fixture；
不只比较最终回答。

### 12.2 工具副作用被重复执行

新旧实现不可对真实 workspace 做双跑。

控制：scripted/replay parity；IQ operation journal；write tool replay policy；每次远端 case 使用新
workspace；artifact SHA 和 process cleanup gate。

### 12.3 Hook 变成隐藏主循环

控制：Hook 只能返回 decision/observation，不允许自行执行 provider turn、递归调用 runtime 或
拥有 conversation truth；加 AST 和 protocol tests。

### 12.4 把 Workflow Runtime 错误下沉

控制：IQ 禁止出现 Stage、Candidate、Gate、Evaluator、Resource lease、MLEBench/LNR 类型；
这些 contract 永久由 ScienceFlow 拥有。

### 12.5 长期保留双 backend

控制：迁移 flag 只存在于阶段分支；V5 完成条件包含配置、实现和测试同时删除。回滚依靠 Git
提交，不依靠永久 legacy 分支。

## 13. 完成定义

只有以下全部成立，才可宣称 V5 完成：

1. InquiryCraft `AgentRuntime` 是唯一 agent turn loop；
2. ScienceFlow Agent 只剩 adapter/Hook/Policy/Transformer/prompt；
3. ScienceFlow Runtime 只表达 Workflow Runtime；
4. 通用 process、LLM、tool、memory、context、retry、resume 和 cancellation 不再重复实现；
5. Single/Multi Worker 使用同一个 Agent Session contract；
6. 旧 loop、legacy backend、Hosted bridge 用法和 compatibility facade 已物理删除；
7. 两仓测试、parity、wheel 和远端 Circle/Nomad/TFBind8 三个 case 验证全部通过；
8. IQ API 文档、SF migration 文档、精确依赖锁和 evidence manifest 完整；
9. 两仓提交均已推送且工作树干净；
10. 没有把算法改动、prompt 优化或性能调参混入本轮迁移。

此外，下列“看似完成”不计入 V5 完成：

- 仅把 `_run_scienceflow_policy_loop` 再包一层 IQ lifecycle；
- 仅把 SF mixin 改名为 hook，但 hook 内仍执行完整 model/tool loop；
- 只复用 IQ policy/classifier，实际 retry 或 tool bundle executor 仍留在 SF；
- 把通用实现从 `scienceflow.agent` 移到另一个 ScienceFlow catch-all；
- 为通过结构门禁而删除测试、降低断言或长期保留 legacy backend；
- 三个 case 只验证最终文件存在，而没有检查 provider/context/tool/event/artifact contract。

V5 的最终判断标准不是“目录看起来更少”，而是通用 Agent Runtime 只有一个 owner，
ScienceFlow 的每一行 Agent 代码都能解释其科学工作流领域价值。
