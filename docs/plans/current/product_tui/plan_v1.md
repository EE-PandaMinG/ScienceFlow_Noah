# ScienceFlow 统一 TUI 与自然语言长程 Onboarding 规划 V1

状态：已由 [`plan_v2.md`](plan_v2.md) 替代
日期：2026-09-02
实施分支：`product`
规划基线：`66bfe05`（Light/Full 产品安装与部署档位）
关联规划：[`../plan_v5.2.md`](../plan_v5.2.md)
长程机制验收：[`../../../benchmark/bench_sf_v1.md`](../../../benchmark/bench_sf_v1.md)

## 1. 结论

ScienceFlow 产品交互收敛为一个统一 TUI。启动后默认直接进入 Agent Loop，不要求选择模式、
创建 goal 或提供任务配置；用户的普通输入全部交给 Agent Runtime。只有用户显式输入
`/long-research` 时，系统才从当前会话切入长程研究 onboarding，在同一会话内生成任务契约草案，
扫描数据，配置 evaluator/gate，执行可信 preflight，并在用户确认后调用现有 LNR/Parallel
运行入口。

默认 Agent Loop 不进入 LNR，不创建 Stage，不分配长程 worker，也不要求 task package、
evaluator、validator 或 gate。它不能把普通会话结论声明为经过权威验收的长程结果。

现有脚本入口继续保留，并与 TUI 消费同一份冻结配置：

```bash
scienceflow run ...
scienceflow parallel --manifest <generated-manifest.yaml>
scienceflow monitor ...
```

TUI 是交互和编排入口，不建立第二套 Agent Runtime、Workflow Runtime、Gate 或资源管理实现。

## 2. 用户问题

当前正式长程任务通常要求用户提前准备：

- task description；
- dataset 路径和布局；
- candidate artifact 合同；
- metric 名称与方向；
- evaluator/validator；
- gate policy；
- worker、CPU/GPU 和时间预算；
- run/parallel manifest。

这些信息对稳定 benchmark 是必要的，但不应成为陌生任务的首次使用门槛。用户先在默认 Agent
Loop 中自然交流；需要长程研究时输入 `/long-research`。系统发现可以安全推断的事实，只要求用户
确认无法可靠推断且会改变实验含义的项目。

## 3. 产品模式

### 3.1 默认 Agent Loop

统一入口：

```bash
scienceflow tui
```

默认 Agent Loop 的合同：

- 使用 InquiryCraft Agent Runtime；
- TUI 启动后立即可用，不要求先选择运行模式；
- 普通自然语言输入直接进入 Agent Loop，不自动启动长程研究；
- 不调用 evaluator/gate，不产生“verified”结论；
- 不创建长程 worker，不申请长时 GPU lease；
- 保留会话，可将对话压缩为后续 Task Brief；
- 用户输入 `/long-research` 前，不生成或执行长程 evaluator 代码。

现有 `scienceflow agent run/repl` 保留为无 TUI 的轻量脚本与终端入口。

### 3.2 Long-horizon Research

只有 `/long-research` 可以从默认 Agent Loop 进入长程研究：

```text
/long-research
```

无参数时，系统从当前会话提炼 Task Brief。也允许在命令后补充本次长程约束：

```text
/long-research 数据就在当前目录，macro F1 越高越好，两个 worker，运行一小时
```

`/long-research` 启动 onboarding，但不跳过 preflight 或确认直接运行任务。它依次完成：

1. 从对话提炼 Task Brief；
2. 扫描只读数据源；
3. 生成结构化 TaskSpec 草案；
4. 解析或生成 evaluator/gate；
5. 执行 preflight；
6. 在 TUI 展示确认卡；
7. 冻结配置和摘要；
8. 调用现有 LNR/Parallel launch service；
9. 在同一 TUI 中监控、暂停、恢复和查看证据。

## 4. 统一交互状态机

