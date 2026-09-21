# DeepCraft / ScienceFlow 迁移观察台账

## 1. 用途

本文件记录底座迁移期间发现但不应在纯工程迁移中顺手修改的架构债务、历史行为和潜在问题。
记录的目的，是将“保持当前行为完成无损迁移”和“后续改善设计”分开，避免两类变化互相掩盖。

状态定义：

- `observed`：已有证据，尚未安排处理；
- `deferred`：确认存在，但明确推迟到指定阶段；
- `needs-decision`：需要单独设计或产品决策；
- `accepted`：确认保留为长期设计；
- `resolved`：已在独立提交完成并重新建立门禁。

每条记录至少包含：证据、当前行为、风险、迁移期决定和建议处理阶段。不得只写主观评价。

## 2. 当前观察

### OBS-001：Message 与 ToolCall 存在 Pydantic 类型身份耦合

- 状态：`resolved`
- 证据：`Message.tool_calls` 绑定历史 `deepcraft_core.ToolCall`；定向实验中，结构相同但类不同的
  ToolCall 会触发 Pydantic validation error。
- 当前行为：ScienceFlow 的 `Message/Function/ToolCall` 继续保持历史对象身份。
- 风险：类型不能独立迁移，兼容 facade 容易产生“字段相同即可替换”的错误判断。
- 迁移期决定：四个类型已在 C2 作为原子组迁入 `deepcraft.legacy`；`deepcraft_core` 兼容导出
  指向同一对象，旧 MemoryRecord 因而不会产生同结构异类型校验失败。
- 建议：显式 structural coercion 和 provider-payload contract 已建立；C3 迁移 Memory 后继续保留
  旧 Workspace 输入兼容测试。

### OBS-002：导入 ScienceFlow 会修改 `sys.path`

- 状态：`resolved`
- 证据：`scienceflow/__init__.py` 将 repo 内 `deepcraft/legacy_packages/core` 和 `agent` 插入
  `sys.path`。
- 当前行为：ScienceFlow 不再修改 `sys.path`；DeepCraft 由声明式 dependency/source 解析。
- 风险：包解析依赖导入顺序，独立安装和多仓环境容易出现隐式版本覆盖。
- 迁移期决定：C7/C8 已依次删除 agent/core path injection 和 historical distribution。
- 结果：独立 wheel 隔离安装、ScienceFlow consumer contract 与完整矩阵均通过；ScienceFlow
  已切换到私有 Git `v0.1.2` 并由 lock 固定 commit，仓内 editable source 已删除。

### OBS-003：正式、legacy 和 compat 三套 namespace 并存

- 状态：`resolved`
- 证据：当前同时存在 `deepcraft.*`、`deepcraft.legacy.*` 和 `deepcraft.compat.*`，部分 facade
  只做 re-export。
- 当前行为：零消费者的 `deepcraft.compat` 和 flat re-export 已删除；ScienceFlow 所需的冻结
  Message/Memory/Tool compatibility 实现仍在 `deepcraft.legacy`，新 CLI/runtime 使用正式 namespace。
- 风险：对象身份、公开 API 和弃用边界不直观，容易导入错误层级。
- 迁移期决定：C8 按消费者清单删除纯 re-export；有实际 import 消费者的
  `deepcraft.memory.legacy_records` 装配入口和旧 Workspace 数据读取实现继续保留。
- 结果：删除后 DeepCraft `139 passed`、跨层定向 `8 passed`、quick replay 差异为 0；隔离 wheel
  不再包含 `deepcraft/compat` 或 flat shim。

### OBS-004：ScienceAgent 通用循环机制与科学策略高度交织

- 状态：`needs-decision`
- 证据：ScienceAgent RunLoop 同时处理 LLM/Tool 调度以及 LNR、guard、result.md、资源反馈和
  Workspace 日志策略。
- 当前行为：所有 Hook 顺序和提前返回共同决定当前科学任务效果。
- 风险：机械抽取 RunLoop 可能改变调用时机，即使最终样例文件暂时一致也会造成长期行为漂移。
- 迁移期决定：C5 前不改主 RunLoop；C1 先冻结 mechanism trace。
- 建议：C5 通过小粒度 Hook/Middleware 显式表达顺序，不顺便重写科学策略。

### OBS-005：根项目运行依赖、测试依赖和重型 ML 栈混合

- 状态：`deferred`
- 证据：根 `pyproject.toml` 默认 dependencies 同时包含 ScienceFlow runtime、pytest 和完整 ML/CUDA
  相关包；DeepCraft 最小包已单独轻量化。
- 当前行为：项目默认环境覆盖现有任务和完整测试矩阵。
- 风险：ScienceFlow 独立安装体积大，runtime 与开发/任务依赖边界不清晰。
- 迁移期决定：不在 Runtime 身份迁移中调整，以免改变任务环境和性能基线。
- 建议：C8 独立发布时基于真实任务矩阵拆分 runtime、dev 和 task extras。

