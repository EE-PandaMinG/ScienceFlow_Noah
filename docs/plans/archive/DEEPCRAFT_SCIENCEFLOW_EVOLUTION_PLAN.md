# DeepCraft Agent Runtime 与 ScienceFlow 独立演进规划

> 2026-08-23 起的剩余阶段、原子迁移边界和执行门禁见
> `DEEPCRAFT_SCIENCEFLOW_COMPLETION_PLAN_2026-08-23.md`。本文继续保留总体架构、功能矩阵
> 和发布原则，阶段状态以收口执行规划及后续阶段记录为准。

> **状态刷新（2026-08-23）：** 原规划已经完成。DeepCraft 已作为独立私有 Git 仓库发布
> `v0.1.2`，ScienceFlow 已删除仓内副本并通过固定 Git tag/commit 消费；默认 Runtime、CLI
> 组合、MCP optional extra、独立测试与跨仓 CI 均已落地。最终验证为 DeepCraft
> `136 passed, 1 skipped`、ScienceFlow `1677 passed, 3 skipped`，完整 Runtime parity 差异为 0。
> 具体交付状态见 `DEEPCRAFT_GIT_RELEASE_SEPARATION_STAGE_2026-08-23.md`；本文后续阶段表仅作为
> 迁移过程的历史记录，不再表示当前未完成项。

## 1. 背景

当前仓库同时包含 DeepCraft 与 ScienceFlow：

- DeepCraft 提供 `Message`、`Memory`、LLM、Tool、`BaseAgent` 等基础能力。
- ScienceFlow 在 DeepCraft 之上实现长时程科研 Agent，包括 Stage、Gate、Evaluator、ESTRA、Workspace Snapshot、Resume、资源控制、多 Worker 和结果合并。
- 一部分通用 Agent Runtime 能力仍位于 `scienceflow`，DeepCraft 也包含 ScienceFlow 未使用的 reasoning agent、Tool Extension、向量检索和重型可选依赖。
- 当前测试主要集中在仓库根目录 `tests/`，底座契约、ScienceFlow 业务行为和跨层集成测试尚未形成清晰边界。

后续需要让两个项目能够独立发布和演进：

1. **DeepCraft** 成为最轻量、稳定、领域无关的 Agent Runtime。
2. **ScienceFlow** 只依赖 DeepCraft 的公开契约，继续独立演进科研工作流。
3. 拆分测试所有权和 CI，避免一个项目修改时必须理解另一个项目的内部实现。
4. 整个迁移过程不得造成 ScienceFlow 功能、行为、数据兼容性或性能缺失。

### 1.1 历史执行状态（2026-08-22，已归档）

以下表格记录 2026-08-22 时的迁移中间状态：

| 阶段 | 状态 | 已完成/剩余工作 |
| --- | --- | --- |
| 阶段 0：基线与测试清点 | 已完成 | 已保存 Worker=1/2 Circle Packing 基线、两轮改造后样本和 Workspace Contract；3-seed/worker=2 配对效果与 Workspace 门禁已于 2026-08-22 通过。 |
| 阶段 1：DeepCraft 公共契约 | 部分完成 | 独立 Runtime、LLM/Tool/Memory/Event/CLI、AgentState 及通用 Resume 契约已建立；ScienceFlow 的兼容 BaseAgent 已由 DeepCraft 自身实现，不再要求默认安装 `deepcraft-agent`。 |
| 阶段 2：测试物理拆分 | 已完成（单仓库） | DeepCraft 自有测试、ScienceFlow 测试和跨层契约门禁已经分开；独立仓库 CI 属于阶段 7。 |
| 阶段 3：Event 与 JSONL | 部分完成 | 通用 JSONL、恢复与可选双写已经完成；现有 ScienceFlow 日志仍是唯一权威输出，尚未迁移后删除旧实现。 |
| 阶段 4：LLM 与 Tool 基础层 | 部分完成 | 独立 Adapter、确定性 record/replay、同轮 retry、tool-call 解析、endpoint pool、provider error、PooledLLM failover、legacy LLM factory、stream guard、telemetry、Tool bundle 调度、subprocess 生命周期与 shell reducer 已下沉并通过契约测试；ScienceFlow 默认 client 仍为兼容期 legacy OnlineLLM。 |
| 阶段 5：RunLoop 与 Memory 迁移 | 部分完成 | Resume、store、历史 record IO/window repair、Workspace prefix rewrite、legacy Memory mutation/recent-round prune、BaseAgent/AgentState 兼容实现以及 RunLoop retry/tool-call 通用机制已下沉，并通过 strict replay、旧 Workspace fixture 和三 seed Resume 门禁；主 RunLoop、Message/Memory/ToolResult/ToolCollection 类型身份与 ScienceFlow Memory Policy 尚未迁移。 |
| 阶段 6：切换默认 Runtime | 未完成 | 第一阶段新任务门禁和本次 exact-start Memory Resume 三 seed 效果门禁通过，`scientific-design` extra 测试已补齐；完整 backend replay、无软链接歧义的 Workspace gate、其他真实代表任务和主 RunLoop 迁移仍未完成，因此不得切换或删除旧 Runtime。 |
| 阶段 7：独立仓库/发布 | 未完成 | DeepCraft 和 ScienceFlow 尚未拆成独立仓库、版本和发布流水线。 |
| 阶段 8：清理 | 部分完成 | 默认依赖已轻量化，MCP 作为 optional extra 保留；兼容 facade、旧 Runtime 和未使用集成源码需等前述门禁通过后清理。 |

以上未完成项已在 2026-08-23 收口；当前状态以本节顶部状态刷新和最终阶段记录为准。

## 2. 核心原则

### 2.1 单向依赖

```text
ScienceFlow  ────────>  DeepCraft
DeepCraft    ──X────>  ScienceFlow
```

