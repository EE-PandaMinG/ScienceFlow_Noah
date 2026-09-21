# ScienceFlow / DeepCraft 下一阶段精简与合并规划（2026-08-23）

> **边界复审：** 本文最初对 Tool Runtime 下沉范围偏保守。针对
> `core/agent/tool_exec`、`core/tools`、`core/agent/tools`、`core/executor` 以及 DeepCraft
> `legacy/` 的逐文件复审和替代执行计划，见
> `SCIENCEFLOW_DEEPCRAFT_TOOL_RUNTIME_V2_PLAN_2026-08-23.md`。Tool/Executor 与 legacy
> 收敛以 V2 规划为准；本文的 Solver、Resource Runtime 大文件拆分建议继续有效。

## 1. 目标与约束

DeepCraft 独立分仓已经完成。下一阶段不再做发布形态迁移，而是清理 ScienceFlow 中迁移后留下的
兼容入口、继续下沉少量领域无关机制，并拆解过大的 ScienceFlow 领域模块。

本阶段的硬条件保持不变：不得改变 ScienceFlow 的 Prompt、消息顺序、Tool 名称与 Schema、LLM
参数及调用时机、重试和超时、Memory 投影、Tool feedback、Stage/Gate/ESTRA/Resource/Merge 机制，
也不得改变任何 Workspace 路径、日志、Memory、JSON/JSONL、Snapshot、软链接或最终产物。

“代码变少”和“文件变小”都不是单独的验收理由。只有上下文、机制、Workspace 和任务效果门禁
一致，候选改动才可合并。

## 2. 当前审计结论

ScienceFlow 当前约有 9.2 万行 Python。主要热点为：

| 文件 | 行数 | 归属判断 |
| --- | ---: | --- |
| `solver/lnr/solver.py` | 10,248 | ScienceFlow 科研编排，保留并拆分 |
| `solver/lnr/resource_runtime/observer/controller.py` | 9,663 | ScienceFlow 资源策略，保留并拆分 |
| `core/mem/memory_context.py` | 4,621 | ScienceFlow 上下文策略，保留并拆分 |
| `core/tools/bash_tool.py` | 2,785 | 通用进程机制可下沉，科研策略保留 |
| `core/agent/agent.py` | 1,904 | ScienceFlow Agent 组合层，保留并拆分 |
| `config/settings.py` | 1,791 | ScienceFlow 配置合同，保留并分区 |
| `core/agent/runtime/run_loop.py` | 1,616 | 通用机制与科研策略混合，按合同切片 |

静态扫描发现约 80 个超过 120 行的函数。最突出的职责集中点包括
`BashTool.execute`、ScienceFlow policy loop、resource preflight、`ScienceAgent.__init__` 和
Bash resource guard。这些是后续模块化目标，但不能通过机械切文件或重写控制流一次性处理。

### 2.1 已经完成下沉、只剩兼容入口

以下能力已经由 DeepCraft 实现，不应再复制一份算法：

- `core/key_pool.py`：底层 endpoint pool、retry-after 和稳定路由已在 DeepCraft；当前文件只保留
  ScienceFlow logger、环境变量及历史 monkeypatch 入口。
- `core/llm_reasoning_compat.py`：只转发 DeepCraft provider 错误识别。
- `core/subprocess_utils.py`：只重导出 DeepCraft subprocess 生命周期 API，生产代码已直接引用
  DeepCraft，当前仅测试和潜在外部调用者依赖历史路径。
- `core/agent_runtime.py`：Memory record IO/window repair、workspace prefix rewrite 和 legacy LLM
  factory 已在 DeepCraft；文件中仍有 ScienceFlow 的 route-record 过滤、日志和配置组合。
- Read/Write/Edit/Glob/Grep/Ls 工具的文件操作原语已经下沉；ScienceFlow 文件保留历史 Tool Schema、
  默认值、错误文本和 `ToolResult` 渲染。

这些 facade 不应立即全部删除。先固定公开 import 清单，为内部消费者改用 DeepCraft 公开 API；对外部
兼容入口至少保留一个弃用周期，或在确认它从未属于公开 API 后才删除。

### 2.2 仍可下沉到 DeepCraft 的机制

