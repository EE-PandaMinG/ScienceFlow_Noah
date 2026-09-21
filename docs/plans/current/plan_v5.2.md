# ScienceFlow V5.2 组件压缩与架构收口规划

状态：实施中（2026-08-30 第二批组件和回归门禁已合并；`bench_sf` V1 的 14 个 component 与 2 个 physical GPU point 已全部验证）

基线日期：2026-08-30

ScienceFlow 基线：`49f76f3`（V5.1 验收证据提交；运行时代码基线 `8f6e057`）

InquiryCraft 基线：`51332642b474a87a8808612b9dc06607215f4858`

V5.2 实施起点：`f1fd2b2`（规划、bench 合同与资源审计已推送）

## 1. 结论

V5.1 已完成 ScienceFlow 与 InquiryCraft 的主分层、唯一 Agent Runtime 切换和正式长程验收取证。
V5.2 不再继续做大范围框架迁移，重点转为 ScienceFlow 内部的真实复杂度压缩。

当前代码已经完成“按职责拆文件”，但尚未完全完成“状态、接口与兼容面收口”。V5.2 的目标不是把
代码藏进动态绑定、生成代码或更大的公共上下文对象，而是减少组件真实拥有的状态、方法和跨组件知识。

真实长程机制验证由工作区级独立本地项目 `bench_sf` 维护；本仓库的
[`../../benchmark/bench_sf_v1.md`](../../benchmark/bench_sf_v1.md) 保留规划来源。本文件只定义
架构和实施顺序，canonical registry/case/oracle/scorecard 均以独立项目为准。

### 1.1 本次刷新后的执行基线

- ScienceFlow 架构基线仍为 `49f76f3`；InquiryCraft 已前移到
  `51332642b474a87a8808612b9dc06607215f4858`，以公共 namespace 固化流式 guard、
  Resume 和 shell guard 合同。
- 初始 AST 基线确认 4 个零实现 callable-binding façade：`LnrSolver` 286、`LHRResourceObserver` 212、
  `ScienceAgent` 107、`ResourceRuntime` 67；coordinator 另有 21 个直接业务模块。V5.2
  从“压缩两个大类”升级为统一治理绑定 façade、平铺目录、空壳代理和 `shared.py` 汇聚面。
- canonical `/home/mingming/rsi/codes/bench_sf/registry.yaml` 现登记 16 个 `stable` case：14 个
  component checkpoint 与 2 个 physical GPU point。全部 case 均有同一只读 bundle 的两次独立
  100 分 Resume；两项物理证据使用真实 CUDA，而非 dry-run 或测试探针。
- 已定向审计 6 批 MLEBench GPU 运行：48 个资源事件日志、74,642 条控制面事件、
  15 个历史 reaped lease。审计见
  [`../../benchmark/resource_workspace_audit_20260830.md`](../../benchmark/resource_workspace_audit_20260830.md)。
- 资源类 P0 是 Jigsaw seed3333 的 stale heavy-train owner + `gpu_tt_light`
  test-time inference waiter + 双 pending Tool Call 边界；228 MB bundle 已冻结并完成两次真实
  GPU point Resume。它与 “text-only completion 触发 ESTRA” 是两个不同技术点。
- Circle、Nomad、TFBind8 Worker=2、1 小时验收仍只在发布候选阶段执行；普通切片通过选择
  对应 stable point 验证，不退化为每次全量长跑。

## 2. 当前问题

### 2.1 物理拆分已完成，逻辑收口未完成

| 热点 | 当前规模 | 主要问题 |
| --- | ---: | --- |
| `solver/lnr/orchestration/coordinator/` | 13,356 行、根级 2 个业务文件 | 已按六个 owner 分层；Evaluation 已由四个真实 owner 组合 |
| `coordinator/solver.py` | 234 个 callable descriptor | 两批共移除 52 个绑定，Stage 等有状态 owner 仍待收口 |
| `resource_runtime/observer/` | 约 9,001 行 | 已按六类职责分层，仍需用 Resume 验证跨阶段 effect chain |
| `observer/controller.py` | 0 个 callable descriptor | canonical class 以 16 个职责 owner 显式组合，旧 proxy/bridge 已删除 |
| `resources/runtime/execution/facade.py` | 0 个 callable descriptor | 以 7 个 capability owner 显式组合，行为验收待定 |
| `agent/core/runtime/agent.py` | 68 个 callable descriptor | Session 改用 19 项 typed host port；剩余兼容/领域 binding 待迁移 |
| `agent/session/` | 7 个文件 | 已按 host/context/contracts/runtime/tool-result/turn 分层 |
| `state/dataset/` | 8 个业务模块、2,257 行、最大 676 行 | traversal、metadata、top-level render、flat/nested tree、eval signature 已分层；C901 已清零 |
| `quality/embedded_fullrun.py` | 1,411 行 | full-run 判定、执行、快照和结果投影耦合，最高复杂度 42 |

