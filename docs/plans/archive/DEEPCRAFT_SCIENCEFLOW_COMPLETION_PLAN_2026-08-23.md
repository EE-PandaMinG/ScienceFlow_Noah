# DeepCraft / ScienceFlow 收口迁移执行规划（2026-08-23）

## 1. 文档定位

本文是 `DEEPCRAFT_SCIENCEFLOW_EVOLUTION_PLAN.md` 的后半程执行计划，以 2026-08-23 的
实际代码和 Git 检查点为起点。旧文档继续保存总体架构原则、功能矩阵和发布门禁；本文只回答：

1. 当前已经迁移到哪里；
2. 剩余代码按什么原子边界迁移；
3. 每个阶段如何证明 ScienceFlow 没有功能、效果、上下文或 Workspace 回归；
4. 何时可以切换默认 Runtime、拆仓和删除 `legacy_packages`。

本文不得被解释为允许修改 ScienceFlow 的科研策略。Prompt、Stage、Gate、Evaluator、ESTRA、
Resource Runtime、Multi-worker、Merge 和任务协议不属于本轮重写范围。

## 2. 不可协商的目标

### 2.1 架构目标

- DeepCraft 是领域无关、可独立安装、可独立测试和发布的轻量 Agent Runtime。
- ScienceFlow 仅通过 DeepCraft 公开 API 组合基础 Agent 能力。
- DeepCraft 不引用 ScienceFlow；ScienceFlow 不引用 DeepCraft 私有实现。
- MCP 保留为 DeepCraft optional extra，不进入最小安装。
- DeepCraft 和 ScienceFlow 最终拥有独立仓库、版本、CI 和发布节奏。

### 2.2 ScienceFlow 等效性硬条件

迁移前后必须保持：

- Prompt 文本、消息顺序、Tool 名称、Tool Schema、Tool Choice 和 LLM 参数；
- LLM、Tool、Evaluator 和资源审查的调用次数、时机、重试和超时；
- Tool feedback 的 `output/error/system`、压缩、artifact 和可见上下文语义；
- Stage/Gate/ESTRA/Resource/Merge 的触发与决策语义；
- Workspace 目录、文件名、日志、Memory JSON/JSONL、配置、Snapshot、软链接和最终产物；
- 旧 Workspace 的 Resume 能力和相同输入下的确定性 replay 结果；
- 真实科学任务的成功率、最终指标、稳定性和性能。

任何一项不一致都视为阶段失败。不得用“内部实现更合理”作为改变现有外部合同的理由。

### 2.3 ScienceFlow 运行上下文冻结要求

本轮迁移保护的不只是最终答案和 Workspace 文件，还包括 Agent 每一轮实际看到和执行的完整
运行上下文。对相同初始 Workspace、配置、录制 LLM 响应和随机种子，迁移前后必须验证：

- 原始 Memory 全量消息、LLM 可见投影消息、system message 分层及 provider 最终 payload；
- 动态注入的 round budget、guard coaching、resource feedback、Stage/ESTRA context 和恢复提示；
- Tool 列表、顺序、完整 Schema、Tool Choice、并行开关和每次 ToolCall arguments；
- ToolResult 进入 Memory 前后的压缩、裁剪、path rewrite、raw artifact 和错误渲染；
- 每次 LLM 调用的模型、temperature、seed、token limit、penalty、timeout 和 retry 参数；
- interaction log、tool artifact、short-term Memory 和 long-term JSONL 的写入内容与顺序。

必须同时保存两个比较视图：

1. **语义前视图**：ScienceFlow 构造但尚未交给 provider adapter 的 Message/Tool/配置；
2. **provider 视图**：system coalescing、字段转换完成后的真实请求 payload。

只验证最终模型回答不算上下文对齐。除已登记的时间戳、PID、临时绝对根路径和外部服务生成
请求 ID 外，不允许模糊比较；新增可忽略字段必须在阶段记录中说明生产者、原因和风险。

### 2.4 ScienceFlow 运行机制冻结要求

对相同录制输入，迁移前后必须生成可比较的 mechanism trace，至少覆盖：