```text
AGENT_LOOP
  -- /long-research --> DRAFTING
  -> NEEDS_INPUT (仅缺少关键语义时)
  -> PREFLIGHT
  -> READY
  -> RUNNING
  -> PAUSED / COMPLETED / FAILED
```

规则：

- `AGENT_LOOP -> DRAFTING` 只能由 `/long-research` 触发，不根据普通自然语言猜测或自动启动；
- `/long-research` 是 TUI action，不作为文本发送给模型；
- `DRAFTING -> PREFLIGHT` 不要求用户理解 YAML；
- metric 方向、数据权限或目标产物无法可靠推断时进入 `NEEDS_INPUT`；
- 只有 `preflight_passed=true` 且用户确认后才能进入 `RUNNING`；
- 配置变化后必须产生新 revision，不能静默修改正在运行或可 Resume 的任务；
- `PAUSED -> RUNNING` 复用已有 Resume，不重新创建任务语义。

## 5. TaskSpec 合同

自然语言最终必须收敛为可序列化、可审计的结构化合同，而不是把自由文本直接传给运行器。
建议 V1 schema：

```yaml
schema_version: "1.0"
task:
  id: generated-task-id
  title: Human-readable title
  description: |
    Frozen task objective and constraints.
dataset:
  source: /read-only/source
  workspace_mount: dataset
  discovery_digest: sha256:...
objective:
  metric: macro_f1
  direction: maximize
artifact:
  path: submission.csv
  kind: submission_csv
evaluation:
  backend: task_package | artifact_command | builtin
  entrypoint: .scienceflow/evaluator/validate.py
gate:
  policy: default | optimization_feasibility
  params: {}
trust:
  level: exploratory | provisional | verified
  preflight_report: .scienceflow/preflight_report.json
```

字段必须区分三种来源：`user`、`discovered`、`inferred`。确认卡应显示来源和置信度，避免把模型
推断伪装成用户要求。

任务语义与运行资源必须分开。TaskSpec 定义“做什么、如何判断正确”，RunSpec 定义“本次怎样跑”。
建议 V1 RunSpec：

```yaml
schema_version: "1.0"
task_spec_hash: sha256:...
run:
  workers: 2
  wall_clock_sec: 3600
resources:
  accelerator: cuda            # auto | cpu | cuda
  gpu_selection: explicit      # auto | explicit | none
  gpu_devices:
  - physical_index: 0
    uuid: GPU-...
  - physical_index: 1
    uuid: GPU-...
  gpu_sharing: false
  cpu_per_worker: 8
  cpu_sets:                    # 由 ResourceRuntime 生成不重叠集合
  - 0-7
  - 8-15
  on_conflict: ask             # ask | wait | reduce_workers | fallback_cpu
```

用户在 TUI 中可以用 `0,1` 选择 GPU；持久化时同时记录 GPU UUID，避免容器或
`CUDA_VISIBLE_DEVICES` 重排后把逻辑编号误认为另一张物理卡。默认不允许多个 worker 静默共享
同一 GPU；共享必须显式确认。

## 6. Workspace 产物

每次 `/long-research` onboarding 在目标 workspace 内生成：

```text
.scienceflow/
  task.yaml                 # canonical TaskSpec
  run.yaml                  # 本次预算与资源选择
  run_manifest.yaml         # 兼容现有 parallel/run 入口
  preflight_report.json     # evaluator/gate 与资源预检证据
  onboarding_events.jsonl   # 草案、确认和 revision 事件
  evaluator/                # 仅在需要自定义 evaluator 时存在
description.md              # 现有 Agent/REPL 的兼容投影
```

`task.yaml` 是任务语义真相源，`run.yaml` 是本次运行真相源，`run_manifest.yaml` 是执行投影。
它们分别记录 `task_spec_hash` 与 `run_spec_hash`。TUI、CLI 和 Resume 必须校验两个 hash；任务
语义漂移时要求创建新 task revision 或显式 fork。Resume 更换空闲 GPU、减少 worker 等资源重绑定
只创建新的 run revision，不伪装成原资源布局，也不改变任务身份。