当前 V5.2 热点范围的 Ruff `C901` 审计发现 58 个复杂度超过 10 的函数。复杂度主要集中在长程状态转换、资源观察、
Embedded Fullrun 和兼容分支；Dataset Scan 的 80/69/25 三个高复杂度流程已清零，不是 InquiryCraft Agent Runtime 的重复实现。

定向测试调用面扫描当前已清零 `object.__new__(LnrSolver)`（26→0），`solver._*` 私有访问
255→186；`observer._*` 仍为 181 处。剩余私有访问继续按 owner 迁移，否则 façade 仍会被测试锁住。

### 2.2 大组件持续存在的原因

1. V3/V5 迁移采用机械 move/extract，优先保持 Prompt、事件顺序、Workspace 和 Resume 行为。
2. coordinator 和 resource observer 的函数虽已分文件，仍把原巨型对象作为隐式服务容器。
3. 大量测试直接构造 `LnrSolver`、修改私有字段或 monkeypatch 私有方法，迫使宽 façade 长期保留。
4. legacy callback、旧 Workspace、旧事件与旧 import 兼容尚未按版本周期清退。
5. 多处使用弱类型 `dict[str, Any]` 传播状态，同一字段在不同阶段反复解析、补全和投影。

### 2.3 目录同时存在平铺和过度碎片化

- coordinator 的 run、stage、evaluation、context、ESTRA、resource 文件全部平铺在同一级，查找职责必须依赖文件名猜测。
- observer 的 `*_bridge.py` 混合 callback、policy、state transition、projection 和 effect；`bridge` 已失去边界含义。
- `observer/controller.py` 只有 12 行，通过替换 `sys.modules` 转发到 `observer.py`，属于可合并空壳。
- coordinator 与 observer 的 `shared.py` 汇聚大量不相关 import，使迁移后仍可继续依赖完整旧语义面。
- `quality/finalization/service.py` 只包装 runner 和若干函数，service 没有真正拥有 orchestration。
- 部分小文件是稳定 contract，不能只因行数少就合并；版本化 request/record、typed ports 和公开模型应保留独立 owner。

## 3. V5.2 目标

### 3.1 架构目标

- `LnrSolver` 只负责 composition、run identity、`run`/`resume` 入口和顶层生命周期。
- Stage、Evaluation、Context、ESTRA、Resource、Finalization 各自拥有状态和接口。
- `LHRResourceObserver` 只保留真实外部 callback；策略、状态机、effects 和 projection 由注入组件拥有。
- ScienceFlow 只使用 InquiryCraft 公共 namespace，不依赖实现模块或私有符号。
- 测试面向组件 contract 和 typed state，不再依赖巨型对象的任意私有 monkeypatch 点。
- 大函数优先拆成纯 decision、typed transition 和独立 effect，保持事件顺序不变。

### 3.2 规模目标

规模是结果门禁，不允许通过隐藏代码或改变行为强行达成。

- 普通业务模块目标为 500–800 行；超出时必须在 owner 文档中解释。
- 新增或重构函数原则上不超过 120 行。
- `LnrSolver` 的生产入口控制在 5 个以内，内部不再绑定数百个方法。
- `LHRResourceObserver` 对外 callback 目标控制在 15–25 个。
- `ScienceAgent` 只保留 Agent host 必需字段和少量稳定入口，不再绑定跨 Quality、Safety、State、Observability 的上百个私有方法。
- `ResourceRuntime` 改为组合 admission、queue、lease、pressure、monitor capability，不再重新绑定全部内部方法。
- coordinator 与 observer 不再以共享宿主 `self` 作为跨组件隐式 API。
- 一个组件包的直接业务模块原则上不超过 8 个；超过时按 owner 建立二级目录，不用编号文件或新的 catch-all 规避门禁。
- ScienceFlow 预计净减少 1,000–2,500 行；如果删行与行为稳定冲突，以行为稳定为先。
- 复杂度超过 20 的函数必须清零或登记有时限的例外。