### OBS-006：MCP extra 仍依赖历史 `deepcraft-agent` distribution

- 状态：`resolved 2026-08-23`
- 证据：`deepcraft[mcp]` 当前声明 `deepcraft-agent[mcp]`。
- 当前行为：MCP 仍可作为非默认 extra 使用，最小 DeepCraft 不安装它。
- 风险：无法物理删除 `legacy_packages/agent`，MCP 与新 Runtime 的生命周期契约也未独立验证。
- 迁移期决定：继续保留 MCP 能力和 optional 边界。
- 建议：C8 将 MCP client/ReAct adapter 迁入正式 DeepCraft MCP extra 后删除历史 distribution。
- 处理结果：`deepcraft[mcp]` 现直接依赖 MCP SDK，正式 adapter 使用 DeepCraft Runtime Tool
  contract；`deepcraft-agent` 已从 lock graph 和源码树移除，历史未跟踪构建缓存已可恢复地转移到
  `/tmp/deepcraft_legacy_agent_removed_20260823`。

### OBS-007：主中文 README 的历史 extra 描述与当前 pyproject 可能不一致

- 状态：`observed`
- 证据：README 仍描述 `deepcraft-full` 以及 Browser/LiteLLM 等历史集合；当前根 pyproject 只保留
  `deepcraft-mcp` 和 `scientific-design` 等实际 extra，未声明 `deepcraft-full`。
- 当前行为：运行代码不受影响，但安装文档可能引导用户执行不存在的 extra。
- 风险：安装失败或对受支持能力范围产生误解。
- 迁移期决定：不与 Message/Memory/Runtime 迁移混合修改。
- 建议：使用独立 docs 提交核对中英文 README、pyproject 和 uv.lock 后修正。

### OBS-008：Runtime Event ID 当前由随机 UUID 生成

- 状态：`deferred`
- 证据：`deepcraft.events.RuntimeEvent.event_id` 默认使用 `uuid4()`；同一 deterministic replay 的
  事件类型、顺序和父子关系一致，但原始 ID 文本不同。
- 当前行为：事件 JSONL 每次运行产生新 ID，`parent_event_id` 引用该次运行中的对应 ID。
- 风险：直接逐字比较会产生伪差异；直接删除 ID 又会漏掉父子关系回归。
- 迁移期决定：C1 Benchmark 将 ID 按事件 sequence 稳定映射，同时严格比较每个 parent 引用；该规则
  已集中登记在 `normalization.yaml`。
- 建议：C6 评估是否由 Runtime 注入确定性 ID factory；在此之前保持生产格式不变。

### OBS-009：历史 JSON Storage 与恢复 helper 的坏行策略不一致

- 状态：`deferred`
- 证据：`JsonKeyValueStorage.load()` 对任意坏 JSON 行直接抛错；`read_legacy_records()` 则逐行跳过
  坏行。ScienceFlow Resume 会先走 repair helper，普通直接 Storage load 不具备同样容错。
- 当前行为：受控 Resume 可以恢复部分损坏文件；直接使用历史 Storage 的调用方可能失败。
- 风险：未来合并两条读取路径时，选择任一策略都会改变另一侧可观察行为。
- 迁移期决定：C3 原样保留两种合同，并分别测试；不在归属迁移中静默统一。
- 建议：C8 前单独设计显式 `strict/recover` 读取模式，并以独立 baseline 更新处理。

### OBS-010：历史 OpenAI adapter 仍是超大兼容实现

- 状态：`resolved`
- 证据：`deepcraft_core.llm.base` 与 `deepcraft_core.llm.online` 分别约 500/1500 行，后者同时包含
  text/tool streaming、write decoder、logits、embedding、usage 和 provider 兼容分支。
- 当前行为：C8 已把冻结实现拆入 `deepcraft.llm` 正式模块；ScienceFlow 继续使用同一
  `OnlineLLM` 入口、方法签名、请求字段和逐 chunk 合同。
- 风险：直接把大文件搬进正式源码会破坏 350 行规范门禁；立即拆函数又会扩大 C4 行为风险。
- 迁移期决定：C8 使用 C1 replay 将 decoder、request policy、text stream、tool stream、logits、
  usage 和公共重试入口分模块拆出；文件仍不超过 350 行、函数仍不超过 120 行，未放宽门禁。
- 结果：`legacy_packages/core`、`deepcraft_core` distribution 和中间
  `deepcraft.llm.legacy_compat` 已删除；quick replay 四类差异为 0，真实 vLLM text/tool/stream、
  DeepCraft `140 passed` 和根完整矩阵 `1675 passed, 3 skipped` 通过。

## 3. 新观察模板

### OBS-013：PyPI 名称冲突后采用私有 Git 发布

- 状态：`accepted`
- 证据：PyPI simple index 已存在第三方 `deepcraft==0.0.1`，描述为 language processing
  utilities；我们的 `deepcraft==0.1.0` 不存在。