## 7. Evaluator 与 Gate 自动生成策略

### 7.1 优先级

按以下顺序选择 evaluator，尽量避免生成任意代码：

1. 已登记的 task package；
2. 内置声明式 evaluator；
3. 用户提供的现有验证命令；
4. 根据明确 metric/artifact 合同生成的最小 evaluator；
5. 无法建立权威评价时使用 `exploratory`，不伪造 validator。

Gate 优先使用已登记的声明式 policy 和参数。自然语言应映射到已有 policy；只有发现新的领域
不变量时才设计新 gate plugin，不能为每个陌生任务复制一个策略文件。

### 7.2 信任级别

| 等级 | 含义 | 是否可声明权威验收 |
| --- | --- | --- |
| `exploratory` | 缺少真实标签、参考求解器或确定评价函数 | 否 |
| `provisional` | evaluator 可运行，但只完成基础反例和 smoke 检查 | 否 |
| `verified` | evaluator 来源可信，关键不变量和重复性检查均通过 | 是 |

长程探索可以在 `exploratory` 或 `provisional` 下运行，但 Stage 和最终结果必须保留信任等级，
不得与 `verified` 排名混合。

### 7.3 Preflight 最低要求

- 数据路径存在且保持只读；
- schema 与必要字段可解析；
- 正常 baseline 产物可以执行 evaluator；
- 缺失、损坏、NaN/Inf 和错误行数产物会被拒绝；
- metric 名称、方向和范围一致；
- 相同输入重复运行得到一致结果，或明确记录允许的随机性；
- evaluator 有超时、隔离工作目录和输出大小限制；
- gate 对 evaluator 失败保持 fail-closed；
- worker/CPU/GPU 请求可被 ResourceRuntime 接受；
- 生成 `preflight_report.json`，包含配置 hash 和检查结果。

由 LLM 生成的 evaluator 在 preflight 通过前只能作为不可信草案执行，不能写入正式 Stage ledger。

## 8. TUI 页面与交互

V1 只需要五个稳定视图：

1. **Agent**：默认 Agent Loop，并解析 `/long-research` TUI action；
2. **Task Setup**：数据、目标、metric、artifact、预算的结构化摘要；
3. **Preflight**：每项检查、失败原因和修复建议；
4. **Run Monitor**：worker、Stage、资源、ESTRA、候选和剩余时间；
5. **Resume**：已有运行、配置 hash、最后可信 Stage 与恢复动作。

确认卡至少展示：

```text
Task: tabular classification
Dataset: /data/example (read-only, discovered)
Metric: macro F1, maximize (user)
Artifact: submission.csv (inferred)
Evaluator: generated artifact command, provisional
Gate: default/high validity
Resources: 2 workers, 1 GPU, 1 hour

[Run preflight] [Edit] [Continue chat]
```

不在 TUI 中重新实现日志解析、资源调度或 Resume。视图消费现有 typed event、resource event、
Stage ledger 和 Resume contract。

### 8.1 关键配置问询

`/long-research` 进入 onboarding 后，系统先读取任务、数据和实时资源事实，再只询问会影响成本、
可行性或评价语义的配置。问询支持按钮、数字输入和自然语言回答，不要求用户编辑 YAML。

V1 必须覆盖：

| 问题 | 系统建议依据 | 可选回答示例 |
| --- | --- | --- |
| 是否使用 GPU | 任务依赖、模型类型、当前 GPU 可用性 | 自动、仅 CPU、使用 GPU |
| 使用哪些 GPU | 物理 index、UUID、空闲显存、已有 lease/waiter | 自动、`0`、`1`、`0,1` |
| worker 数量 | 数据规模、GPU 数、CPU/内存和剩余预算 | `1`、`2`、`4` |
| CPU 如何分配 | 可用核心、NUMA/affinity、worker 数 | 自动隔离、每 worker 8 核 |
| 运行多久 | 用户目标、任务规模和资源成本 | 15 分钟、1 小时、4 小时 |
| 资源冲突怎么办 | 当前 owner、等待队列和任务是否支持 CPU | 询问、等待、减少 worker、CPU 回退 |