- Agent state 转换、轮次编号、最大步数变化、自动继续和 Stop Reason；
- Hook/Middleware 调用顺序、次数、输入摘要和返回决定；
- ToolCall 顺序、readonly/mutation/Bash 分组、并发 slot 和回调顺序；
- stream chunk channel、interrupt、retry、failover、timeout 和 client close；
- write/read/edit guard、no-progress guard、embedded full-run 和 result.md 更新；
- Stage capture、Gate、Evaluator、ESTRA、snapshot、restore 和 final selection；
- Resource admission、GPU lease、worker 隔离、停止、归档和 Merge；
- crash/restart、人工停止、Resume 和旧 Workspace 继续运行。

机制门禁比较的是“何时、以什么顺序、调用了什么”，不能只比较最终文件恰好相同。任何 Hook
重排、调用合并、提前返回或默认值变化，即使当前样例最终结果相同，也必须先判定为不一致。

### 2.5 不合理设计的记录与隔离原则

迁移中发现的不合理耦合、重复实现、命名问题、性能隐患或历史缺陷，统一记录到
[迁移观察台账](../../history/runtime_migration/DEEPCRAFT_SCIENCEFLOW_MIGRATION_OBSERVATIONS.md)，不得在归属迁移提交中
顺手修正。

- 观察记录必须包含证据、当前可观察行为、风险、建议方向和处理阶段。
- 当前行为只要不是安全或数据损坏问题，仍作为迁移兼容基线保留。
- 改善设计必须使用单独议题、单独 Git 提交和单独前后效果验证。
- 若发现安全、数据丢失或不可恢复问题，暂停当前迁移，先记录并由独立修复阶段处理；修复后
  明确更新 baseline，不能静默改变 Golden。
- “已记录”不等于“接受为永久设计”，也不等于允许跳过当前等效性门禁。

## 3. 当前基线（Git `e7febf9`）

### 3.1 已完成

- DeepCraft 正式 Runtime、LLM/Tool/Memory/Event 基础契约和基础 CLI 已建立。
- DeepCraft CLI 支持 `run`、多轮 `repl`、`tools` 和事件/session JSONL。
- 通用 JSONL store、record/replay、Resume store 和 Workspace prefix rewrite 已建立。
- endpoint pool、provider error、retry、PooledLLM failover 和 legacy LLM factory 已归入 DeepCraft。
- subprocess 生命周期、stream repetition guard、telemetry、Tool bundle dispatch 和 shell reducer
  已归入 DeepCraft。
- workspace read/write/edit/grep/glob/ls 基础实现已归入 `deepcraft.tools.workspace`。
- `BaseAgent` 与 `AgentState` 已由 DeepCraft 自身维护。
- compatibility `BaseTool`、`ToolChoice`、`ToolResult`、`ToolCollection` 已由 DeepCraft 自身维护。
- ScienceFlow Tool schema 固定为 5391 bytes，SHA256
  `cc0aa04ca49d9f72f2b3ceb87073758650a65427136698568e2421ebdc93635b`。
- DeepCraft 测试已物理分到 `unit/contract/integration/legacy`，根测试保留 ScienceFlow 和跨层门禁。
- Browser、向量检索、LiteLLM 等未使用集成已从受支持 Runtime 清除；MCP 作为 optional extra 保留。
- Worker=1/2、Circle Packing 三 seed、Resume 和多轮阶段记录已保存，可作为最终门禁 baseline。

### 3.2 尚存的 legacy 边界

以下对象仍由 `deepcraft_core` 提供或与其身份绑定：

- `Message`、`Role`、`Function`、`ToolCall`；
- `Memory`、`MemoryRecord`、`BaseChatHistoryMemory`、`BaseContextCreator`、JSON KV storage；
- `OnlineLLM`、`BaseLLM`、`StreamHandle`、`GuardStreamChunk`、`CallStats`；
- MCPReAct 使用的 `deepcraft-agent[mcp]` compatibility。

ScienceFlow 主 `ScienceAgent` 仍运行 ScienceFlow 自有 RunLoop。当前没有 `legacy/deepcraft` 双
backend 开关，也不能删除：

- `deepcraft/legacy_packages/core`；
- `deepcraft/legacy_packages/agent`；
- `deepcraft.legacy` facade；
- `scienceflow/__init__.py` 的 repo-local `sys.path` 注入；
- 根项目和 DeepCraft `pyproject.toml` 中的 path source。