- DeepCraft 代码、测试、配置和依赖中不得引用 `scienceflow`。
- ScienceFlow 只能使用 DeepCraft 的公开 API，不得引用其 `_internal` 模块。
- ScienceFlow 特有概念不得进入 DeepCraft，例如 Stage、Metric、Gate、Evaluator、ESTRA、GPU Lease 和 Task Package。

### 2.2 机制与策略分离

- DeepCraft 固化通用机制：LLM 调用、Agent 循环、工具执行、消息与会话存储、运行事件、取消和超时。
- ScienceFlow 实现科研策略：何时提交 Stage、如何验证指标、何时回退、如何分配资源、如何合并结果。
- ScienceFlow 通过 Hook、Middleware、Protocol 和扩展事件接入 DeepCraft，不通过修改 DeepCraft 内部流程实现功能。

### 2.3 先兼容迁移，后删除旧实现

- 新旧实现并行存在期间，默认仍可选择旧路径。
- 每个迁移切片必须独立通过功能、序列化、恢复和性能验收。
- 只有当新路径满足全部验收条件后，才能删除兼容层和旧实现。
- 不在底座抽取的同时重写 LNR、资源控制算法或 Prompt。

### 2.4 不可协商的 ScienceFlow 等效性要求

本规划中的“无功能和性能缺失”是发布硬条件，不是优化目标或尽力而为。完成底座抽取后，ScienceFlow 必须满足：

- 在相同代码、配置、模型、数据、Workspace、随机种子和外部响应下，执行路径和可观察结果等效。
- 不改变 Prompt 文本、消息顺序、Tool 名称、Tool Schema、Tool Choice、模型参数、重试策略、超时、上下文压缩阈值和 LLM 调用时机。
- 不改变 Stage Capture、Gate、Evaluator、ESTRA、Snapshot、Resume、资源控制、多 Worker 和 Merge 的触发条件与决策语义。
- 不增加或减少非预期的 LLM 调用、工具调用、Evaluator 调用和资源审查调用。
- 不降低具体任务的完成率、最终指标、稳定性和可恢复性。
- 不改变现有 Workspace 的外部契约，包括目录、文件名、日志、Memory、JSON/JSONL、配置文件、Snapshot Manifest、提交物和软链接。
- 新版本必须能够继续 Resume 旧版本创建的 Workspace；迁移期间旧版本也应能够读取未发生显式 schema 升级的新 Workspace。

如果内部实现改为 DeepCraft Event、Memory 或 Runtime，新实现必须通过 ScienceFlow Compatibility Adapter 继续产生现有外部格式。内部重构不构成修改外部文件契约的理由。

### 2.5 分层验证与时间预算

纯代码归属迁移、裁剪和兼容 facade 合并不再逐切片重复运行长时真实任务。验证按变更风险分层：

1. 每个纯工程切片运行 DeepCraft unit/contract、ScienceFlow 消费方契约、确定性 replay、旧 Workspace fixture、import/lint 门禁，目标耗时 1–3 分钟。
2. 一个迁移阶段完成后运行 1 seed、短 wall-clock budget 的真实 CLI/LLM smoke，验证配置、进程、Workspace 和 evaluator 链路。
3. 只有 Prompt、Tool Schema、调度、算法、默认 Runtime 切换或发布候选发生变化时，才运行完整 3-seed/Worker=2 配对效果门禁。
4. 已保存且输入契约未变化的 baseline 必须复用；最终收口只补 candidate，禁止为每个内部重构重复生成两侧结果。

分层只减少重复的随机长任务，不降低发布硬门禁。完整三 seed 效果、性能和 Workspace 契约仍在默认 Runtime 切换与最终发布前执行一次。

## 3. 目标职责边界

### 3.1 DeepCraft 职责

DeepCraft 最小底座只保留以下能力。

#### Agent Runtime

- `BaseAgent` 与 Agent 生命周期状态。
- 单轮和多轮运行循环。
- Run Policy、自动继续、停止和取消。
- LLM 与 Tool Call 调度。
- 通用异常处理和恢复入口。
- Runtime Hook 与 Middleware 调用。

#### LLM

- `LLMClient` Protocol。
- OpenAI-compatible Adapter。
- 文本与 Tool Call 流式输出。
- reasoning content 兼容。
- 超时、重试、错误分类和 Client 生命周期。
- Token Usage、Cached Token 和调用统计。
- 通用多 Key Pool、sticky routing 和故障切换。

#### Tool

- `BaseTool`、`ToolCall`、`ToolResult`。
- `ToolCollection` 与 `ToolExecutor`。
- 顺序和并行执行。
- 工具超时、取消和输出流。
- 通用 Tool Hook 与 Middleware。

DeepCraft 可以提供轻量的通用文件和 Shell 工具，但不得包含 ScienceFlow 的 GPU admission、训练进度判断、资源仲裁和 Stage 捕获逻辑。

#### Message 与 Memory

- Message、Role 和 Tool Turn 数据模型。
- Conversation Store。
- JSON/JSONL 会话持久化。
- 基础消息窗口和一致性检查。
- 会话加载、保存与通用恢复。

#### Runtime Event

- 统一事件 envelope。
- `EventSink`、`JsonlEventSink` 和 `CompositeEventSink`。
- 事件顺序、刷新、关闭和错误隔离。
- 面向实时 Monitor 和离线回放的稳定 JSONL 契约。

#### 基础 CLI

- 独立的 `deepcraft` 命令入口。
- 最小 `run` 和 `repl` Agent 命令。
- Tool 列表与 Tool Schema 查看。
- Session/Event JSONL 查看和回放入口。
- 可复用的参数模型、Runtime Factory 和 Command Registry。
- 面向上层项目的 CLI Extension API。

DeepCraft CLI 只操作通用 Agent Runtime，不得包含 LNR、Stage、Evaluator、ESTRA、资源控制和任务包参数。