推荐交互：

```text
检测到 2 张可用 GPU：
  GPU 0  72 GB free  no active lease
  GPU 1  68 GB free  no active lease

该任务建议使用 2 workers，每个 worker 独占 1 张 GPU。

GPU：[自动（推荐）] [仅 GPU 0] [仅 GPU 1] [GPU 0,1] [仅 CPU]
Workers：[2（推荐）] [1] [自定义]
Time：[1 hour] [15 min] [自定义]
Conflict policy：[询问（推荐）] [等待] [减少 workers] [回退 CPU]
```

问询规则：

- 已由用户明确给出的配置不重复询问，只在不可行或冲突时解释原因；
- 推荐项必须显示依据，不能把推断显示成用户选择；
- TUI 展示的是资源 proposal，不直接占用 GPU；
- 点击最终启动前，ResourceRuntime 重新读取实时状态并执行 authoritative admission；
- 问询后资源状态发生变化时，按 `on_conflict` 处理，不能静默抢占或换卡；
- worker 使用互不重叠的 CPU set；共享 GPU、超额 worker 或 oversubscription 必须明确提示；
- 选择 GPU index 时同时显示 UUID、显存和当前 owner，避免编号歧义；
- TUI 只收集意图并展示决策，lease、queue、revoke 和 process effect 仍由 ResourceRuntime 拥有。

## 9. 组件与所有权

目标目录建议：

```text
scienceflow/
  interfaces/
    tui/                         # Textual 页面、view-model、用户 action adapter
  research/
    onboarding/
      intent/                    # /long-research action 与会话投影，不执行副作用
      task_spec/                 # schema、revision、serialization
      discovery/                 # dataset/task facts
      drafting/                  # natural language -> TaskSpec draft
      inquiry/                   # 关键语义、预算与资源问询
      confirmation/              # unresolved facts and approval record
    quality/
      preflight/                 # evaluator/gate trust checks
  runtime/
    launch/                      # TUI/CLI 共用的 run request 与 launch service
```

边界要求：

- `interfaces/tui` 不导入 Click command handler；
- TUI 与 CLI 都调用 typed launch service；
- onboarding 不拥有 Agent turn loop；
- preflight 不修改正式 Stage ledger；
- launch 不解释自然语言，只接受冻结 TaskSpec 与 RunSpec；
- ResourceRuntime 仍是资源 admission/lease/effect owner；
- 组件一般保持在 500--800 行以内，超过时按 state、port 或 effect 拆分；
- 不建立新的 `shared.py`、巨型 controller 或包含全部可变状态的 context 对象。

## 10. CLI 兼容与自动化

TUI 生成的 manifest 必须可以脱离 TUI 重放：

```bash
scienceflow parallel --manifest .scienceflow/run_manifest.yaml
```

正式目标是把现有 Click handler 中的运行逻辑下沉为 typed application service：

```text
TUI action -----------+
                      +--> LaunchService --> LnrSolver / ParallelRunner
CLI command ----------+
```

短期允许 TUI 调用稳定 launch adapter，但不以 shell 拼接用户文本。长期不保留“TUI 子进程路径”和
“CLI 直接 Python 路径”两套不同行为。

## 11. 实施阶段

### P0：合同冻结

- 定义 TaskSpec、RunSpec、两类 revision/hash、trust level 和 onboarding event；
- 定义默认 Agent Loop 与 Long-horizon 的能力边界；
- 提取 CLI/TUI 共用 LaunchRequest/LaunchService；
- 固定生成文件路径和 hash 规则。