### 3.3 已知原子边界

`Message.tool_calls` 的 Pydantic 字段绑定历史 `ToolCall` 类。已验证：只迁移 `ToolCall` 而保留
旧 Message 会触发同结构异类型校验失败。因此：

```text
Message + Role + Function + ToolCall
```

必须作为同一原子类型组迁移。Memory 的持久化模型又引用 Message，因此 Message 类型组通过后，
才能切换 Memory identity。不得再次尝试单类型强换。

## 4. 总体执行顺序

| 阶段 | 内容 | 当前状态 | 长时真实实验 |
|---|---|---|---|
| C0 | 当前基线与 Tool/BaseAgent 收口 | 已完成 | 已完成短 vLLM smoke |
| C1 | Golden 冻结与 Runtime Parity Benchmark | 已完成 | 不需要 |
| C2 | Message/Role/Function/ToolCall 原子迁移 | 已完成 | 短 vLLM tool-turn 已通过 |
| C3 | Memory/Record/Storage 原子迁移 | 已完成 | 旧 Workspace 短 Resume 已通过 |
| C4 | OnlineLLM/StreamHandle 正式 Adapter 切换 | 已完成 | streaming/tool-call smoke 已通过 |
| C5 | ScienceAgent 双 Runtime backend 与完整 replay | 已完成 | 已完成确定性 replay、短 vLLM 和 Circle Packing Resume |
| C6 | Event/JSONL compatibility sink 收口 | 已完成 | 不单独跑长任务 |
| C7 | 默认 Runtime 切换与发布硬门禁 | 已完成 | 3 seed、worker=2、代表任务、CLI 已通过 |
| C8 | 独立发布、MCP adapter 和 legacy 清理 | 已完成（私有 Git `v0.1.2`、commit lock、仓内副本删除、最终矩阵通过） | 发布候选 smoke 已通过 |

依赖关系为严格串行的 `C1 -> C2 -> C3 -> C4 -> C5 -> C6 -> C7 -> C8`。阶段内部可以并行跑
互不写同一 Workspace 的测试，但不能跳过前置合同。

## 5. C1：Golden 冻结与 Runtime Parity Benchmark

### 5.1 目标

在替换对象身份前，先把当前真实序列化、上下文投影和恢复行为固定为可逐字节比较的 fixture。

### 5.2 交付物

- DeepCraft provider golden：
  - user/system/assistant/tool Message 的 `model_dump()`；
  - reasoning content、空 content、单/多 ToolCall；
  - Function arguments 的字符串、Unicode、转义和字段顺序；
  - ToolCall ID、type 和 Message role 值。
- Memory golden：
  - `short_term.json`；
  - `long_term.jsonl`；
  - bounded window、坏行跳过、UUID 去重、prefix repair；
  - clone inherit、recent-round prune、Workspace path rewrite。
- ScienceFlow consumer golden：
  - `build_messages_for_llm()` 的完整 provider payload；
  - provider adapter 之前的语义前 Message/Tool/配置快照；
  - tool turn sanitization；
  - write/edit 压缩与 raw artifact；
  - `.logs/interaction.log`、`.logs/tool_outputs/index.txt`。
- mechanism trace golden：
  - state/round/hook/tool/retry/stop 的有序事件；
  - Stage/Gate/ESTRA/Resource/Resume 的触发和决定；
  - 调用次数和未调用原因。
- 一份只读旧 Workspace fixture，记录文件清单、普通文件 SHA256、软链接文本和解析目标。

### 5.3 门禁

- Fixture 必须来自当前 Git 检查点，不得手工改写成目标格式。
- 同一 fixture 连续 replay 两次结果一致。
- Golden 覆盖空值、Unicode、坏行、截断窗口和未闭合 Tool turn。
- 同一录制输入的语义前上下文、provider payload 和 mechanism trace 均可严格比较。
- 所有归一化字段集中声明，不允许测试用例自行忽略未知差异。
- 本阶段不改生产类型，不运行长时真实任务。

### 5.4 Runtime Parity Benchmark 目录设计

C1 实现一套可被后续所有迁移阶段复用的确定性 Benchmark，计划目录如下：