### 3.3 非目标

- 不修改科研 Prompt、Tool Schema、模型参数、Tool Choice 或调用时机。
- 不重写 Stage、Gate、Evaluator、ESTRA、Resource、Merge 或 Finalization 算法。
- 不把 ScienceFlow 领域策略下沉到 InquiryCraft。
- 不以动态 `setattr`、元类或自动生成绑定表来伪造 façade 变小。
- 不要求每个重构切片重新运行三项 Worker=2、1 小时正式任务。
- 不以“一文件越小越好”为目标；同 owner、无独立 contract/state/effect 的薄包装应合并。

## 4. 目标组件结构

### 4.1 LNR composition

建议将当前 coordinator 收敛为以下协作组件；名称可调整，但 owner 不得重新混合：

| 组件 | 拥有 | 不拥有 |
| --- | --- | --- |
| `LnrSolver` | composition、run identity、顶层 run/resume | Stage/Evaluation/Resource 具体算法 |
| `RunCoordinator` | single/multi worker 生命周期、预算、停止原因 | evaluator、resource policy |
| `StageController` | stage transaction、capture、commit、ledger projection | provider loop、资源 effects |
| `EvaluationController` | evaluator 调用、metric projection、gate request | final artifact 选择、Stage 存储 |
| `ContextController` | stage prompt projection、memory/context hygiene | factual conversation owner |
| `EstraController` | ESTRA request、decision、lineage restore | evaluator 与资源决策 |
| `FinalizationController` | candidate collection、merge、selection、result | worker/provider 生命周期 |
| `ResourceAdvisor` | coordinator 侧资源 context/advisory port | lease store 与 process effect |

不得建立一个包含所有可变字段的 `CoordinatorContext` 来替代旧 `self`。应至少区分：

- immutable configuration；
- run identity；
- stage/lineage state；
- injected ports；
- component-owned mutable state。

### 4.2 Resource Observer

`LHRResourceObserver` 保留 callback adapter 身份，其内部组合：

- `ResourceObservationService`：采样归一化、progress facts；
- `ResourceReviewService`：review state machine 和 history；
- `ResourceSafetyPolicy`：kill/release/continue 安全判定；
- `GpuSharingPolicy`：sharing、contention、revocation；
- `ResourceAdmissionService`：queue/lease admission；
- `ResourceEffectPort`：唯一 effect 执行口；
- `ResourceTelemetryProjector`：事件与 agent feedback 投影。

组件之间传递 typed request/decision，不直接读写另一个组件的内部字典。兼容字段 `_jobs`、
`_queue_started`、`_last_heartbeat` 和 `_leased_gpu_ids` 在测试迁移后删除。

### 4.3 其他大模块

- `dataset/scan.py`：拆成 traversal、format readers、sample policy、tree renderer。
- `embedded_fullrun.py`：拆成 eligibility decision、execution request、result interpreter、snapshot writer。
- `bash/execution_monitor.py`：将 watchdog、resource decision、stream monitor 和 termination effect 分开。
- `agent/session.py`：将 host callback adapter、turn decision 和 tool-result projection 分开；不得建立第二个
  Agent Runtime。

### 4.4 物理目录目标

目录层级必须表达 owner，而不是迁移历史。目标形态如下；实际迁移可分切片完成，但不得重新平铺：

```text
solver/lnr/
  lifecycle/                # stage, records, workspace, and snapshots
  orchestration/
    coordinator/            # evaluation, resource, run, ESTRA, and lifecycle owners
    runtime/                # single/multi-worker execution and services
  resources/
    runtime/
      control/              # admission, GPU, and feedback policy
      execution/            # facade, process facts, stores, and utilization
      observer/             # allocation, assessment, callbacks, and sharing
      review/               # decision and evidence owners
      runtime_components/   # narrow composed capabilities
  support/                  # prompt templates and context helpers
  transitions/              # ESTRA, resume, replay, and restore

agent/
  core/                     # thin runtime implementation and typed host ports
  session/                  # session, hooks, context projection, tool adapter
  factory/                  # public contracts, builder and traced service

quality/finalization/
  service.py                # real orchestration owner
  selection/                # ranking and coverage
  candidates/               # evidence and packing
  artifacts/                # materialization and submission links
```