| 候选 | 下沉内容 | 必须留在 ScienceFlow 的内容 | 风险 |
| --- | --- | --- | --- |
| Bash transport | stream pump、process frame、取消/超时、返回码与信号归一化 | GPU/resource admission、quick-test、evidence、日志文本和 guard 决策 | 中高 |
| Replay message access | dict/object 消息、tool-call id/name/arguments 的公共解析器 | Workspace truncate、manifest、Stage/Resume 决策 | 中 |
| ToolCollection dispatch | 通用 kwargs 转发和无领域含义的调用适配 | Bash 命令校验、Tool 顺序、Schema 和错误渲染 | 中 |
| Event bridge primitives | 通用 envelope/flush policy 的可配置机制 | legacy ScienceFlow 字段映射及双写开关 | 低中 |

下沉必须先在 DeepCraft 新增公开、无 ScienceFlow 名称的 API，并由 DeepCraft 独立测试；随后发布新的
私有 Git tag，再由 ScienceFlow 更新锁文件。禁止让 ScienceFlow 引用 DeepCraft 私有函数以减少几行代码。

### 2.3 只应在 ScienceFlow 内部合并或拆分的内容

- 将六个 Workspace 文件工具的重复配置读取、路径绑定和结果包装收敛为内部 adapter/factory；各工具
  对外 Schema 的字段、顺序、required、description、默认值和错误文本保持字节级不变。
- 将 `utils/workspace_interaction_log.py` 与 `core/agent/io/interaction_log*.py` 按“logger 生命周期”和
  “内容格式化”重新归位，消除交叉依赖；`interaction.log` 仍是 ScienceFlow 外部合同，不下沉。
- 将 `BashTool` 拆为 transport adapter、resource policy、output renderer 和 tool facade；先拆函数，后
  调用 DeepCraft transport，避免一个提交同时改变执行与渲染。
- 将 `ScienceAgent.__init__` 拆为配置快照、工具装配、Memory 装配、运行策略装配和 Workspace 绑定；
  保持初始化次序、副作用和默认值。
- 将 `run_loop.py` 按 provider 调用、retry/reasoning replay、tool bundle、route decision 和 lifecycle
  拆分，入口仍由 ScienceFlow policy 驱动。
- 将 `memory_context.py` 按 source snapshot、fold/compression、clone/teleport rewrite、tool feedback 和
  assembly 拆分；Memory 内容及投影顺序不得变化。
- 将 `solver.py` 按 worker lifecycle、Stage/ESTRA、resume、merge/finalization 拆成协作组件；solver
  仍是唯一编排入口，不借拆分重写算法。
- 将 resource observer controller 按 admission、queue/lease、observation、intervention 和 termination
  decision 拆分；决策次序和 event 顺序由 mechanism benchmark 固定。
- 将 `settings.py` 的模型定义、环境覆盖、manifest normalization 和 profile override 分区；字段名、
  alias、优先级与默认值保持不变。

### 2.4 明确禁止下沉的边界

下列内容属于 ScienceFlow 科研运行语义：ScienceAgent Prompt、Context/Memory policy、Stage、Gate、
Evaluator、ESTRA、Workspace snapshot/restore、resource admission 与 GPU lease、多 Worker、任务包、
Merge/final selection、interaction log 格式和 embedded full-run。它们可以在 ScienceFlow 内模块化，
不能进入 DeepCraft。

## 3. 分阶段执行顺序

### N0：冻结当前检查点

- 保存本审计、README 调用说明和当前 Git/lock 坐标。
- 复用 Runtime parity baseline v2，不重新生成 baseline。
- 固定 Tool Schema hash、配置归一化结果和旧 Workspace fixtures。

验收：文档命令 smoke、dependency boundary、CLI composition 和当前 parity quick 全绿。

### N1：兼容 facade 清理

- 建立 ScienceFlow 历史 import 清单。
- 内部消费者直接引用 DeepCraft 公开 API。
- 删除无生产消费者且确认非公开的 re-export；其余 facade 加清晰弃用说明，不改变对象身份。
- 合并 `llm_reasoning_compat` 等单函数转发时，先覆盖历史 import 测试。

预期 ScienceFlow 净减少约 100–300 行。只运行 unit/contract、import 和 replay quick 门禁。

### N2：Workspace Tool wrapper 合并

- 提取内部公共配置/绑定层，保留六个工具类和原模块 import 路径。
- 对重构前后 Tool Schema 做规范化 JSON 与原始 JSON 双重比较。
- 对 success/error/system、placeholder rejection、路径 rewrite 和 artifact 做 golden 比较。

预期净减少约 200–500 行。运行 Tool contract、Workspace fixture 和 parity quick。