### 3.2 ScienceFlow 职责

以下能力完整保留在 ScienceFlow：

- `ScienceAgent` 及科研 Prompt。
- Stage Capture、Stage Ledger 和 Stage Memory。
- Gate 与 Evaluator。
- ESTRA、上下文重建、回退和重定向。
- Workspace Snapshot、Restore、Resume 和 Replay Prepare。
- Resource Runtime、GPU Queue、Lease、Review 和 Intervention。
- 数据与提交物安全检查。
- 多 Worker、Global Merge 和 Final Artifact。
- Task Package、MLE-bench、SciModelingBench 与优化任务适配。
- ScienceFlow Monitor、Trace、Dashboard 和科研指标统计。

## 4. DeepCraft 目标包结构

DeepCraft 最终作为一个独立 Python 包发布，避免继续依赖仓库级 `sys.path` 注入。

```text
deepcraft/
├── pyproject.toml
├── src/deepcraft/
│   ├── __init__.py
│   ├── agent/
│   │   ├── base.py
│   │   ├── runtime.py
│   │   ├── policy.py
│   │   └── hooks.py
│   ├── llm/
│   │   ├── protocol.py
│   │   ├── models.py
│   │   ├── openai_adapter.py
│   │   ├── pool.py
│   │   └── usage.py
│   ├── tools/
│   │   ├── base.py
│   │   ├── collection.py
│   │   ├── context.py
│   │   └── executor.py
│   ├── memory/
│   │   ├── message.py
│   │   ├── conversation.py
│   │   └── store.py
│   ├── events/
│   │   ├── models.py
│   │   ├── sink.py
│   │   └── jsonl.py
│   ├── cli/
│   │   ├── app.py
│   │   ├── context.py
│   │   ├── registry.py
│   │   ├── runtime_factory.py
│   │   └── commands/
│   └── _internal/
└── tests/
    ├── unit/
    ├── contract/
    ├── integration/
    └── performance/
```

`deepcraft-core` 和 `deepcraft-agent` 最终合并为单一 `deepcraft` 分发包。MCP 作为受支持的 optional extra 保留，不进入最小安装。仓库审计确认 ScienceFlow 生产路径未使用 Browser、向量检索和 LiteLLM，因此它们不再由顶层 `deepcraft` 分发包暴露；兼容迁移完成前只保留旧源码，不作为新 Runtime 的受支持能力。

### 4.1 依赖分层

建议的安装层次：

```toml
deepcraft                 # 数据模型、Runtime、Tool、Memory、Event、基础 CLI
deepcraft[openai]         # OpenAI-compatible Adapter 和重试依赖
deepcraft[tokens]         # tiktoken 精确估算
deepcraft[mcp]            # MCP Adapter
deepcraft[dev]            # 测试、覆盖率、Lint 和 Benchmark
```

基础 CLI 是 DeepCraft 默认能力，Click 作为唯一 CLI 基础依赖；Rich 保持可选。ScienceFlow 显式依赖满足其完整功能需要的 extra，例如 `deepcraft[openai]`，因此 DeepCraft 的最小安装变轻不会削弱 ScienceFlow。`import deepcraft` 不应加载 Click、Rich 或具体 LLM Adapter；只有 CLI 入口和相关模块按需加载这些依赖。

## 5. 稳定公开契约

### 5.1 LLM 契约

```python
class LLMClient(Protocol):
    async def complete(self, request: CompletionRequest) -> CompletionResult: ...
    async def stream(self, request: CompletionRequest) -> StreamHandle: ...
    async def aclose(self) -> None: ...
```

迁移后必须继续支持：

- OpenAI-compatible 消息格式。
- 多个并行 Tool Call。
- Tool arguments 增量流。
- reasoning content。
- Usage、Cached Token、TTFT 和 TPOT。
- 连接复用、超时、重试和多 Key 路由。

### 5.2 Tool 契约

```python
@dataclass
class ToolContext:
    session_id: str
    run_id: str
    agent_id: str
    workspace: Path
    event_sink: EventSink
    cancellation: CancellationToken
    metadata: dict[str, Any]


class BaseTool(Protocol):
    name: str
    description: str
    input_schema: dict[str, Any]

    async def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult: ...
```

迁移期保留当前 `tool_input` 和额外回调参数的兼容 Adapter，避免一次性修改全部 ScienceFlow 工具。

### 5.3 Runtime Hook 契约

DeepCraft 至少提供以下扩展点：

```python
class AgentHooks:
    async def before_round(self, context): ...
    async def before_llm(self, request, context): ...
    async def after_llm(self, result, context): ...
    async def before_tool(self, call, context): ...
    async def on_tool_stream(self, chunk, context): ...
    async def after_tool(self, call, result, context): ...
    async def on_context_limit(self, context): ...
    async def on_error(self, error, context): ...
    async def should_continue(self, context): ...
    async def after_round(self, context): ...
```

ScienceFlow 的 Stage Capture、ESTRA、资源控制、上下文卫生和停止策略通过这些 Hook 接入。Hook 顺序属于公开契约，必须有 Contract Test。

### 5.4 JSONL 事件契约

```json
{
  "schema_version": "1.0",
  "sequence": 42,
  "event_id": "evt_...",
  "timestamp": "2026-08-22T15:30:00Z",
  "session_id": "session_...",
  "run_id": "run_...",
  "agent_id": "W00",
  "turn_id": 12,
  "parent_event_id": "evt_parent",
  "type": "tool.completed",
  "payload": {}
}
```

DeepCraft 内置事件命名：

```text
session.started
session.completed
agent.turn.started
agent.turn.completed
llm.requested
llm.completed
llm.failed
tool.requested
tool.started
tool.completed
tool.failed
memory.appended
runtime.warning
```

ScienceFlow 使用命名空间扩展：