层级原则：

1. 通常不超过“领域 / 组件 / 子职责”三级；只有存在独立 state、port 或 effect 时才增加目录。
2. `__init__.py` 只导出稳定公共 contract，不建立宽 barrel。
3. `bridge` 只用于真实跨框架或兼容边界；内部 owner 之间使用 port/adapter 的具体名称。
4. V5.2 目标组件中删除 `shared.py`；依赖由模块直接导入，组合所需能力由 typed ports 注入。
5. 测试目录按 owner 镜像，不再把所有行为放入 `test_long_horizon_repl_*` 后通过巨型 façade 调用。

### 4.5 合并与拆分判定

优先合并：

- `observer/controller.py` 与 `observer/observer.py`：公共路径保留，实际 class 直接位于 `controller.py`。
- `agent/factory/construction.py` 与 `construction_runtime.py`：两者共同拥有同一次构造，可收为一个 typed builder。
- `finalization/service.py`、`runner.py` 和 `worker_outcomes.py` 的 service orchestration：消除只转发的 service；纯选择算法仍独立。
- finalization 的 ranking 与 coverage 可收进同一个 `selection` owner，避免多个百行以下策略文件平铺。

必须拆分：

- `coordinator/event_projection.py`：event journal、Workspace 准备、lineage/snapshot index 和 interaction log 不是同一 owner。
- `agent/session.py`：Host adapter、context projection、turn lifecycle 和 tool-result dispatch 分开。
- `dataset/scan.py`：readers、traversal、sample policy、rendering 分开。
- `embedded_fullrun.py`：eligibility、execution、snapshot、result projection 分开。
- `observer/monitor_bridge.py`：采样/事实生成与 review scheduling 分开。
- `resource_runtime/gpu_lease_store.py`：持久化 store、reconciliation 和 scheduling policy 分开，但保持原子事务边界。

不因 helper 同名就跨领域合并。只有语义、错误合同、生命周期和 owner 均一致时才抽取公共实现。

## 5. 实施阶段

### V5.2-0：冻结 owner 与度量

- 记录当前文件行数、method binding 数、复杂度和公开 import。
- 固定 V5.1 runtime parity baseline，不在普通开发中自动重录。
- 建立生产调用面与“仅测试调用的私有方法”清单。
- 为每个目标组件指定 owner、state、ports 和 effects。
- 记录每个 package 的直接业务文件数、`shared.py` import 面、薄代理和 descriptor-binding façade。

完成条件：度量脚本可重复；owner 清单覆盖 coordinator、observer、ResourceRuntime 和 ScienceAgent 全部绑定面。

当前状态：已完成。`tests/support/architecture/v5_2_structure_metrics.py` 可重复生成结构快照和剩余 façade owner matrix；
当前 matrix 有 302 个绑定（`LnrSolver` 234、`ScienceAgent` 68），Observer/ResourceRuntime
已由显式 composition owner 覆盖，不再产生 descriptor 绑定行。

### V5.2-1：公开 API 与过期兼容清理

- 将 `inquirycraft.llm.base`、`runtime.resume`、`tools.shell_guards` 等调用切到公共 namespace。
- 删除当前精确 pin 已覆盖的旧 subprocess/shell fallback。
- 删除无生产消费者且从未承诺公开的 re-export。
- 仍需保留的兼容入口明确 deprecation owner 和删除版本。

验证：dependency boundary、import contract、tool/process contract、runtime parity quick。

当前状态：公共 namespace 与 InquiryCraft 精确 pin 已完成；旧 subprocess/shell fallback 的退役仍待后续切片。

### V5.2-2：测试 seam 迁移

- 将纯函数测试从 `LnrSolver._private_method` 改为直接测试 owner 模块或组件。
- 将 `object.__new__(LnrSolver)` + 手工字段注入改为 typed fixture。
- 将任意 method monkeypatch 改为 port/fake 注入。
- 保留少量 façade contract 测试，只验证公开入口。

这一阶段不应改变生产行为，但它是删除 286/212 个 Solver/Observer 绑定，以及 Agent/ResourceRuntime
绑定面的前置条件。