```text
tests/contract/runtime_parity/
├── README.md
├── manifest.yaml                 # schema、baseline commit、case 与比较器版本
├── normalization.yaml            # 唯一允许归一化的字段及原因
├── fixtures/
│   ├── baseline_v1/              # 历史基线，不覆盖
│   └── baseline_v2/              # full 机制覆盖收口基线
│       ├── recorded_llm.jsonl
│       ├── initial_workspace/
│       ├── context/
│       ├── mechanism/
│       └── workspace_manifest.json
├── cases/
│   ├── message_tool_turn.yaml
│   ├── memory_window_repair.yaml
│   ├── tool_dispatch.yaml
│   ├── retry_stop.yaml
│   ├── resume.yaml
│   └── stage_resource.yaml
├── comparators/
│   ├── context.py
│   ├── mechanism.py
│   ├── workspace.py
│   └── performance.py
├── capture.py
├── runner.py
└── test_runtime_parity.py

scripts/run_runtime_parity.py      # 本地/CI 统一入口，仅编排上述公开测试组件
```

版本化 fixture 只保存最小且可审阅的数据；运行产生的候选 Workspace 放到独立临时根目录，不写回
fixture。旧 Workspace 中的敏感配置和凭据必须脱敏，但脱敏过程不得改变被比较字段的结构。

### 5.5 四类 Benchmark

#### A. Context Benchmark

每次 LLM 调用产生一条 context capture，至少包含：

- call index、agent state、round、stage/worker ID；
- 原始 Memory message dump；
- ScienceFlow LLM-visible projection；
- system message layers 和 provider payload；
- Tool schema、Tool Choice、parallel flag；
- model/generation/retry/timeout 参数；
- 动态注入来源与文本 SHA256。

通过标准：登记归一化后 `context_diff_count == 0`。

#### B. Mechanism Trace Benchmark

机制事件使用单调 sequence，记录 state、round、hook、LLM、Tool、guard、Stage、Gate、ESTRA、
Resource、Resume 和 stop。事件必须包含名称、phase、关键输入摘要、决定和父事件 ID。

通过标准：事件数量、名称、顺序、父子关系、关键参数和决定全部一致，即
`mechanism_diff_count == 0`。

#### C. Workspace Contract Benchmark

比较路径集合、文件类型、普通文件 SHA256、JSON/JSONL 规范化内容、软链接文本与解析目标、
Memory、日志、tool artifact、snapshot、Stage、Merge 和 final artifact。

通过标准：`missing == 0`、`additional == 0`、`unregistered_mismatch == 0`。允许差异必须在
manifest 中逐路径登记，不能在 comparator 内硬编码忽略。

#### D. Performance Benchmark

独立测量 context build、Memory append/retrieve、Tool dispatch、event write、Resume、CLI 冷启动、
Runtime 请求前开销和峰值内存。性能样本使用 warmup、重复轮次、中位数和 P95。

通过标准：满足原规划阈值；Runtime 调度新增中位不超过 1 ms、P95 不超过 2 ms，其余同机回归
默认不超过 2%。性能 Case 不与功能 Case 并行执行，避免 CPU、磁盘和进程调度干扰结果。

### 5.6 Benchmark Case 最小集合

`quick` suite 必须覆盖：

1. 单轮纯文本响应；
2. `write -> read -> final` Tool turn；
3. 多 ToolCall 的 readonly 并行与 mutation 顺序执行；
4. Tool error、LLM retry、stream interrupt 和 stop；
5. Memory window、坏行、未闭合 Tool turn 和 prefix repair；
6. 旧 Workspace Resume；
7. 一次 Stage/Gate/Resource 决策链的录制 replay。

`full` suite 在 quick 基础上增加 worker=2、ESTRA、snapshot restore、Merge、人工停止/继续和失败
恢复，但仍优先使用 recorded LLM，不连接真实模型。

### 5.7 Baseline 生成与不可变规则

- baseline 必须记录 Git commit、Python/依赖锁摘要、fixture schema 和 comparator version。
- baseline 只能通过显式 `--record-baseline` 生成，普通测试禁止自动更新 Golden。
- 录制前要求工作树干净，并检查目标 commit 与 manifest 一致。
- 更新 baseline 必须单独 Git 提交，附差异报告和更新原因。
- 迁移实现提交不得同时更新 baseline；否则无法判断是兼容还是重写了预期结果。
- 历史 baseline 永不覆盖；schema 变化新建 `baseline_vN`。