完成条件：TaskSpec/RunSpec round-trip、语义与资源配置漂移、CLI/TUI 等价 contract 测试通过。

### P1：统一 TUI 与默认 Agent Loop

- 在 Light 安装中提供 TUI 所需的轻量依赖；
- 暴露 `scienceflow tui`；
- 接入 InquiryCraft session、stream、history 和 workspace 选择；
- 默认 Agent Loop 不加载 evaluator/gate/LNR；
- 实现 `/long-research [可选约束]` action；
- 普通模型输出或用户文本不能伪造该 TUI action。

完成条件：PyPI Light 环境可直接启动 TUI；普通 Agent Loop 不会产生 Stage、长程资源 lease 或
evaluator event；只有 `/long-research` 能进入 `DRAFTING`。

### P2：长程 TaskSpec 与数据发现

- 从会话生成 Task Brief；
- 扫描数据目录并生成 discovery digest；
- 标注字段来源和置信度；
- 只针对 metric 方向、权限、资源成本和关键目标提出问题；
- 检测 GPU/CPU/内存事实，问询 GPU 0/1、worker 数、CPU 隔离、时限和冲突策略；
- 保存 revisioned `task.yaml`、`run.yaml` 和 `description.md` 投影。

完成条件：未登记的 fixture task 不手写 YAML 即可得到可审阅 TaskSpec/RunSpec；资源建议包含事实
依据，用户明确选择不会被静默覆盖。

### P3：Evaluator/Gate Preflight

- 实现 evaluator 选择优先级；
- 提供通用 schema、metric、artifact 和负例检查；
- 隔离执行生成的 evaluator；
- 生成 trust level 与 preflight report；
- 未达到 `verified` 时在 TUI、Stage 和结果中持续显示等级。

完成条件：损坏 artifact、错误方向、非有限 metric、非确定 evaluator 和超时均被稳定识别。

### P4：Launch、Monitor 与 Resume

- TUI 确认后生成兼容 manifest；
- 启动前由 ResourceRuntime 重新校验资源 proposal，并固化实际 CPU/GPU mapping；
- 通过 LaunchService 启动 single/multi worker；
- 复用现有 monitor/resource/Stage/ESTRA events；
- 展示暂停、失败和 Resume 候选；
- Resume 校验 TaskSpec hash 和最后可信 Stage。

完成条件：同一 manifest 经 TUI 与 CLI 启动得到一致 resolved config；TUI 可恢复脚本启动的运行。

### P5：发布收口

- 补齐中英文 TUI Quick Start；
- 提供三个短 fixture：无数据聊天、内置 evaluator、生成 evaluator；
- 运行组件 contract、安装 smoke 和短程端到端测试；
- 发布候选阶段才用 `bench_sf` 的关键 Resume point 验证长程继承，不在每次 UI 修改后全量长跑。

完成条件：Light wheel 安装后 TUI/CLI 均可运行；Full 环境保持现有正式任务兼容。

## 12. 验收矩阵

| 场景 | 期望 |
| --- | --- |
| `scienceflow tui` 首次启动 | 无 task package、gate 或 dataset 配置要求 |
| 普通自然语言输入 | 直接进入 Agent Loop，无 Stage、evaluator event 或长程 worker |
| 普通文本包含“长程研究” | 不自动进入长程模式，仍作为普通 Agent 输入 |
| `/long-research` | 从当前会话生成可审阅 TaskSpec，不立即启动正式运行 |
| `/long-research <约束>` | 会话 Task Brief 与命令约束一起进入 onboarding |
| 数据路径未知 | 只询问路径，不要求用户写 manifest |
| metric 方向未知 | 阻塞确认，不猜测后静默运行 |
| 检测到 GPU 0、1 | 展示 index、UUID、空闲显存和 owner，并提供自动/指定/CPU 选择 |
| 用户选择 GPU `0,1` | RunSpec 固化稳定设备身份，两个 worker 默认分别独占一张卡 |
| worker 多于独占 GPU | 明确提示共享/等待/减少 worker，不静默 oversubscribe |
| CPU worker 并行 | ResourceRuntime 生成互不重叠的 CPU set |
| 确认后 GPU 被占用 | 按冲突策略询问或等待，不静默抢占和换卡 |
| 无权威评价函数 | 标为 `exploratory`，允许探索但不声明 verified |
| evaluator preflight 失败 | fail-closed，不进入正式长程运行 |
| TUI 确认启动 | 生成标准 manifest 并调用现有运行能力 |
| CLI 重放生成 manifest | resolved config 与 TUI 启动一致 |
| Resume | 校验 TaskSpec hash，恢复最后可信状态 |
| 多 worker | 继续使用既有资源管理、集合提示、ESTRA 与 finalization |