```text
scienceflow.stage.committed
scienceflow.gate.rejected
scienceflow.evaluator.completed
scienceflow.estra.redirected
scienceflow.resource.lease_granted
```

大输出不得直接无限写入 JSONL。应写入 Artifact，并在事件中保存 `artifact_ref`、摘要、SHA256、字节数和有限预览。

### 5.5 CLI 契约

DeepCraft 提供独立基础 CLI，同时提供可被 ScienceFlow 组合使用的 CLI API。ScienceFlow 不应通过子进程调用 `deepcraft` 命令，而应直接复用 Command Handler、参数模型和 Runtime Factory。

#### DeepCraft 独立命令

建议的最小命令面：

```text
deepcraft run             # 执行一个通用 Agent 任务
deepcraft repl            # 启动通用 Agent REPL
deepcraft tools list      # 查看已注册工具
deepcraft tools schema    # 查看工具输入 Schema
deepcraft events show     # 查看或过滤 Runtime JSONL
deepcraft events replay   # 回放 Session/Event
```

首个稳定版本可以只实现 `run`、`repl`、`tools list` 和 `events show`；其余命令在契约稳定后增加。

DeepCraft 和 ScienceFlow 分别保留自己的可执行入口：

```toml
# DeepCraft pyproject.toml
[project.scripts]
deepcraft = "deepcraft.cli.app:main"

# ScienceFlow pyproject.toml
[project.scripts]
scienceflow = "scienceflow.cli:main"
```

#### 可组合 CLI API

```python
class RuntimeFactory(Protocol):
    def create_runtime(self, options: RuntimeOptions) -> AgentRuntime: ...


class CliExtension(Protocol):
    name: str

    def register(self, registry: CommandRegistry) -> None: ...
```

基础 CLI 应提供：

- `CommandRegistry`：注册命令和子命令，但不持有 ScienceFlow 逻辑。
- `CommandContext`：传递配置、Runtime Factory、Event Sink 和退出控制。
- `RuntimeOptions`：通用模型、Workspace、Session、Tool 和日志参数。
- `RuntimeFactory`：将 CLI 参数转换为 Agent Runtime，支持 ScienceFlow 替换工厂。
- `CliExtension`：由 ScienceFlow 注册领域命令。

#### ScienceFlow 的使用方式

ScienceFlow 保留自己的 `scienceflow` 可执行入口和现有命令语义：

```text
scienceflow run
scienceflow repl
scienceflow parallel
scienceflow monitor
scienceflow monitor-trace
scienceflow resource-summary
scienceflow replay-prepare
```

其中：

- `scienceflow run` 仍表示 LNR 科研任务，不改成 DeepCraft 的普通 Agent Run。
- `scienceflow repl` 保留现有配置、Workspace 和 Prompt 行为。
- 通用参数解析、LLM 创建、Session、Tool、Event Sink 和退出处理复用 DeepCraft CLI 组件。
- `parallel`、`monitor`、`resource-summary` 等领域命令由 ScienceFlow 的 `CliExtension` 注册。
- 如需暴露不带科研工作流的原始 Agent，可增加 `scienceflow agent run` 和 `scienceflow agent repl`，但不能替换现有命令。

建议的组合方式：

```python
from deepcraft.cli import create_cli
from scienceflow.cli_commands import ScienceFlowCliExtension

app = create_cli(
    name="scienceflow",
    runtime_factory=ScienceFlowRuntimeFactory(),
    extensions=[ScienceFlowCliExtension()],
)
```

#### CLI 兼容要求

- ScienceFlow 现有命令名称、主要参数和默认值保持兼容。
- 命令退出码属于公开行为，必须有 Contract Test。
- `--help` 和配置检查不得初始化 LLM、扫描数据集或加载 ML/CUDA 依赖。
- CLI Handler 不直接 `sys.exit()`；应返回结构化结果或抛出标准 CLI 异常，由入口统一转换退出码。
- CLI 输出区分人类可读输出和 `--json` 机器输出；JSON 输出必须有版本字段。
- DeepCraft CLI 不读取 ScienceFlow 配置文件；ScienceFlow Runtime Factory 负责自己的配置合并。
- CLI Extension API 按 SemVer 管理，破坏性变化只能进入 DeepCraft major 版本。

## 6. 两个项目的独立演进策略

### 6.1 独立版本

- DeepCraft 使用独立 SemVer，例如 `deepcraft==1.x`。
- ScienceFlow 使用独立版本，不与 DeepCraft 版本绑定。
- ScienceFlow 声明明确兼容范围，例如：

```toml
dependencies = [
    "deepcraft[openai]>=1.2,<2.0",
]
```

- DeepCraft 破坏公开契约时必须发布 major 版本。
- 可迁移的 API 至少保留一个 minor 版本的弃用周期。
- DeepCraft 通用 JSONL schema 独立版本化；包版本升级不应无条件导致事件 schema 升级。ScienceFlow 已存在的 Workspace JSON/JSONL 属于 ScienceFlow 外部兼容契约，不得因为采用 DeepCraft Event 而自动替换、改名或改变字段语义。

### 6.2 兼容矩阵

ScienceFlow 仓库维护兼容矩阵：

| ScienceFlow | DeepCraft 最低版本 | DeepCraft 最高版本 | 状态 |
|---|---:|---:|---|
| `0.x` | `1.0` | `<2.0` | 计划 |

ScienceFlow CI 至少验证：

1. 声明范围内的最低 DeepCraft 版本。
2. 当前锁定版本。
3. 最新兼容版本。

DeepCraft 的主分支预发布版本可以进入 ScienceFlow 的非阻塞 nightly CI，用于提前发现兼容性问题。

### 6.3 发布顺序

涉及跨项目的新能力时：