### 5.8 统一归一化规则

`normalization.yaml` 是唯一允许忽略易变字段的来源。每条规则必须包含：

- JSON path 或 Workspace path；
- 生产者；
- 易变原因；
- 替换策略；
- 风险说明；
- 首次批准阶段。

初始只允许时间戳、PID、临时 Workspace 根路径和外部 provider request ID。ToolCall ID、消息顺序、
Prompt、Tool arguments、Stage ID、Stop Reason 和文件相对路径默认不允许归一化。

### 5.9 并行快速验证

功能 Benchmark 按 Case 进程级并行，每个 Case 使用独立 Workspace、Memory 目录、日志目录和端口。
禁止多个 worker 共享可写 fixture 或候选 Workspace。

统一命令计划为：

```bash
# 日常工程迁移：并行 quick suite
python scripts/run_runtime_parity.py --suite quick --jobs 4

# 阶段收口：并行完整功能 suite
python scripts/run_runtime_parity.py --suite full --jobs 4

# 性能门禁：串行，避免并行噪声
python scripts/run_runtime_parity.py --suite performance --jobs 1
```

Runner 使用固定 case ID 分片，子进程环境固定 `PYTHONHASHSEED`、timezone、locale 和任务 seed；
聚合报告按 case ID 排序，因此并行完成顺序不影响报告内容。默认收集全部失败后统一返回非零退出码，
避免 fail-fast 隐藏后续差异。

并行只用于缩短墙钟时间，不改变每个 Case 的 strict comparator。涉及共享 GPU、真实 vLLM、性能或
同一历史 Workspace 原地 Resume 的 Case 必须串行或使用物理副本。

### 5.10 报告与通过条件

每次运行输出机器可读 `runtime_parity_report.json` 和简短终端摘要。报告至少包含：

```json
{
  "schema_version": 1,
  "baseline_commit": "...",
  "candidate_commit": "...",
  "suite": "quick",
  "jobs": 4,
  "cases": [],
  "totals": {
    "context_diff_count": 0,
    "mechanism_diff_count": 0,
    "workspace_unregistered_diff_count": 0,
    "failed_cases": 0
  },
  "verdict": "pass"
}
```

功能套件只有以下条件同时满足才通过：

```text
context_diff_count == 0
mechanism_diff_count == 0
workspace_unregistered_diff_count == 0
failed_cases == 0
```

性能 verdict 独立呈现，不能用功能一致覆盖性能回归，也不能因性能噪声放宽上下文或机制比较。

## 6. C2：Message 类型组原子迁移

### 6.1 目标

在 DeepCraft 内部实现权威 `Message/Role/Function/ToolCall`，保持历史 Pydantic 与 provider
payload 合同，并一次性切换所有 ScienceFlow 消费方。

### 6.2 实现步骤

1. 在 DeepCraft 正式或明确的 compatibility namespace 实现四个类型。
2. 保持字段名称、顺序、默认值、构造 helper、`model_dump()` 和 copy 行为。
3. 为旧 `deepcraft_core.Message/ToolCall` 提供结构化无损 coercion。
4. 一次切换 BaseAgent、Memory projection、agent runtime 和 solver 消费方。
5. 旧对象只作为输入兼容，不再作为 ScienceFlow 新消息的生产类型。

### 6.3 门禁

- C1 Message/ToolCall Golden 逐字节一致。
- Tool schema SHA256 与 Tool Choice 不变。
- 同一 tool-turn 的 role、ToolCall ID、arguments 和消息数量一致。
- short-term/long-term 文件在本阶段仍由旧 Memory 写入，但内容必须一致。
- vLLM 短任务执行 `write -> read -> final`，Memory role 顺序保持
  `user, assistant, tool, assistant, tool, assistant`。

### 6.4 回滚条件

出现 Pydantic 类型校验、字段顺序、provider payload、tool-call parsing 或 interaction log 差异，
立即回到 C1 fixture 修正适配器，不继续进入 Memory 迁移。

## 7. C3：Memory / Record / Storage 原子迁移