- 当前行为：Python import package 和 CLI 仍为 `deepcraft`；发布 distribution 已改名为未占用的
  `deepcraft-runtime`；用户明确不需要 PyPI，正式发布采用私有 Git tag。
- 风险：若继续使用旧 distribution 名，trusted publishing 会因项目所有权失败；若连 import 名一起
  修改，则会造成 ScienceFlow 代码、上下文和用户命令的大范围非必要变化。
- 迁移期决定：只改安装元数据和依赖声明，保留全部 Python namespace、CLI、Prompt、Tool 和
  Workspace 合同；full runtime parity v2 复验为 0 diff。
- 处理结果：`v0.1.2` 指向 `5f2493374ccd3d318997926714eb0c8c2cbb0f78`；release workflow
  构建 wheel/sdist 并创建 GitHub Release，不含 PyPI 步骤。ScienceFlow 直接依赖该 tag，lock 固定
  同一 commit；仓内 DeepCraft 副本已删除。

### OBS-014：ScienceFlow 全量 Ruff 存在历史规范债务

- 状态：`deferred`
- 证据：分仓收口时执行 `ruff check scienceflow` 报告 32 项，主要是 `E402` 历史导入位置、未用
  import/局部变量和一个无占位符 f-string；涉及 `scienceflow/cli.py`、Resource Runtime、UI 和
  executor 等既有文件。
- 当前行为：这些问题在本切片前已存在；本次实际修改的 Python 文件、runtime parity 和 DeepCraft
  独立源码 Ruff 均通过。
- 风险：直接自动修复 import 顺序可能改变 CLI bootstrap 或 compatibility re-export 的导入副作用；
  与物理分仓混在同一提交也会扩大无损验证范围。
- 迁移期决定：不放宽规则、不加 blanket noqa，也不在分仓提交中顺手改生产模块。
- 建议：单独建立 ScienceFlow lint cleanup 任务，按模块切片修复并对每片运行 quick parity 与受影响
  consumer contract。

```markdown
### OBS-NNN：简短标题

- 状态：`observed|deferred|needs-decision|accepted|resolved`
- 证据：文件、测试、trace 或复现步骤。
- 当前行为：现有 ScienceFlow 可观察行为。
- 风险：对功能、上下文、机制、Workspace、性能或维护性的影响。
- 迁移期决定：保持、阻断、单独修复或接受。
- 建议：目标设计和建议处理阶段。
```

若观察升级为修复，必须链接独立阶段记录、Git 提交和更新后的验证证据；不得删除原始观察。
## OBS-011：ScienceAgent RunLoop 是 C5 的主要迁移风险

- 日期：2026-08-23
- 现象：生命周期、上下文压缩、LLM retry、Tool bundle、LNR、Stage/Resource 和恢复集中在一个
  超长异步循环中。
- 决策：先用 DeepCraft `HostedAgentRuntime` 建立可回滚 backend 边界，并原样托管现有策略循环；
  再以双 backend replay 为门禁，按稳定接缝逐段下沉。
- 禁止：复制第二份 RunLoop、让 backend 名称进入上下文、或仅凭最终文件一致判定迁移完成。
## OBS-012：Runtime JSONL 必须同时支持 async Runtime 和同步历史生产者

- 日期：2026-08-23
- 现象：DeepCraft AgentRuntime 是 async，而 ScienceFlow LHR state machine 的历史 append API 是
  同步调用；若各自维护 writer，会出现 sequence 恢复、partial line 和 flush 规则漂移。
- 决策：DeepCraft 同时提供共享语义的 async/sync sink；LHR 先构造 RuntimeEvent，再通过
  compatibility renderer 保持旧 JSONL 字节合同。
- 修复边界：只自动截断文件末尾未闭合的坏行；完整坏行不静默跳过。

## OBS-015：旧 Tool Runtime 目录已删除，但 SF policy adapter 仍偏大

- 日期：2026-08-23
- 状态：`deferred`
- 证据：`core/agent/tool_exec`、`core/agent/tools`、`core/tools` 和通用 `core/executor` 已物理删除；
  `core/tooling/execution/single.py` 仍约 994 行，`safety/tooling/bash.py` 仍约 2790 行。
- 当前行为：通用 Tool contracts、并发顺序、subprocess、guard pipeline、artifact store/reducer 和 code
  runner 已由 DeepCraft 提供；剩余大文件主要编排 ScienceFlow Memory、interaction log、Stage/LNR、
  Resource/GPU、UI 和历史反馈文本。
- 风险：继续在本次纯迁移中拆分这些强耦合 policy，容易改变 tool message 插入点、日志顺序、预算扩展、
  result.md/ledger 或 resource feedback；但长期维持大函数也会增加审查成本。
- 迁移期决定：不为追求行数目标删除领域分支，也不把 Stage/LNR/GPU 概念下沉到 DeepCraft。先以 B1–B7
  放行当前 owner 边界；后续仅做 ScienceFlow 内部 method extraction，每个切片继续跑 B2/B3 和 Resume。