当前状态：全部 26 个 `object.__new__(LnrSolver)` 已迁移为 owner 直接测试、显式
`RuntimeServices` 或 typed façade fixture，结构度量当前为 0；Solver 私有访问由 255 降至
186。Observer 的 181 处私有访问和剩余 Solver seam 随各 owner 切片继续迁移。

### V5.2-3：LNR coordinator 收口

- 先迁移纯 projection/decision，再迁移有状态 controller。
- 每次只迁移一个 owner，保持 event、lock、filesystem 和 callback 顺序。
- consumer 切换完成后，从 `LnrSolver` 删除对应私有方法绑定。
- 最后删除以 `shared.py` 作为全局 import 汇聚点的模式。
- 按 run/stage/evaluation/context/ESTRA/resource 建立二级 owner，完成后 coordinator 根目录直接业务文件不超过 8 个。

验证：相关 unit/contract、runtime parity full、对应 `bench_sf` Resume 记录点。

当前状态：六个 owner 子包和 Finalization owner 已落地，根级业务文件 21→2；Evaluation
已拆为四个真实 MRO owner，原 884 行 runtime 拆为 435/483 行，`LnrSolver` 绑定
286→234。有状态 Stage/Context/Run 迁移与 `shared.py` 收口仍待后续批次。

### V5.2-4：Resource Observer 收口

- 以 observation → facts → proposal → validation → effect 的链路逐段迁移。
- Resource effects 继续只允许经过 validated、idempotent effect port。
- 将 review、safety、sharing、admission 和 telemetry 状态分离。
- 删除 legacy compatibility views 和 212 个 façade 绑定。
- 将 `ResourceRuntime` 的 67 个绑定替换为 capability composition，并将 admission/lease/observation/review/sharing 分层。
- 合并 observer 的 proxy 与 implementation；callback adapter 之外不再使用 `*_bridge.py`。

验证：resource mechanism replay、process/tool contract，以及以下资源类记录点：

- `resource_gpu_contention_resume_v1`：严格 heavy-heavy 互斥、durable queue、stale lease；
- `resource_gpu_train_tt_admission_resume_v1`：heavy train 与 `gpu_tt_light` test-time
  inference admission、合法 share 分支、双 pending Tool Call。

迁移过程中可以先依赖 tests/replay；批量删除 observer façade 和兼容状态前，受影响路径必须
至少有对应的 stable point Resume。V5.2-4 完成时，上述两个 case 都应各自在同一只读 bundle
的两个独立副本上 Resume 并通过 oracle；否则只能标记为实现完成、验收待定。

当前状态：第一轮实现已完成（Observer 212→0、ResourceRuntime 67→0，proxy/bridge 已清理）；
533 项分支定向 Resource/Resume 测试通过。`resource_state_recovery_logic_resume_v1` 已基于真实
Jigsaw store 完成 2×100 component Resume；mixed admission 和 strict contention 也都完成两个
独立的真实 CUDA point Resume 并晋升 `stable`。V5.2-4 的资源物理验收已关闭。

### V5.2-5：Agent host 与 Session 收口

- 将 `ScienceAgent` 的 107 个 callable binding 按 IQ Runtime hook、ScienceFlow callback port 和领域 service 分流。
- `ScienceAgent` 不再直接拥有 Finalization、Embedded Fullrun、Workspace、Safety、Telemetry 的私有实现方法。
- 将构造参数归并为 typed spec，factory builder 只负责 composition，不传播巨型 `locals()` 字典。
- 将 `agent/session.py` 迁入 session 子包，按 host/context/turn/tool-result owner 分文件。

验证：IQ runtime contract、agent factory trace、callback ports、runtime parity quick/full。

当前状态：typed builder、session 六类 owner 和 19 项 `AgentHostPorts` 已完成，公共导入保持；
`builder.py` 632→34 行，construction assembly 为 626 行，`ScienceAgent` 绑定 107→68。
剩余兼容 binding 随调用方 owner 继续收口，不能以动态绑定伪造下降。

### V5.2-6：高复杂度流程压缩

- 拆解 Dataset Scan 的 traversal/render 分支。
- 将 Embedded Fullrun 和 Bash Monitor 表达为显式 transition + effect。
- 清理重复 dict normalization，替换为 typed records。
- 对复杂度超过 20 的剩余函数逐项登记原因。

验证按 owner 选择，不自动触发全部长程任务。