### 7.1 目标

将通用 Memory 容器、Record、历史存储和 ContextCreator 的权威实现归入 DeepCraft；
ScienceFlow 只保留压缩、继承、Stage Memory、L0 anchor 和 LNR-specific policy。

### 7.2 实现边界

DeepCraft 负责：

- Message append/retrieve 和 bounded history；
- MemoryRecord 与 UUID/extra_info；
- JSON KV storage、JSONL append/read、坏行容忍；
- 基础 context window 和通用 Resume；
- 可注入的 persistence adapter。

ScienceFlow 保留：

- tool memory compression；
- clone inheritance 和 protected prefix 策略；
- Stage/ESTRA/Resource feedback memory；
- result.md、snapshot 和 LNR context assembly；
- 现有 Workspace 文件名与目录选择。

### 7.3 门禁

- C1 Memory Golden 逐字节一致，包括结尾换行和 JSON compact 格式。
- 新代码原地读取 C1 旧 Workspace，并继续追加消息。
- legacy 代码能够读取未发生 schema 升级的新 Workspace。
- exact-start Resume 的消息顺序、Stage、最终产物和 Workspace manifest 一致。
- Memory 热路径、Resume 时间和峰值内存同机不得回归超过 2%。
- 只跑一次短 Resume vLLM smoke；不重复三 seed。

## 8. C4：LLM / Streaming 正式 Adapter 切换

### 8.1 目标

ScienceFlow 默认 LLM 构造不再实例化 legacy `OnlineLLM`，改用 DeepCraft 正式
OpenAI-compatible adapter，同时保持现有模型调用行为。

### 8.2 必须对齐

- system message coalescing；
- text、reasoning 和 ToolCall streaming；
- StreamHandle queue、finish、interrupt 和异常传播；
- request seed、temperature、max tokens、frequency penalty；
- parallel tool calls 和 tool choice；
- timeout、同轮 retry、rate-limit/connection cooldown、failover；
- tokens、cached tokens、TTFT、TPOT 和 endpoint telemetry；
- client close 生命周期和代理参数。

### 8.3 门禁

- 录制请求逐字段一致，敏感值只比较存在性或哈希。
- 同一 recorded stream 的 chunk channel、顺序和最终 Message 一致。
- retry/failover 的 endpoint 顺序和调用次数一致。
- ToolCall 空参数、JSON 转义和 reasoning-only chunk 用例一致。
- 短 vLLM smoke 覆盖 text、单 ToolCall、stream interrupt 和 client close。
- 请求前开销、TTFT 和 streaming replay 性能同机不得回归超过 2%。

## 9. C5：ScienceAgent 双 Runtime backend

### 9.1 目标

让 ScienceFlow 可以在不改变外部 CLI 和配置的情况下选择：

```text
legacy    -> 当前 ScienceAgent RunLoop
deepcraft -> DeepCraft AgentRuntime + ScienceFlow hooks/policies
```

切换开关只用于迁移和回滚，不进入模型上下文，不改变 Workspace 路径。

### 9.2 DeepCraft 负责的机制

- 生命周期、轮次推进、取消、停止原因；
- LLM 调用与 ToolCall 调度；
- 顺序/安全并发 Tool 执行；
- 通用 retry、stream guard、事件发射；
- Hook/Middleware 的确定顺序。

### 9.3 ScienceFlow 保留的策略

- Prompt、stable prompt、round budget 和自动继续策略；
- write/read/edit guard、科学任务 coaching；
- embedded full-run、result.md、Stage/Gate/Evaluator；
- LNR、ESTRA、Resource Runtime、GPU lease/admission；
- Workspace snapshot、clone、merge 和 artifact selection。

### 9.4 完整 backend replay

同一份 LLM recording 分别运行两个 backend，逐轮比较：

- provider adapter 前的 Message、Tool schema、Tool Choice 和生成参数；
- provider request 和返回 Message；
- ToolCall 名称、参数、并发分组、回调顺序和结果；
- Memory 全量消息与压缩边界；
- runtime event、interaction log 和 tool artifact；
- Stage、Gate、Evaluator、Stop Reason；
- Workspace manifest、软链接、snapshot 和 final artifact。