1. DeepCraft 先增加向后兼容的底座能力并发布。
2. ScienceFlow 升级最低版本并使用新能力。
3. ScienceFlow 完成迁移后，DeepCraft 才能在后续 major 版本删除旧 API。

不得要求 ScienceFlow 依赖 DeepCraft 的未发布提交作为正式运行方式。

## 7. 测试拆分规划

### 7.1 测试所有权原则

- 测试跟随行为所有者，而不是跟随历史文件位置。
- DeepCraft 测试不得 import `scienceflow`。
- ScienceFlow 单元测试可以 mock DeepCraft 公开 Protocol，但不得 mock DeepCraft 私有实现。
- ScienceFlow 集成测试必须使用真实 DeepCraft 包验证端到端行为。
- 跨项目契约应同时有“提供方契约测试”和“消费方兼容测试”。
- 测试依赖进入各自的 `dev` extra，不进入运行时默认依赖。

### 7.2 DeepCraft 测试目录

```text
deepcraft/tests/
├── unit/
│   ├── agent/
│   ├── llm/
│   ├── tools/
│   ├── memory/
│   ├── events/
│   └── cli/
├── contract/
│   ├── test_llm_protocol.py
│   ├── test_tool_protocol.py
│   ├── test_hook_order.py
│   ├── test_event_schema.py
│   ├── test_jsonl_replay.py
│   └── test_cli_extension_protocol.py
├── integration/
│   ├── test_minimal_agent.py
│   ├── test_streaming_tool_agent.py
│   ├── test_cancel_and_timeout.py
│   ├── test_session_resume.py
│   └── test_cli_commands.py
└── performance/
    ├── test_event_sink_benchmark.py
    ├── test_tool_dispatch_benchmark.py
    ├── test_stream_overhead_benchmark.py
    └── test_cli_startup_benchmark.py
```

### 7.3 ScienceFlow 测试目录

```text
tests/
├── unit/
│   ├── gates/
│   ├── evaluator/
│   ├── stage/
│   ├── estra/
│   ├── snapshots/
│   ├── resource/
│   ├── merge/
│   ├── task_package/
│   └── ui/
├── contract/
│   ├── test_deepcraft_adapter.py
│   ├── test_scienceflow_hooks.py
│   ├── test_scienceflow_event_extensions.py
│   ├── test_workspace_compatibility.py
│   └── test_deepcraft_cli_extension.py
├── integration/
│   ├── test_repl_runtime.py
│   ├── test_lnr_single_worker.py
│   ├── test_lnr_multi_worker.py
│   ├── test_stage_gate_evaluator.py
│   ├── test_estra_restore.py
│   ├── test_resource_runtime.py
│   └── test_resume_existing_workspace.py
├── e2e/
│   ├── test_circle_packing.py
│   ├── test_artifact_command.py
│   └── test_task_package.py
└── performance/
    ├── test_lnr_runtime_overhead.py
    ├── test_snapshot_performance.py
    └── test_monitor_event_throughput.py
```

### 7.4 现有测试的初步归属

以下按测试行为迁移，具体文件清单在实施时记录到 `tests/ownership.yaml`。

| 当前测试主题 | 目标所有者 |
|---|---|
| Message、Memory 基础存储、BaseAgent | DeepCraft |
| StreamHandle、LLM Streaming、Usage、Key Pool | DeepCraft |
| BaseTool、ToolCollection、通用并行调度 | DeepCraft |
| JSONL EventSink、通用 Interaction Event | DeepCraft |
| 基础 CLI、Runtime Factory、Command Registry | DeepCraft |
| ScienceAgent Prompt、写入提醒、工具保护策略 | ScienceFlow |
| ScienceFlow 命令、Manifest 和领域参数 | ScienceFlow |
| LNR、Stage、ESTRA、Resume、Snapshot | ScienceFlow |
| Gate、Evaluator、Artifact Contract | ScienceFlow |
| Resource Runtime、GPU、Queue、Review | ScienceFlow |
| Monitor、Trace、Task Package、Benchmark Adapter | ScienceFlow |
| DeepCraft Hook 与 ScienceFlow 行为衔接 | ScienceFlow Contract/Integration |

当前部分测试同时验证底座机制和 ScienceFlow 策略，不能直接移动。应先拆成两个测试：

1. DeepCraft 测试通用机制和稳定契约。
2. ScienceFlow 测试基于该契约实现的科研行为。

### 7.5 测试 Fixture 与 Golden 数据

- DeepCraft 维护通用 Message、Tool Call、Event 和 JSONL Golden Fixture。
- ScienceFlow 维护 Stage、Evaluator、ESTRA、Resource 和完整 Run Golden Fixture。
- Fixture 中不得包含真实 API Key、用户绝对路径或不可公开的数据。
- Golden 比较以语义一致为主；`timestamp`、UUID 和耗时字段使用标准归一化器。
- 旧工作区 Fixture 必须长期保留，用于验证向后恢复能力。

### 7.6 Workspace Compatibility Fixture

ScienceFlow 需要从迁移前的真实轻量任务生成一套只读兼容 Fixture，至少包含：

- 单 Worker 正常完成 Workspace。
- 多 Worker 和 Merge Workspace。
- 至少包含两个 Stage 和一次 ESTRA 的 Workspace。
- 运行中断后可 Resume 的 Workspace。
- Resource Runtime 开启的 Workspace。
- Evaluator 成功、拒绝和缓存命中的 Workspace。

每个 Fixture 同时保存：

1. 完整相对路径树、文件类型、权限和软链接目标。
2. JSON/JSONL/CSV/Markdown 文件内容或内容摘要。
3. JSON schema、必需字段、字段类型和枚举值。
4. JSONL 事件类型、事件顺序和关键关联 ID。
5. 配置输入、展开后的有效配置和环境覆盖结果。
6. Resume 前后的状态、Stage、Memory 和最终产物摘要。

Fixture 比较分为两层：