当前状态：Dataset Scan 切片已完成。`scan.py` 从 457 行收敛为 148 行 composition，单次遍历、
bottom-up 统计、top-level rendering、large-flat 和 nested-tree rendering 分属明确 owner；原复杂度
80、69、25 以及两个 11 的 JSON 分支均已拆除，Dataset 包 Ruff `C901` 为 0。根目录超过 15 个
同扩展名文件时旧实现会因未初始化 label state 崩溃，本切片已修复并增加回归合同。

Embedded Fullrun 切片也已完成：原 1,411 行模块收为 39 行兼容面，score/snapshot owner 为
777 行，eligibility/execution/result owner 为 790 行；原复杂度 27 的候选快照和 42 的 quick-test
编排分别降到门禁以下与 15，所有 >20 流程已清零。结构脚本已覆盖新二级组件，防止把实现重新
塞回兼容模块。

Bash Monitor 切片已完成：`bash/` 根级业务模块从 12 降为 6，process、policy、monitor 进入二级
owner；原 693 行 execution monitor 拆为 151 行 lifecycle composition、196 行 termination/cleanup
effects、535 行 guard/watchdog decision 和 301 行 stream owner。原复杂度 25 的 `_resource_guard`
已降到门禁以下，Bash 当前 6 个 C901 均不超过 17。

Coordinator 投影切片已完成：worker peer metric selection 从 676 行 advisory 分离到 204 行
`resource/peer_snapshot.py`，stage candidate collection 从 648 行 commit 分离到 226 行
`stage/experiment_state.py`；原复杂度 30 和 23 的两个流程均降到门禁以下，并保留旧模块导出。

Resource decision/control 切片已完成：preflight 按 context、pressure、post-feedback、active-plan、
timeout gate 分层；queue admission 按 assignment、安全采样、lease acquire、boundary/result effect 分层；
classification 与 budget priority 分离事实选择和评分信号；active intervention 分离 observation、shared
runtime、guard 和 follow-up review；arbiter 分离 LLM invocation、decision normalization 与 review-state
推进。原复杂度 37、25、29、22、21、23 的 6 个流程均降到门禁以下。

验证证据：实现完成后的默认完整回归为 1,879 passed、3 skipped；Dataset/结构最终定向合同
14 项通过，task/agent/workspace 关键调用链组合 39 项通过；runtime parity quick 的
context/mechanism/workspace diff 均为 0，模块依赖、Ruff、compileall 通过。最后新增的单项测试只
加强“展开目录普通文件只展示一次”的合同，未再修改生产代码。

Embedded Fullrun 验证证据：score contract、submission history/row guard、统一 evaluator、REPL
run-loop、LNR metric/stage/resume 共 133 项定向测试通过；两个 owner 的 Ruff、compileall、模块依赖
和 800 行结构门禁通过。

Bash Monitor 验证证据：resource arbiter/boundary/guard/mechanism/monitor、parallel Bash 与 pip
normalize 共 311 项定向测试通过；最终结构/关键组合 189 项通过，Ruff、compileall、模块依赖和
目录结构门禁通过。结构审计新增 Bash 全包后，V5.2 扩展目标范围 C901 为 63，其中复杂度超过 20
的剩余项仍为 8 个。

Coordinator 投影验证证据：runtime/resume/stage 与结构合同 46 项通过；runtime parity quick 的
context/mechanism/workspace diff 均为 0，Ruff、compileall、模块依赖通过。扩展目标范围 C901
降至 61，其中复杂度超过 20 的剩余项为 6 个，均位于 Resource decision/control path。

Resource decision/control 验证证据：资源控制面专项 343 项通过，结构合同 18 项通过；runtime
parity quick 的 4 个场景全部通过，context/mechanism/workspace diff 均为 0；修改文件 Ruff 与
compileall 通过；排除正在迁移的 `test_benchmark_sf.py` 后全仓回归为 1,880 passed、3 skipped。
扩展目标范围 C901 降至 55，复杂度超过 20 的流程为 0。

### V5.2-7：兼容面退役与文档收口

- 删除已完成一个弃用周期且无消费者的 façade。
- 更新 dependency rules、owner matrix 和公开 API 文档。
- 固化结构度量门禁，防止新的 catch-all 组件出现。
- 门禁拒绝：超过 8 个直接业务模块的未登记组件包、canonical 路径上的 `sys.modules` proxy、
  超过 10 个 callable descriptor 绑定的零实现 façade，以及目标组件中的 `shared.py`。