此外必须比较 mechanism trace，确认 state、round、hook、retry、guard、Stage、Resource 和 Resume
事件的顺序及次数一致。最终产物一致但 mechanism trace 不一致时，backend replay 仍判定失败。

除时间戳、PID、临时绝对根路径等登记字段外必须严格一致。

### 9.5 门禁

- mock/recorded backend replay 全部通过后，才跑一个短真实任务 seed。
- 单 worker、worker=2、Resume、ESTRA、Resource 和 failure recovery 均有 deterministic case。
- Runtime 调度开销中位新增不超过 1 ms、P95 不超过 2 ms。
- legacy backend 始终保持可回切，直到 C7 发布周期结束。

## 10. C6：Event / JSONL 与现有日志收口

### 10.1 目标

DeepCraft Event 成为通用运行事件来源，但 ScienceFlow compatibility sink 继续逐字生成所有历史
Workspace 日志。Monitor/Trace 可消费新事件，同时保持旧 Workspace 可读。

### 10.2 实现要求

- 单调 `sequence`、schema version、session/run/agent ID；
- Tool、异常、Session 结束边界 flush；
- 高频 stream chunk 可聚合，但不得改变 interaction log 的可见写入时机；
- compatibility sink 保留旧文件名、字段、颜色、截断和分片布局；
- Monitor/Trace 对旧格式只读兼容长期保留。

### 10.3 门禁

- 同一 replay 的 event 语义、顺序和旧日志输出一致。
- JSONL append 在 crash/partial line 后可恢复。
- 写入不得阻塞 LLM 或 Bash stream。
- Workspace 新增内部文件不得被 Agent、Snapshot、Merge 或 artifact 扫描误收集。

## 11. C7：默认 Runtime 切换与最终效果门禁

### 11.1 切换前条件

C1–C6 全部通过，且没有未登记的 Golden、Workspace、调用次数或性能差异。

### 11.2 最终验证矩阵

- Circle Packing：复用历史 baseline，candidate 跑 3 seed；
- worker=2：验证隔离、资源分配、Stage、Merge 和 final；
- exact-start Resume：从历史 Workspace 继续；
- 至少一个非 Circle Packing 优化任务；
- 一个 ML/数据任务；
- scientific-design extra 可用时跑一个代表任务；
- ESTRA、Resource Runtime、失败恢复和人工停止/继续；
- DeepCraft CLI run/repl 与 ScienceFlow CLI 参数、默认值和退出码。

### 11.3 判定标准

- 具体任务成功率和最终指标不低于 baseline；
- 每轮语义前上下文和 provider payload 无未登记变化；
- 调用次数、Prompt token、Hook 顺序、Stop Reason 和阶段决策无非预期变化；
- Workspace manifest 无未登记 mismatch；
- 性能指标满足原规划 2% 上限，目标仍为零退化；
- 旧 Workspace Resume 和回滚到 legacy backend 均成功。

全部通过后，将 DeepCraft backend 设为默认；legacy backend 至少保留一个发布周期。

## 12. C8：独立发布与 legacy 清理

### 12.1 MCP 收口

- 将仍需保留的 MCP client/ReAct adapter 迁入 `deepcraft[mcp]`。
- MCP extra 不依赖 `deepcraft-agent` 历史 distribution。
- 最小 `deepcraft` 安装不导入 MCP、OpenAI、ML/CUDA 或 ScienceFlow。

### 12.2 独立发布

- DeepCraft 独立仓库、SemVer、CI、wheel 和 release notes；
- ScienceFlow 依赖已发布 DeepCraft Git tag，lock 固定解析 commit，不依赖路径或未发布提交；
- ScienceFlow CI 验证锁定 tag；升级通过显式 tag/lock PR 完成；
- 建立跨仓 nightly compatibility CI。

### 12.3 删除顺序

只有 C7 通过并经过回退周期后，按以下顺序删除：

1. `scienceflow/__init__.py` 的 `sys.path` 注入；
2. root/DeepCraft pyproject 的 legacy path source；
3. `deepcraft-agent` 历史包；
4. 已无消费者的 `deepcraft-core` 模块；
5. `deepcraft.legacy` 和 `deepcraft.compat` 纯 re-export facade；
6. 重复旧 Runtime 和日志内部实现。