### N3：Bash 通用 transport 下沉

- 先在 ScienceFlow 内用 characterization tests 锁定 chunk、signal、timeout、cancel、stderr、exit code
  和进程树行为。
- 在 DeepCraft 实现无资源策略的 transport API，独立发布下一 Git tag。
- ScienceFlow adapter 注入现有 callback，并保留 resource guard、quick-test、日志与 output renderer。
- 分别提交 DeepCraft API、ScienceFlow 接入和旧代码删除，便于逐层回退。

预计从 ScienceFlow 移出 300–800 行，DeepCraft 增加约 200–500 行；合并后的总净删除量较小，收益
主要是唯一实现和独立测试。该阶段必须运行 subprocess contract、mechanism parity、旧 Workspace
fixture、CLI smoke；只有 trace 不一致时才运行长任务定位。

### N4：Agent、RunLoop 与 Memory 内部模块化

- 只做 move/extract，第一轮不改条件表达式、调用顺序、默认值或异常边界。
- 每个切片限制在一个职责和一组消费方测试。
- 完成整个阶段后才运行一次 3-seed/Worker=2 候选门禁。

目标是将修改后的普通模块控制在约 500–800 行、单函数控制在 120 行内。此阶段总行数可能基本不变；
验收关注可测试性和依赖方向，不以删行强行驱动设计。

### N5：Solver 与 Resource Runtime 结构拆分

- 先提取纯数据转换和无副作用 decision helper，再提取有状态组件。
- 每次拆分保持 solver/controller 外部入口、event 顺序、锁边界和恢复语义。
- `solver.py` 和 observer controller 的第一目标是各自降到 2,500 行以内；新组件原则上不超过
  800 行，例外需在阶段记录中解释。

该阶段风险最高。每个切片运行相关 mechanism benchmark；阶段末运行完整 parity、3-seed/Worker=2
Circle Packing、Resume 和 CLI 交互验证。

### N6：最终清理与独立演进确认

- 删除已经跨一个版本周期且无调用者的 facade。
- 更新架构图、README、依赖边界与跨仓 compatibility matrix。
- DeepCraft 与 ScienceFlow 分别打 Git 检查点；不增加 PyPI 发布。

## 4. 快速验证策略

开发期使用并行快速门禁，避免纯工程移动反复花费长时实验：

1. 变更文件的 Ruff/compile/import；
2. DeepCraft unit/contract 与 ScienceFlow 受影响测试并行执行；
3. Runtime parity quick 以 4 个进程比较 Context、Mechanism、Workspace 和 failure；
4. 阶段边界运行 CLI `tools schema`、generic repl/session、旧 Workspace Resume；
5. 仅 N4、N5 或 Prompt/Schema/调度/默认值发生变化时运行三 seed、Worker=2 真实任务。

可接受差异只包括已登记的时间戳、PID、临时绝对根路径和外部 request id。任何新增忽略项必须记录
生产者、原因和风险。以下任一变化直接阻断合并：

- provider payload、Tool Schema、ToolCall 参数或调用次数不同；
- Stage/Gate/ESTRA/Resource/Merge event 顺序或决定不同；
- Workspace 路径、文件集合、JSON/JSONL 内容或顺序不同；
- Resume 旧 Workspace 失败；
- 真实任务指标超出既有 paired gate 容差，或 wall-clock/资源开销明显回退。

## 5. 代码量预期

在不删除 ScienceFlow 功能的前提下，合理目标是 ScienceFlow 净减少约 1,000–2,500 行：兼容 facade
与 wrapper 合并贡献 300–800 行，通用 Bash/Replay 机制移出 350–900 行，其余来自拆分过程中发现的
真实重复。DeepCraft 预计增加 300–700 行，因此两个仓库合计净减少约 300–1,500 行。

`solver.py`、resource controller、Memory Context 的拆分主要降低单文件和单函数复杂度，不应承诺大量
删行。若为了达到行数目标而合并控制分支、改变事件顺序或压缩兼容逻辑，应放弃该删行目标。

## 6. 建议的下一步

先执行 N1，再执行 N2。两者风险最低，能够清除迁移后最明显的重复入口，并为 N3 的 DeepCraft 新
API 设计提供稳定消费边界。N1/N2 完成且 quick parity 为 0 diff 后，再单独评审 Bash transport API；
不要直接从 `solver.py` 或 Memory Context 开始大规模搬运。