- 对稳定内容进行 byte-for-byte 比较。
- 只对时间戳、UUID、PID、耗时和绝对路径等已登记的易变字段做标准化后比较。不得使用宽泛的“忽略所有未知字段”规则掩盖回归。

## 8. 功能零缺失验收矩阵

### 8.1 Workspace 外部契约

Workspace 是 ScienceFlow 的持久 API，而不是内部临时目录。以下属性必须保持：

- 相对目录结构和文件生成位置。
- 文件名、后缀、编码、换行和追加/覆盖语义。
- JSON/JSONL 字段、类型、语义和事件顺序。
- Memory Record 的角色、Tool Call ID、消息顺序和序列化格式。
- Snapshot Manifest、对象引用、恢复保留目录和文件选择规则。
- Interaction Log 的路径、格式、裁剪规则和 Stream 写入行为。
- Stage、Evaluator、Resource、Merge 和 Monitor 读取的全部文件契约。
- 文件原子替换、flush 时机和进程异常后的可恢复状态。

需要纳入兼容清单的代表性文件包括但不限于：

```text
.agent_memory/**/short_term.json
.agent_memory/**/long_term.jsonl
.logs/interaction/interaction.log
.logs/traj_interaction/traj_interaction.log
.run_results.md
lhr_state.json
lhr_stage_map.json
lhr_events.jsonl
lhr_stage_events.jsonl
lhr_stage_commit_events.jsonl
lhr_estra_events.jsonl
lhr_estras.jsonl
lhr_context_events.jsonl
lhr_resume_events.jsonl
lhr_stage_memory_events.jsonl
lhr_stage_performance.csv
evaluator_events.jsonl
evaluator_cache.jsonl
resource_events.jsonl
resource_state.json
worker_results.json
global_candidates.jsonl
global_stage_map.json
global_merge_manifest.json
selected_candidate.json
monitor_state.json
snapshot manifests and object references
submission.csv and configured candidate artifacts
```

实际契约以迁移阶段生成的完整 `workspace_contract_manifest.json` 为准，不能只保护上述示例。该 Manifest 应记录路径、生产者、消费者、格式版本、写入模式、是否可选和兼容测试。

允许内部新增 DeepCraft 通用事件文件，但不得移动、删除、改名或改变现有 ScienceFlow 文件。若新增文件可能被 Agent、Snapshot 或 Merge 扫描到，必须更新隐藏路径和排除规则，确保任务行为不受影响。

### 8.2 配置外部契约

以下配置行为必须保持完全兼容：

- 默认值及其生效时机。
- YAML `include` 顺序和相对路径解析。
- Manifest defaults、task override、profile override 的优先级。
- 环境变量、CLI 参数和配置文件之间的覆盖顺序。
- 资源控制 mode 展开结果。
- 未知字段、空值、布尔值和列表的兼容处理。
- Workspace、任务包和 Python executable 的路径解析。
- 序列化后的有效配置和下游子进程环境变量。

迁移前应为每个维护中的示例 Manifest 保存“输入配置 → 展开后 Config”的 Golden Fixture。新旧 Runtime 必须产生等效的 Config 对象和子进程环境。

### 8.3 具体任务效果契约

具体任务效果不能只通过单元测试判断，需要两类验证：

#### 确定性 Replay

- 录制并脱敏 LLM Response、Streaming Chunk、Tool Result 和 Evaluator Result。
- 新旧 Runtime 消费同一套录制数据，避免模型随机性干扰。
- 比较 Prompt、消息序列、Tool Call、Stage、ESTRA、资源决策、Memory、Workspace 和 Final Artifact。
- 除登记的易变字段外，要求结果严格一致。

#### 真实端到端任务

- 使用相同模型、参数、数据、时间预算、随机种子和硬件资源运行新旧路径。
- 覆盖优化任务、MLE 任务以及启用资源控制和多 Worker 的代表任务。
- 比较任务成功率、首个有效指标时间、最佳指标、Stage 产出、恢复成功率和最终 Artifact 有效性。
- 对具有模型随机性的任务进行多次重复，比较均值、方差和失败类型；新路径不得出现统计显著或工程上可观察的退化。
- 任何指标改善不能抵消功能、文件兼容性或稳定性回归。

#### Circle Packing 配对门禁（已通过）

Circle Packing 不再用单次高分或低分决定 Runtime 切换。reference 和 candidate 分别运行 seed `2222`、`3333`、`4444`，每个 seed 保持 `worker=2`，每组三个 seed 并行。两边的模型、任务、CPU 分配、900 秒 LNR 预算、Evaluator、Gate 及除 workspace/run identity 外的 Manifest 必须一致。

Live LLM 门禁通过环境变量显式开启，默认执行路径和 `resolved_config.yaml` schema 不变：

```bash
SCIENCEFLOW_DETERMINISTIC_GATE=1 \
SCIENCEFLOW_DETERMINISTIC_GATE_TIMESTAMP_UTC=2000-01-01T00:00:00Z \
uv run python -m scienceflow.cli parallel \
  -m scripts/circle_packing_3seed_gate_reference.yaml -j 3

SCIENCEFLOW_DETERMINISTIC_GATE=1 \
SCIENCEFLOW_DETERMINISTIC_GATE_TIMESTAMP_UTC=2000-01-01T00:00:00Z \
uv run python -m scienceflow.cli parallel \
  -m scripts/circle_packing_3seed_gate_candidate.yaml -j 3
```

开启后只对门禁运行稳定 provider 可见输入：固定 ResourceContext 时间和 Git commit 时间，固定 runtime budget 文本，把 `LNR seed + worker index` 传给 OpenAI-compatible request，稳定哈希 vLLM 随机 tool-call ID，并从 Bash 结果头移除动态耗时。普通运行不发送 provider seed、不改提示、不改 Git 时间、不改 Bash 输出，也不新增配置字段。