旧 Workspace、旧 JSON/JSONL 和旧配置的读取 adapter 不随内部源码一起删除。

## 13. 测试与时间控制

### 13.1 日常迁移切片

每个纯工程切片只运行：

- DeepCraft provider unit/contract；
- ScienceFlow 受影响 consumer contract；
- C1 deterministic fixture/replay；
- 受影响路径的上下文快照和 mechanism trace 对比；
- Ruff、compileall、dependency boundary 和 `git diff --check`。

目标耗时 1–3 分钟。不为每个内部搬运重复 Circle Packing 或完整三 seed。

默认优先运行 `runtime_parity quick --jobs 4` 和受影响的 provider/consumer tests。并行度可以根据
CI CPU 配额降低，但每个 Case 的输入、比较器和通过标准不得改变。完整离线 pytest 与性能 suite
分别运行，避免并行 Benchmark 抢占资源造成伪回归。

### 13.2 阶段检查点

- 每个 C 阶段结束运行一次完整离线矩阵；
- 行为边界阶段运行一次短 vLLM/CLI smoke；
- 只有 C5 首次 backend 集成和 C7 默认切换运行真实代表任务；
- 只有 C7 运行最终 3 seed、worker=2 和性能矩阵。

### 13.3 失败处理

- 定向门禁失败时不得用放宽断言掩盖差异；
- 先判断是 fixture 不完整、adapter 丢字段还是策略被错误下沉；
- 上下文或 mechanism trace 出现差异时，即使最终产物一致也不得继续；
- 未通过当前阶段不得删除旧实现或进入下一类型组；
- 每个阶段保持独立 Git 检查点，可单提交回退；
- 发现 Prompt、Tool Schema、调用时机或科研策略变化时立即停止迁移并恢复安全边界。

## 14. 测试所有权

### DeepCraft

- Message/Tool/Memory/LLM/Event/Runtime 的 provider contract；
- minimal agent、CLI、JSONL replay、cancel/timeout 和性能 microbenchmark；
- 不得 import `scienceflow`。

### ScienceFlow

- Prompt、tool feedback、Memory policy、Stage/Gate/ESTRA/Resource/Merge；
- Workspace contract、旧 Workspace Resume 和真实任务效果；
- 只使用 DeepCraft 公开 API。

### 跨层 contract

- provider payload、Tool schema、hook order、事件 schema；
- backend replay、Workspace manifest、CLI extension；
- 同时保留 DeepCraft 提供方测试和 ScienceFlow 消费方测试。

## 15. 文档与提交规范

每个阶段必须：

1. 在 `docs/history/runtime_migration/` 或 `docs/baselines/` 记录实现边界、验证结果、已知差异和下一边界；
2. 将发现的不合理设计写入迁移观察台账，并注明本阶段是否保持原行为；
3. 更新本文状态表，不回写或篡改历史 baseline；
4. 明确记录真实任务是否运行以及为什么；
5. 独立 Git 提交，提交信息使用 `refactor/test/docs` 前缀；
6. 提交后工作树保持干净。

文档中的测试数量是阶段证据，不作为未来固定数量；固定合同应使用 fixture、schema hash 和
明确断言表达。

## 16. 完成定义

以下全部满足才算本规划完成：

- DeepCraft 可独立安装、运行 Tool-using Agent、持久化 session 并 replay；
- ScienceFlow 默认使用 DeepCraft Runtime 且可以在回退周期内切回 legacy；
- ScienceFlow 全部科研能力、具体任务效果和 Workspace 外部合同保持；
- ScienceFlow 每轮运行上下文和 mechanism trace 无未登记变化；
- MCP 作为独立 optional extra 可用且不依赖历史 agent distribution；
- 两个项目具有独立仓库、测试、CI、版本和发布流水线；
- ScienceFlow 使用已发布 DeepCraft Git tag，不再进行路径注入或仓内 editable source；
- `legacy_packages`、重复 Runtime 和纯兼容 facade 已安全删除；
- 旧 Workspace 和旧 JSON/JSONL 仍可读取和 Resume；
- 最终三 seed、worker=2、代表任务、性能和发布门禁全部通过。

在这些条件满足前，不得宣称“全部规划完成”。