- 运行 V5.2 阶段验收；正式三任务长程验收只在发布候选时执行。

### 当前推荐执行顺序

1. 先用合并后的 unit/contract/runtime parity quick 验证第二批组件收口。
2. 普通切片按 diff/owner 选择 1–3 个 stable `bench_sf` case；源 bundle 永不原地修改，
   不默认运行全量 release。
3. 继续 V5.2-1 的 fallback 清理和 V5.2-2 的私有 seam 迁移，不再扩大 façade monkeypatch 面。
4. 按 Stage → Evaluation → Context/ESTRA 的 owner 顺序继续 V5.2-3；每个
   切片只选择相关 point case，不运行全量 release。
5. V5.2-4 先拆 observation/admission/safety/effect owner，再删除 façade 绑定；批量删除前
   执行对应 stable resource case，避免用静态拆文件代替真实 Resume 证明。
6. V5.2-5 单独收口 Agent host、factory 与 session；这一步不能通过把方法搬到另一个 façade 完成。
7. V5.2-6/7 收口后才进入发布候选，最后运行 Circle、Nomad、TFBind8 正式验收。

第二批合并后证据：759 项跨 Coordinator/Resource/Agent/Dataset/Resume 定向测试通过；
runtime parity quick 单进程运行通过，context/mechanism/workspace diff 均为 0。该证据不替代
`bench_sf` Resume 或发布候选长程验收。

回归门禁收口证据（2026-08-30）：ScienceFlow 默认完整测试为 1,871 passed、3 skipped，
InquiryCraft 默认完整测试为 232 passed、1 skipped；ScienceFlow CI 契约清单 84 passed，
runtime parity full 入口通过，模块依赖、Ruff、compileall 均通过。Agent 结构门禁已从与二级
owner 目录冲突的递归文件数限制，迁移为“根级业务模块不超过 8、单 owner 不超过 800 行、
聚合代码不超过当前 4,331 行”的三层门禁；当前实测分别为 7、626、4,331。

这样，低风险的 API/test seam 工作可以立即进行；需要真实长程状态证明的 façade 删除则等待
对应 point checkpoint 晋升 stable，不存在“每次先跑一小时”或“没有 bench 就无法开始”的循环。

### 第一执行批次（已合并）

第一批只建立可迁移条件，不进行跨 owner 的批量搬家：

1. 新增可重复结构度量，输出文件行数、复杂度、直接模块数、descriptor binding、私有测试访问和
   `shared.py` import 面。
2. 建立 V5.2 owner matrix；每个 coordinator/observer/agent/resource-runtime 方法标明
   `target_owner`、state、port、effect、生产消费者、测试消费者和删除条件。
3. 先迁移纯函数测试与 `object.__new__(LnrSolver)` fixture；这一切片不得改变 Prompt、事件或 Workspace。
4. 切换现存 InquiryCraft 私有 import 到公共 namespace，并运行 dependency/import/runtime parity quick。
5. 以 Finalization 作为首个目录收口样板：让 service 真正拥有 orchestration，按
   selection/candidates/artifacts 分层；只做等价移动与空壳合并，不改变候选排序和最终产物语义。

第一批完成条件：度量可重复、owner matrix 无未归属项、受影响测试不再依赖待删除 façade、
Finalization 样板通过定向 contract 与 runtime parity。完成后才开始 Stage/Evaluation controller 迁移。

禁止一次性移动整个 coordinator 或 observer。每个切片必须同时完成 owner 代码、consumer、测试、
兼容入口和定向验证，不能留下“新目录实现 + 旧 façade 永久转发”的双重结构。

### 第二执行批次（已合并）

- Evaluation 以四个真实 owner 进入 `LnrSolver` MRO，删除 42 个 Evaluation descriptor binding；
- Resource Observer 将 monitoring/sharing/review 四个大文件拆成 10 个 592 行以内的 owner，方法 AST 保持一致；
- Agent Session 改用 typed `AgentHostPorts`，builder 与 assembly 分层，删除 39 个 host binding；
- Dataset Scan 第一层拆为 scan/metadata/tree/eval-signature 四个 owner，单文件最大 612 行；随后
  V5.2-6 将 traversal、top-level render、large-flat 和 nested-tree 决策进一步收为独立 owner，
  保持直接业务模块为 8、最大单文件 676 行，并将 Dataset C901 清零；