结果使用配对脚本判定：

```bash
uv run python scripts/circle_packing_effect_gate.py \
  --reference-root workspaces/circle_packing_3seed_gate_reference \
  --candidate-root workspaces/circle_packing_3seed_gate_candidate \
  --output docs/baselines/circle_packing/three_seed_effect_gate_report.json
```

默认要求三个 seed 均完成且 evaluator valid/eligible；每个 seed、三 seed 中位数和最差 seed 的 `radii_sum` 均不得下降；每个 seed 和中位耗时不得超过 reference 的 10%。Live seeded 门禁用于降低服务调度噪声，但不能替代上面的严格录制 Replay：Agent 主动执行的外部程序仍可能产生任务自身的非确定输出。

### 8.4 验收矩阵

迁移前建立功能清单，迁移后逐项验收。

| 能力 | DeepCraft 保证 | ScienceFlow 保证 | 必须验证 |
|---|---|---|---|
| LLM Streaming | 流和错误语义 | Prompt 与模型配置 | Chunk、TTFT、最终内容 |
| Tool Call | 调度和结果模型 | 工具策略与保护 | Schema、顺序、并行性 |
| Memory | 存储和基础恢复 | 压缩、继承和 Stage Memory | 消息顺序、恢复结果 |
| JSONL | 通用事件与写入 | 扩展事件与 Monitor | Schema、顺序、可回放 |
| CLI | 命令框架、通用 Handler | 领域命令与配置映射 | 参数、默认值、退出码 |
| Run Policy | 生命周期和 Hook | LNR/REPL 策略 | 停止原因、轮数 |
| Stage/Gate | Hook 承载能力 | 完整业务逻辑 | Stage、Metric、Artifact |
| ESTRA | Context/Restore 接口 | 决策与回退策略 | 恢复点、Memory、文件 |
| Resource | Middleware 接口 | 完整资源控制 | Admission、Lease、Stop |
| Multi-worker | 通用隔离原语 | Worker 和 Merge | 候选、Final、失败恢复 |

以下条件全部满足才允许移除旧路径：

- 全量测试通过。
- Golden Trace 语义一致。
- Workspace Contract Manifest 全部通过。
- Prompt 内容、消息顺序、Tool 名称和 Tool Schema 不变。
- LLM、Tool、Evaluator 和资源审查调用次数与时机无非预期变化。
- Stage 数量、选择结果和 Stop Reason 一致。
- 确定性 Replay 除登记的易变字段外严格一致。
- 真实任务的成功率、最终 Artifact、指标和稳定性不低于基线。
- 旧工作区可以被新版本 Resume。
- 现有日志、Memory、JSON/JSONL 和配置契约保持兼容。
- 单 Worker、多 Worker、ESTRA 和 Resource Runtime 均完成真实集成验证。

## 9. 性能零退化门禁

性能基线在迁移前固定，CI 保存历史结果。不同机器上的绝对时间仅作参考，回归判断优先使用同机对比。

| 指标 | 门禁 |
|---|---|
| LLM 调用次数 | 不增加 |
| Prompt Token | 非预期变化为 0 |
| Runtime 请求前开销 | 同机中位数和 P95 默认不得回归超过 2% |
| TTFT | 排除外部服务波动后，同机中位数和 P95 默认不得回归超过 2% |
| Streaming 吞吐 | 同一录制流回放时不低于旧路径 |
| Tool 调度开销 | 新增中位开销不超过 1 ms，P95 不超过 2 ms |
| JSONL 事件写入 | 不阻塞 LLM 和 Bash 输出流 |
| CLI `--help` 冷启动 | 不加载 LLM、数据集或 ML/CUDA 依赖 |
| CLI 命令启动开销 | 同机中位数和 P95 默认不得回归超过 2% |
| Agent 内存峰值 | 同一 Replay 默认不得回归超过 2% |
| Resume 时间 | 同一 Fixture 默认不得回归超过 2% |
| Snapshot 时间与物理大小 | 同一 Fixture 默认不得回归超过 2% |
| 任务最终指标 | 不低于基线 |

上述 2% 是默认最大容忍线，不是允许消耗的性能预算；目标仍为零退化。如果基线波动小于该范围，使用更严格门槛。JSONL 建议使用单写入者、有界队列和递增 `sequence`。Tool、Stage、异常和 Session 结束边界必须 flush；高频流式 chunk 可以聚合，但不能改变现有 ScienceFlow interaction log 的写入时机和可观察内容。

## 10. 分阶段实施

### 阶段 0：基线与测试清点

- 生成现有测试所有权清单 `tests/ownership.yaml`。
- 建立功能矩阵、Golden JSONL、确定性 Replay 和性能基线。
- 从现有真实运行生成 `workspace_contract_manifest.json` 和 Workspace Compatibility Fixture。
- 保存维护中 Manifest 的输入配置、展开后 Config 和子进程环境 Golden。
- 标记 DeepCraft、ScienceFlow 和跨层测试。
- 不移动代码，不改变行为。

### 阶段 1：DeepCraft 公共契约

- 建立新的包结构和公开入口。
- 定义 LLM、Tool、Memory、Event、Hook Protocol。
- 定义 Runtime Factory、Command Registry 和 CLI Extension Protocol。
- 为现有类型提供兼容 Alias/Adapter。
- ScienceFlow 暂不切换默认运行路径。

### 阶段 2：测试物理拆分

- 先在当前仓库内将 DeepCraft 测试移动到 `deepcraft/tests/`。
- ScienceFlow 测试按 unit、contract、integration、e2e、performance 分类。
- 拆开同时验证两层行为的测试。
- 为两个项目分别配置 pytest 和覆盖率门禁。

### 阶段 3：Event 与 JSONL 迁移