## 13. 测试策略

普通提交不运行全量长程验收：

1. TaskSpec/RunSpec schema、`/long-research` action、问询 decision 与 preflight 纯单元测试；
2. TUI view-model 与 action contract 测试，不依赖真实终端截图；
3. CLI/TUI resolved-config parity；
4. 生成 evaluator 的正例、反例、超时与重复性 fixture；
5. ResourceRuntime admission dry-run；
6. 单 worker 极短 smoke；
7. 发布候选才选择 `bench_sf` 对应 Resume checkpoint 做真实机制验证；
8. Circle/Nomad/TFBind8 `w2-1h` 仍只属于正式发布验收，不作为日常 TUI 回归。

## 14. 非目标

- 不删除现有 `run`、`parallel`、`monitor` 或脚本入口；
- 不让 TUI 成为新的 Workflow Runtime；
- 不在 InquiryCraft 中加入 ScienceFlow Gate、Stage 或资源领域逻辑；
- 不为每个新任务生成新的 Python gate 类；
- 不把 LLM 自评直接当作权威 metric；
- 不因缺少 validator 而假装任务已经 verified；
- 不在本规划中重写 LNR、ESTRA、Resume、Resource 或 Finalization 算法；
- 不要求每次交互层改动执行全量长程 benchmark。

## 15. 主要风险与控制

| 风险 | 控制 |
| --- | --- |
| 自动推断错误 metric 或方向 | 显示来源/置信度；关键语义必须确认 |
| LLM 生成 validator 自证正确 | 负例、重复性、baseline、隔离执行；未通过不得 verified |
| TUI 与 CLI 行为分叉 | 共用 TaskSpec、LaunchRequest 和 LaunchService |
| 会话上下文污染正式 Prompt | 只投影冻结 Task Brief，不直接复制全部聊天历史 |
| 配置修改破坏 Resume | revision + TaskSpec hash + 显式 fork |
| TUI 组件继续膨胀 | view、view-model、intent、preflight、launch 分 owner |
| Light 安装明显变重 | 只加入终端 UI 依赖；ML/GPU/MLEBench 仍留在 Full/内部层 |

## 16. 首轮实施决策

V1 默认采用以下决策，只有获得新证据时才调整：

1. 产品统一入口命名为 `scienceflow tui`；
2. TUI 启动后默认直接进入 Agent Loop，不存在额外 Quick 模式选择；
3. `/long-research` 是进入长程 onboarding 的唯一显式命令；
4. TaskSpec 是语义真相源，manifest 是执行投影；
5. 优先复用内置 evaluator/gate，生成代码是后备路径；
6. 无权威评价依据时允许探索，但信任等级不得高于 `exploratory`；
7. CLI 和脚本入口长期保留，并与 TUI 共用运行服务；
8. 日常验证用 contract/fixture/短 smoke，正式长程继承用 `bench_sf` Resume point。
9. GPU、worker、CPU set、时限和冲突策略由 TUI 基于事实推荐并向用户问询，ResourceRuntime
   保持最终 admission owner。