- 合并后的 callable descriptor 总数从初始 672 降到 302，未使用动态绑定或生成代码规避门禁。

## 6. 验证策略

V5.2 使用分层验证，不把真实模型分数和框架合同混为一体。

1. 每个切片：Ruff/compile/import、受影响 unit/contract、架构边界。
2. ownership 或消息/事件相关切片：runtime parity quick/full。
3. 长程技术点相关切片：从 `bench_sf` 的相应真实 checkpoint Resume，验证短窗口 continuation。
4. Prompt、Schema、调用顺序或机制语义改变：升级为受影响任务的真实新跑与 Resume 对照。
5. 发布候选、基线刷新或跨版本 Runtime 切换：才运行 Circle、Nomad、TFBind8 正式 Worker=2、1 小时验收。

模型未触发目标路径应记录为 `unreached`，不能误报为框架失败；框架事件、状态、Workspace、Resume
幂等性和 artifact 合法性才是 V5.2 重构的硬门禁。

### 6.1 当前 case 映射与缺口

| 变更范围 | 当前 checkpoint | 当前状态 | 本阶段动作 |
| --- | --- | --- | --- |
| Resource lease/queue/process | `resource_gpu_contention_resume_v1` | `stable` / 真实 CUDA 2×100 | owner/queue/process 变更的 physical point 门禁 |
| Resource admission/sharing/Resume | `resource_gpu_train_tt_admission_resume_v1` | `stable` / 真实 CUDA 2×100 | admission/share/Resume 变更的 physical point 门禁 |
| Resource state recovery | `resource_state_recovery_logic_resume_v1` | `stable` / 2×100 | 普通 resource state 变更的快速门禁；不替代 CUDA 层 |
| Context/text-only/ESTRA | `text_only_estra_trigger_resume_v1`、`estra_keep_compact_resume_v1`、`estra_switch_restore_resume_v1`、`estra_restore_rollback_resume_v1` | 4 个均 `stable` / 2×100 | 按 owner 选择；四 case chain 已并行实跑 100 |
| Multi-worker peer context/merge | `multi_worker_peer_context_resume_v1`、`worker_merge_resume_v1`、`partial_worker_finalization_resume_v1` | 3 个均 `stable` / 2×100 | Context/merge/finalization 切片门禁 |
| Stage/query/finalization | `stage_commit_resume_v1`、`query_budget_terminal_resume_v1`、`best_stage_finalization_resume_v1`、`snapshot_restore_resume_v1` | 4 个均 `stable` / 2×100 | Stage/TFBind8/Snapshot 切片门禁 |
| IQ Runtime/Tool/provider deadline | `resume_pending_tool_v1`、`provider_deadline_resume_v1` | 2 个均 `stable` / 2×100 | exactly-once 与本机 deterministic deadline 门禁 |

因此当前 `bench_sf` 已是可执行的 stable 证据集：14 个 component 与 2 个 physical GPU
记录点均可从不可变 bundle Resume。每个组件切片只运行与 diff/owner 匹配的 1–3 个 point
case，不用全量 release 代替选择；physical case 仍需显式选择，默认 release 不占用 GPU。

## 7. 完成定义

V5.2 只有同时满足以下条件才完成：

1. ScienceFlow/IQCraft 单向依赖及唯一 Agent Runtime 继续成立。
2. ScienceFlow 不再使用 InquiryCraft 私有实现模块。
3. `LnrSolver`、`LHRResourceObserver`、`ResourceRuntime` 和 `ScienceAgent` 不再通过大规模 descriptor binding 组装。
4. Stage、Evaluation、Context、ESTRA、Resource、Finalization 均有明确 state/port/effect owner。
5. Coordinator、Resource Runtime、Observer、Agent 和 Finalization 的目录层级直接表达 owner；不存在无意义 proxy 或平铺 bridge 集合。
6. 复杂度和模块规模达到目标，或每个例外均有 owner、原因和清理期限。
7. runtime parity 无未登记差异。
8. 对应 `bench_sf` checkpoint 可以从不可变副本 Resume，关键技术点实测通过。
9. 旧 Workspace Resume、事件顺序、artifact 合法性和最终选择语义保持兼容。