- 新旧日志接收同一运行事件并双写。
- 对新旧日志做语义对比。
- Monitor/Trace 同时支持新旧事件格式。
- 验收后可以删除重复的旧日志内部实现，但 ScienceFlow Compatibility Sink 必须继续写出原有文件名、路径和格式。除非未来通过单独的 ScienceFlow major 版本和显式迁移工具变更契约，否则不得停止现有格式输出。

### 阶段 4：LLM 与 Tool 基础层迁移

- 迁移 LLM Client、Streaming、Usage 和 Key Pool。
- 迁移 BaseTool、ToolCollection 和通用 ToolExecutor。
- 实现 DeepCraft 最小 `run`、`repl`、`tools` 和 `events` 命令。
- ScienceFlow 通过 Runtime Factory 和 CLI Extension 复用基础 CLI。
- ScienceFlow 的资源感知 Bash 行为通过 Middleware 保留。
- 保证 Prompt、Tool Schema、调用次数和回调顺序不变。

### 阶段 5：BaseAgent、RunLoop 与 Memory 迁移

- 抽取通用 Agent 状态机和 RunLoop。
- 将 ScienceFlow 行为改接 Hook，不改变业务逻辑。
- 通用 Memory Store 下沉；ScienceFlow Memory Policy 留在上层。
- 提供 `legacy` 与 `deepcraft` 两种 Runtime Backend。
- 两种 Backend 使用相同录制输入运行确定性 Replay，并比较完整 Workspace Contract。

### 阶段 6：切换默认 Runtime

- 新 Runtime 完成全量功能与性能验收。
- ScienceFlow 默认切换到 DeepCraft Runtime。
- 旧 Runtime 至少保留一个发布周期。
- 保留可立即回切的配置开关和发布回滚路径。
- 生产或长时任务验证通过后再进入删除阶段。

### 阶段 7：独立仓库和发布流水线

- DeepCraft 独立仓库、版本、CI 和 Release。
- ScienceFlow 改用已发布 DeepCraft 版本，不再使用路径注入。
- 建立最低版本、锁定版本和最新兼容版本测试矩阵。
- 建立跨项目 nightly compatibility CI。

### 阶段 8：依赖与兼容代码清理

- 重型依赖移入 DeepCraft optional extras 或插件。
- 删除未使用的 reasoning agents 和 Tool Extension 默认依赖。
- 删除已完成迁移的旧日志内部实现和 Runtime 实现，但保留产生现有 ScienceFlow Workspace 文件格式的 Compatibility Sink/Adapter。
- 删除 `sys.path` 注入和纯兼容 facade。
- 保留旧工作区和旧 JSONL 的读取兼容。

## 11. CI 与发布门禁

### DeepCraft CI

- Unit Test。
- Public Contract Test。
- JSONL schema 与 replay test。
- 最小 Agent integration test。
- OpenAI Adapter mock integration test。
- Import time、Tool dispatch 和 EventSink benchmark。
- CLI 命令、退出码、Extension Contract 和冷启动 benchmark。
- 检查 `deepcraft` 不得 import `scienceflow`。

### ScienceFlow CI

- ScienceFlow Unit Test。
- DeepCraft Adapter Contract Test。
- DeepCraft CLI Extension 和 ScienceFlow 命令兼容测试。
- LNR 单 Worker集成测试。
- 多 Worker、Merge、ESTRA 和 Resume 集成测试。
- Resource Runtime 测试。
- Monitor/Trace JSONL 读取测试。
- 至少一个轻量端到端任务。
- DeepCraft 最低、锁定和最新兼容版本矩阵。

### Release 阻断条件

出现以下任一情况不得发布：

- DeepCraft Contract Test 失败。
- ScienceFlow 使用了 DeepCraft 私有 API。
- 事件 schema 无版本升级却发生破坏性变化。
- Workspace 路径、文件名、写入模式或 Contract Manifest 不一致。
- Log、Memory、JSON/JSONL、CSV、Snapshot 或配置 Golden 不一致。
- 旧工作区无法 Resume。
- LLM、Tool、Evaluator 或资源审查调用次数、时机或 Prompt 非预期变化。
- Tool Schema 或 Hook 顺序变化。
- ScienceFlow 现有 CLI 参数、默认值或退出码发生非预期变化。
- 关键性能指标超过回归门槛。
- Stage、ESTRA、资源决策、Final Artifact、任务成功率或任务指标出现回归。

## 12. 暂不纳入本轮的重构

为控制风险，以下工作与底座抽取分开进行：

- 拆分巨型 `LnrSolver`。
- 重写 Resource Observer 或资源决策算法。
- 调整 Stage/Gate/ESTRA 语义。
- 修改科研 Prompt。
- 修改工作区布局和 Snapshot 格式。
- 修改 Evaluator 或任务包协议。
- 删除 ScienceFlow 高级能力。

这些工作只能在 DeepCraft Runtime 切换稳定后，作为 ScienceFlow 自身的独立演进任务处理。

## 13. 完成定义

当以下条件全部满足时，DeepCraft 底座化工作完成：

1. DeepCraft 可独立安装和运行最小 Tool-using Agent。
2. DeepCraft 不包含任何 ScienceFlow 领域概念或反向依赖。
3. ScienceFlow 只依赖 DeepCraft 公开 API 和已发布版本。
4. 两个项目拥有独立测试、CI、版本和发布流程。
5. 通用交互数据由稳定 JSONL 事件协议承载，可实时消费和离线回放。
6. DeepCraft 提供可独立使用、可被 ScienceFlow 组合扩展的基础 CLI。
7. ScienceFlow 的 Stage、Gate、ESTRA、Snapshot、Resume、Resource Runtime 和 Multi-worker 能力全部保留。
8. 功能、具体任务效果、Workspace 文件、日志、Memory、JSON/JSONL、配置和性能门禁全部通过。
9. 旧 Runtime、重复日志实现和路径注入已安全移除。
