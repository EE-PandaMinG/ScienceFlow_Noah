# ScienceFlow / DeepCraft Tool Runtime 与 legacy 收敛 V2 规划（2026-08-23）

## 1. 复审结论

上一版把 ScienceFlow Tool 层中可下沉范围估计得过小。逐文件检查后，以下四个目录共有
12,170 行 Python：

| ScienceFlow 目录 | 行数 | 复审结论 |
| --- | ---: | --- |
| `core/agent/tool_exec` | 1,811 | 执行流水线应下沉，科研副作用改为 middleware/policy |
| `core/tools` | 6,979 | 内置工具、Shell 安全与执行机制大部分应下沉 |
| `core/agent/tools` | 2,222 | Guard/Artifact 机制应下沉，科研规则留在 SF |
| `core/executor` | 1,158 | 通用 Python/Shell runner 应下沉，数据沙箱策略留在 SF |

目标不应是让这些目录原样保留并减少少量重复，而应是：

1. DeepCraft 拥有完整、可独立使用的 Tool Runtime、内置 Workspace/Shell 工具和代码执行器；
2. ScienceFlow 只提供 Tool policy、科研事件和 Workspace 合同适配；
3. `scienceflow/core/agent/tool_exec` 最终删除；
4. `scienceflow/core/tools` 最终只保留兼容导出和少量 ScienceFlow 专属工具，之后再删除兼容导出；
5. DeepCraft 中两套 public/legacy 类型合并，最终删除 `deepcraft/legacy` 和 `legacy` extra。

全程不得改变 ScienceFlow 的 Prompt、provider payload、Tool Schema、消息顺序、ToolResult 文本、
Memory JSON/JSONL、interaction log、Stage/Gate/ESTRA/Resource/Merge 事件或 Workspace 文件。

## 2. DeepCraft 源码位置与双仓开发方式

DeepCraft 已不在 ScienceFlow 仓库中。当前权威源码为：

- Git 仓库：`git@github.com:EE-PandaMinG/DeepCraft.git`；
- 当前 `main` 与 `v0.1.2` commit：`5f2493374ccd3d318997926714eb0c8c2cbb0f78`；
- ScienceFlow 当前运行副本：`.venv/lib/python3.12/site-packages/deepcraft`；
- 本次审计使用的临时 clone：`/tmp/deepcraft-current-audit-oSaWHJ`。

下一阶段首先在共享 workspace 建立稳定 sibling checkout：

```text
/home/mingming/miing_agents_wsp/
├── scienceflow_lib/   # ScienceFlow 独立 Git 仓
└── DeepCraft/         # DeepCraft 独立 Git 仓
```

不使用 submodule，不把 DeepCraft 源码重新复制回 ScienceFlow，也不把本地 path dependency 写入
`pyproject.toml` 或 `uv.lock`。开发时可临时 editable install；阶段验收必须先给 DeepCraft 打私有 Git
tag，再让 ScienceFlow 更新 tag 和 lock commit。两个仓库始终分别提交、分别测试、分别推送，不发布
PyPI。

## 3. 为什么不能直接删除 `deepcraft/legacy`

DeepCraft 当前约 9,865 行，其中 `src/deepcraft/legacy` 为 2,032 行。ScienceFlow 有 32 个生产文件、
49 行 import 仍引用 `deepcraft.legacy`。它不是不可达旧代码，而是当前真实运行依赖。

目前存在四组重复且不完全兼容的对象：

| 公共对象 | legacy 对象 | 关键差异 |
| --- | --- | --- |
| `memory.Message` dataclass | Pydantic `legacy.Message` | helper、ToolCall 类型、`model_copy`、校验行为不同 |
| `tools.ToolResult` dataclass | Pydantic legacy ToolResult | 默认值、相加、bool、字符串和对象身份不同 |
| context-aware `tools.BaseTool` | kwargs/Pydantic legacy BaseTool | `execute` 签名及 schema 来源不同 |
| public `ToolCollection`/`ToolExecutor` | legacy ToolCollection | 构造、可变性、错误文本、kwargs 转发不同 |

Memory、MemoryRecord、JSON KV storage、BaseAgent、PooledLLM 与 LLM factory 的正式实现也仍放在
`legacy/`。因此“删除 legacy”必须理解为统一 canonical 类型和迁移实现，不能只移动目录或批量替换
import。

## 4. 目标 DeepCraft 结构

建议收敛为以下职责结构，最终源码中不再存在 `legacy/`：

```text
src/deepcraft/
├── agent/
│   └── base.py                 # BaseAgent 与通用生命周期
├── memory/
│   ├── message.py              # 唯一 Message/Role/Function/ToolCall
│   ├── records.py              # 唯一 MemoryRecord 与历史 JSONL codec
│   ├── history.py              # bounded chat history / Memory
│   ├── conversation.py         # generic session store
│   └── storage.py              # memory/JSONL storage
├── llm/
│   ├── online.py
│   ├── pool.py                 # KeyPool + PooledLLM
│   └── factory.py              # 单端点/多端点统一 factory
├── tools/
│   ├── base.py                 # 唯一 BaseTool/ToolResult/ToolContext
│   ├── calls.py                # ToolCall 解析与 invocation
│   ├── collection.py
│   ├── execution/
│   │   ├── engine.py           # single/sequential/parallel 调度
│   │   ├── plan.py             # bundle classification
│   │   ├── middleware.py       # before/after hooks
│   │   └── recorder.py         # memory/event 回写接口
│   ├── builtin/
│   │   ├── workspace.py        # read/write/edit/grep/glob/ls
│   │   └── shell.py            # shell tool facade
│   ├── shell/
│   │   ├── transport.py        # process/stream/cancel/timeout
│   │   ├── guards.py           # 通用 workspace/shell 安全
│   │   └── output.py           # 通用输出与 reducer
│   └── artifacts/
│       ├── store.py            # lossless raw output store
│       └── reducers.py         # 通用 reducer registry
└── executor/
    ├── models.py               # ExecutionResult/CodeRunner
    ├── shell.py
    ├── python.py
    └── output.py
```

目录名称可以在实现前微调，但必须保持单一 canonical 类型、公开 API 和单向依赖。DeepCraft 不能
导入 `scienceflow`，也不能出现 Stage、ESTRA、result.md、solution.py、GPU lease 或 task package
等领域概念。

ScienceFlow 最终不再维护第二套 Tool Runtime，建议只保留明确命名的组合与策略目录：

```text
scienceflow/core/
├── tooling/
│   ├── composition.py          # 组装 DeepCraft tools + SF extensions
│   └── context_adapter.py      # 精确 Memory/log/Workspace 回写
├── agent/policies/tooling/
│   ├── guards.py               # result.md/solution/long-horizon policy
│   ├── coaching.py
│   └── artifacts.py            # Stage/index policy adapter
└── skills/tool.py              # ScienceFlow SkillRegistry extension
scienceflow/safety/tooling/
├── resource_policy.py          # admission/queue/lease/GPU policy
├── progress.py                 # SF/NF progress 与 artifact stability
└── resource_wait.py
```

最终目标是删除 `core/agent/tool_exec`、`core/agent/tools` 和通用 `core/executor`；`core/tools` 在兼容
周期结束后也删除。这里的“删除”指实现已经进入 DeepCraft 或迁到上述明确的 ScienceFlow policy
目录，不是取消现有能力。

## 5. ScienceFlow 各目录迁移清单

### 5.1 `core/agent/tool_exec`

当前四个 Mixin 同时承担 bundle 分类、并发执行、ToolResult 归一化、Memory 写入、interaction log、
raw artifact、write coaching、result.md/long-horizon ledger 和 Stage callback。

迁移方案：

- single/sequential/parallel-readonly/parallel-bash 的执行计划、并发保持顺序、异常归一化和取消下沉到
  `deepcraft.tools.execution`；
- DeepCraft 固定以下 hook 顺序：`before_bundle`、`before_tool`、`invoke`、`after_tool`、
  `record_tool_message`、`after_bundle`；
- ScienceFlow 用 middleware 实现 interaction log、Memory 精确插入、path rewrite、artifact、Stage
  callback、write coaching 和 LNR ledger；
- `blocked_write_edit_bundle`、readonly/mutation 名单和 Bash parallel-safe 判定作为 policy 参数注入；
- 第一阶段仍由现有 RunLoop 调用新 engine，不同时迁移主 RunLoop。

完成后删除整个 `scienceflow/core/agent/tool_exec`。预计迁出 1,000–1,400 行，ScienceFlow policy
adapter 保留约 400–700 行。

### 5.2 `core/tools`

按三类处理：

**完整下沉：**

- Read/Write/Edit/Glob/Grep/Ls 的类实现和 Workspace 原语；
- BaseTool、ToolCollection 的兼容行为；
- `file_utils.py`、`write_placeholder.py`、spawn feedback、通用 timeout feedback；
- ShadowWorkspace 的复制、fingerprint、protected-path validation 机制；
- Bash subprocess、stream、timeout、cancel、exit/signal 和 raw output capture。

**机制下沉、规则注入：**

- `bash/guards.py` 的 command parser、workspace scope、危险删除、全局扫描、privilege、process control、
  stdin、Python/pip normalization；现有规则、顺序和错误文本先作为冻结 policy profile 注入；
- `resource_classifier.py` 的 tokenization/segment/command classifier engine 下沉，ScienceFlow 的训练、
  solution script、GPU resource class 规则留在 ScienceFlow；
- Bash output reducer framework 下沉，ScienceFlow training/pytest/evidence reducer 作为插件注册。

**留在 ScienceFlow，但迁出通用 tools 目录：**

- `ResourceWaitTool`；
- `SkillTool` 与 ScienceFlow SkillRegistry；
- ScienceFlow heartbeat/NF progress、artifact stability、resource context generation；
- GPU admission、queue、lease、metric history、resource observer 和 boundary feedback。

完成后 `scienceflow.core.tools` 先作为旧 import facade 重导出 DeepCraft 内置工具；跨一个固定 tag 后，
生产消费者改到新的 ScienceFlow tool composition 模块，再删除 facade。

### 5.3 `core/agent/tools`

- `ToolGuard`、`GuardManager` 生命周期和可组合 guard protocol 下沉；
- repeat failure、edit/write failure、runtime signature 等领域无关 guard 下沉为可配置 guard；
- raw Tool output 的 reserve/write/hash/index 基础 store 与 reducer registry 下沉；
- Bash command 的通用读写/并发安全分类下沉；
- result.md、solution.py、long-horizon、no-progress hard stop、explore streak、训练错误提示、Stage log
  mirror 等规则保留在 ScienceFlow policy 包；
- ScienceFlow policy 提供现有阈值和完整消息文本，DeepCraft 不内置这些 Prompt/反馈。

完成后该目录不再以含糊的 `agent/tools` 命名；保留内容迁到 `scienceflow/core/agent/policies/tooling`
或 `scienceflow/safety/tooling`。

### 5.4 `core/executor`

该目录 1,158 行，目前没有 ScienceFlow 生产调用者或测试直接消费，但可能属于历史公开接口，不能直接
删除：

- `ExecutionResult`、`CodeRunner`、PythonRunner、ShellRunner、通用 traceback/output parser 和缺包
  解析下沉到 `deepcraft.executor`；
- AsyncInterpreter 的 runner 调度机制下沉，CPU/GPU env 通过 callback 注入；
- dataset truncation、submission rename、node-id rewrite 和 leakage detector 留在 ScienceFlow sandbox
  policy；
- ScienceFlow 旧 import path 先做 re-export，并新增 characterization tests；确认一个版本周期无外部
  依赖后再删除。

## 6. DeepCraft `legacy/` 合并路线

### D0：冻结 legacy 行为

为以下行为新增 public-vs-legacy golden：Message constructor/helper/serialization、Function/ToolCall、
ToolResult 默认值/str/bool/add/copy、MemoryRecord bytes、bounded Memory window、ToolCollection error 与
kwargs、BaseAgent state、PooledLLM routing/retry。Golden 必须使用 ScienceFlow 旧 Workspace fixture。

### D1：统一无 Pydantic 的 canonical value objects

- 扩展 public Message、Function、ToolCall、ToolResult，使其覆盖 ScienceFlow 实际使用的 helper、
  coercion 和 copy API；
- 保持 DeepCraft 最小安装不强制引入 Pydantic；需要的 `model_dump`/`model_copy` 兼容面由轻量方法
  提供，而不是复制一套模型；
- public Runtime、CLI 与 ScienceFlow 同时切换到同一对象身份；
- `deepcraft.legacy.message` 和 `legacy.tool.result/calls` 暂时只做 re-export，禁止保留第二份 class。

如果 characterization 证明某个 Pydantic 校验副作用属于 ScienceFlow 可观察合同，则只为该字段实现
明确校验，不把整个 legacy 模型保留下来。

### D2：统一 BaseTool、ToolCollection 与 ToolExecutor

- 设计唯一 invocation boundary：executor 始终接收 `ToolInvocation + ToolContext`；
- canonical adapter 支持 ScienceFlow 当前 `execute(**kwargs)`，但新工具只实现规范接口；
- 合并两个 ToolCollection，覆盖旧构造方式、顺序、`add_tool(s)`、`to_params`、错误文本和 extra kwargs；
- ScienceFlow `core/tools/base.py` 与 `tool_collection.py` 降为 re-export，之后删除。

### D3：迁移 Memory、Agent 与 LLM 实现

- `legacy/memory/*` 分别合入 `deepcraft.memory.history/records/storage`；
- public `memory/legacy_records.py` 反向引用 legacy 的异常依赖必须消失；
- `legacy/agent/base.py` 合入 `deepcraft.agent.base`；
- `legacy/llm/pooled.py` 和 factory 合入 `deepcraft.llm.pool/factory`，`legacy/llm/base.py`、
  `online.py` 纯重导出直接清理；
- ScienceFlow 所有 49 行 `deepcraft.legacy` import 改为 canonical import，保持对象身份测试。

### D4：删除 legacy namespace

建议使用两个私有 Git 版本边界：

1. DeepCraft `v0.2.x`：canonical 实现完成，`legacy/` 只剩 deprecation re-export；ScienceFlow 更新并
   验证所有生产 import 已使用 canonical API；
2. DeepCraft `v0.3.0`：删除 `legacy/`、`legacy` extra 和对应测试分组，ScienceFlow 更新 lock 后执行
   完整门禁。

版本号是建议的兼容边界，不代表 PyPI 发布；仍只使用私有 Git tag。若希望一个阶段直接完成，也必须
保留两个独立 commit/tag 检查点，保证可回退和二分定位。

## 7. 实施阶段与依赖顺序

| 阶段 | DeepCraft 变更 | ScienceFlow 变更 | 主要门禁 |
| --- | --- | --- | --- |
| T0 | 建立 sibling checkout、冻结 canonical/legacy golden | 冻结 Tool Schema/Context/Workspace golden | B1、B2 baseline + B3 full |
| T1 | D1 value objects | 替换 Message/ToolCall/ToolResult import | B1 + B3 quick |
| T2 | D2 Tool contracts/collection | 基础工具改用 canonical contract | B1、B2 + B3 quick |
| T3 | 内置 Workspace tools、shell guards | 六个 wrapper 降为 facade | B2、B3 full、B4 |
| T4 | Tool execution engine/middleware | 删除 `agent/tool_exec`，保留 SF policy | B2–B5 |
| T5 | artifact/guard framework | 重排 `agent/tools` 为 policy | B2–B4 |
| T6 | code executor | `core/executor` 降为 facade | B2、B3、B7 |
| T7 | D3 Memory/Agent/LLM | 清零 `deepcraft.legacy` import | B1–B5 |
| T8 | D4 删除 legacy | 更新 Git tag/lock | B1–B5、B7、两仓 full tests |
| T9 | 删除 SF facade | 形成最终目录 | B1–B7 全部门禁 |

不能并行实施存在类型依赖的 T1–T4；测试可以并行。T3 以后 DeepCraft 与 ScienceFlow 每个切片都必须
分别提交，DeepCraft commit/tag 在前，ScienceFlow 消费 commit 在后。

## 8. 强制 Benchmark 门禁

验证方式沿用前一轮迁移：确定性 benchmark 保护上下文、机制和 Workspace，真实任务 benchmark 保护
最终科学效果。Unit test 通过不等于迁移通过。

所有 baseline 必须在对应迁移代码之前以独立 Git commit 冻结。迁移提交不得同时修改 baseline、
comparator、容差或 allowlist；若 benchmark 暴露历史问题，只能先记录，不能通过放宽比较器让迁移
通过。每次阶段验收都保存机器可读 JSON report、DeepCraft commit、ScienceFlow commit、`uv.lock`
hash、Python 版本和执行命令。

### B1：Canonical Model Contract

新增 DeepCraft canonical/legacy 等效 benchmark，冻结：

- Message/Role/Function/ToolCall 构造、helper、coercion、copy、字段类型及序列化；
- ToolResult 的默认值、`str`、`bool`、相加、copy、output/error/system；
- MemoryRecord JSON bytes、bounded window、system prefix 和 long-term JSONL；
- BaseAgent state、ToolCollection 构造/顺序/错误/kwargs、PooledLLM 路由与 retry。

通过标准：canonical 输出与冻结 legacy fixture 严格一致；迁移到 re-export 阶段后，同名 public/legacy
对象还必须满足 identity 断言。T8 删除 legacy 后继续用同一 fixture 比较 canonical 输出，不能重新录制。

### B2：Tool Runtime Contract

新增 `tool_runtime_contract` benchmark，至少覆盖：

- exact Tool Schema JSON、字段顺序、description、required、默认值和 Tool 顺序；
- single、invalid、ToolError、sequential、parallel readonly、parallel Bash、blocked write/edit bundle；
- `before_bundle`、`before_tool`、`invoke`、`after_tool`、`record_tool_message`、`after_bundle` 顺序；
- Memory 消息插入点、ToolCall id/name/arguments、ToolResult output/error/system 和 raw artifact；
- read/write/edit/grep/glob/ls 的成功结果及全部历史错误文本；
- Bash guard 顺序、normalization、timeout/cancel/signal、stream chunk、返回码和进程树清理；
- interaction.log、tool output index、Stage callback、result.md 与 long-horizon ledger 副作用。

fixture 建议放在 `tests/fixtures/tool_runtime_contract/baseline_v1`。通过标准为 Context、Mechanism、
Workspace、Schema 和 error-text 未登记差异全部为 0。

### B3：Runtime Parity Baseline v2

继续使用现有确定性 benchmark，不生成 v3 替换它：

```bash
.venv/bin/python scripts/run_runtime_parity.py --suite quick --jobs 4
.venv/bin/python scripts/run_runtime_parity.py --suite full --jobs 4
.venv/bin/python scripts/run_runtime_parity.py --suite performance --jobs 1
.venv/bin/pytest -q tests/test_runtime_parity_benchmark.py
```

通过标准：`failed_cases`、`context_diff_count`、`mechanism_diff_count`、
`workspace_unregistered_diff_count` 全部为 0。Performance 串行运行，避免并发调度噪声。

### B4：Workspace 与 Resume Contract

复用历史 Circle Packing Worker=1/2 Workspace manifest、Memory fixtures 和 exact-start Resume
Workspace，并为 Tool migration 新增一次 mutation-heavy fixture。比较命令沿用：

```bash
.venv/bin/python scripts/workspace_contract_manifest.py CANDIDATE_ROOT \
  --output /tmp/candidate_workspace_contract.json
.venv/bin/python scripts/workspace_contract_compare.py \
  BASELINE_MANIFEST /tmp/candidate_workspace_contract.json \
  --mode strict --output /tmp/workspace_contract_report.json
```

必须比较目录/软链接、配置、interaction log、short-term/long-term Memory、Stage ledger、Snapshot、
tool artifact/index、state、final artifact 和 JSON/JSONL 行顺序。只有已登记的时间戳、PID、临时根路径
和外部 request id 可以归一化；未登记 mismatch 必须为 0。

Resume 必须从迁移前真实 Workspace 副本继续，验证 pending tool、last tool result、Stage restore、失败
恢复、人工停止后继续和 Worker=2 merge；不允许只新建一个空 Workspace 做 smoke。

### B5：CLI 与跨仓组合 Benchmark

同时覆盖：

- standalone `deepcraft run/repl/tools/events`；
- `scienceflow agent run/repl/tools` 组合入口；
- ScienceFlow 正常 `repl/parallel` 入口；
- 两轮 session 恢复、event sequence、退出码、SIGINT/cancel 和无 LLM 的 tools schema；
- 一个短 vLLM 实机任务，输出 sentinel、session role 顺序和 event JSONL 条数严格断言。

通过标准：命令、默认参数、环境变量映射、Tool Schema、退出码、session/event JSONL 和 Workspace
副作用与 baseline 一致。DeepCraft CLI 成功不能替代 ScienceFlow CLI 验证。

### B6：真实科学任务效果 Benchmark

最终候选沿用此前配对方式，reference 不重复生成：

- Circle Packing seeds `2222`、`3333`、`4444`；每 seed `worker=2`，三个 seed 并行；
- 模型、provider、temperature、CPU/GPU、900 秒 LNR 预算、Evaluator、Gate 和 manifest 保持一致；
- 复用历史 reference root，仅运行 candidate；
- 使用 `scripts/circle_packing_effect_gate.py` 生成机器可读报告；
- 再运行 exact-start historical Workspace continuation，隔离模型重新探索随机性；
- 至少补一个非 Circle 优化任务 Resume；scientific-design extra 可用时补一个代表任务。

Circle Packing 通过标准沿用旧门禁：三个 candidate 均为 `completed`、`validation_ok=true`、
`selection_eligible=true`；每个 seed、三 seed 中位数和最差 seed 的指标不得退化；每 seed 和中位耗时
不得超过 reference 10%。真实任务得分改善不能抵消 B1–B5 的任何合同差异。

### B7：完整测试与性能 Benchmark

- DeepCraft 独立 full tests、Ruff、format、复杂度和包边界全部通过；
- ScienceFlow `pytest -q` 全量通过，既有测试不得被删除、改成 skip 或放宽断言；
- cross-repo locked-tag 与 nightly-main contract 均通过；
- Runtime performance suite 无未登记差异，通用调度开销回归不超过 2%；
- Tool single/parallel、Bash spawn/stream、Memory append 和 JSONL write 分别记录中位数与 P95；
- 不允许用更少的日志、减少 evaluator/guard 调用或关闭安全检查换取性能。

### 8.1 各阶段运行频率

每个原子切片并行运行 B1/B2 受影响 case、B3 quick、两仓 affected tests 和静态检查，目标 1–3 分钟。
每个 tag/阶段边界运行 B1/B2 全量、B3 full/performance、B4 和两仓 full tests。T4、T7 阶段额外运行
B5 短实机与 Resume。完整 B6 只在 T9 最终候选运行一次；T8 到 T9 若发生任何生产执行路径变化，
则最终候选以 T9 commit 为准重新运行，不能复用较早 candidate。

最终删除旧实现和 facade 的条件是 B1–B7 同时通过。任何一项失败，保留兼容实现并回退当前切片，
不得进入下一阶段。

## 9. 预期规模变化

- ScienceFlow 四个目标目录预计从 12,170 行降到约 3,500–5,000 行，最终兼容 facade 删除后可更低；
- 预计从 ScienceFlow 迁出约 5,000–7,000 行通用机制，而不是上一版估计的数百行；
- DeepCraft 会吸收其中约 3,500–5,000 行，但通过统一 public/legacy 类型、复用现有 workspace/subprocess
  原语，预计不会等量增长；
- DeepCraft `legacy/` 从 2,032 行降为 0，`legacy` extra 删除；
- 两仓合计预计净减少约 1,500–3,000 行。

这些数字是结构目标，不是硬门禁。如果删除某段代码会改变 ScienceFlow 的上下文、机制或 Workspace
输出，则应保留兼容 adapter，不能为了达成行数目标牺牲行为。

## 10. 第一批可执行切片

建议下一轮只做 T0 和 T1：

1. 建立稳定 DeepCraft sibling checkout；
2. 新建 B1 canonical model 与 B2 `tool_runtime_contract` benchmark，并从现有测试提取 golden，不运行
   长任务；
3. 在 DeepCraft 统一 Message/Function/ToolCall/ToolResult；
4. 保留 legacy re-export，在 ScienceFlow 分批替换 import；
5. 两仓分别提交并通过 B1、B2 和 B3 parity quick；
6. 打一个 canonical-model Git 检查点，再进入 ToolCollection/Executor。

这是后续大规模 Tool 下沉的前置条件。若不先统一对象身份，直接搬迁 `tool_exec` 会让同一次 diff 同时
包含调度变化、序列化变化和类型变化，出现上下文差异时难以定位。

## 11. 实施记录（2026-08-23）

截至最终验收候选，T0–T9 的代码阶段已经完成：

- DeepCraft canonical runtime 依次落在 `v0.2.0-dev1` 至 `v0.2.0-dev6`；`v0.3.0`
  (`880fc90`) 删除 `deepcraft.legacy` namespace、`legacy` extra 和旧测试分组；
- ScienceFlow `1648883` 固定消费 `deepcraft-runtime[openai]@v0.3.0`，生产源码、测试和 deterministic
  benchmark 均不再 import `deepcraft.legacy`；
- ScienceFlow `0ee5b2a` 删除 `core/agent/tool_exec` 与 `core/agent/tools`，保留的上下文回写和领域规则分别
  进入 `core/tooling/execution` 与 `core/agent/policies/tooling`；
- ScienceFlow `47ccac8` 删除 `core/tools` 和通用 `core/executor` facade；组合入口进入
  `core/tooling/composition.py`，Skill、resource/shell policy、ScienceFlow sandbox 分别进入明确 owner；
- 阶段门禁结果：DeepCraft `145 passed`；ScienceFlow 受影响集 `485 passed, 7 skipped` 和
  tool/resource 受影响集 `671 passed, 4 skipped`；B2 五类 diff 为 0，B3 quick/full/performance 的
  context、mechanism、workspace 未登记差异和 failed case 均为 0。

以上结果不是最终放行；最终候选仍须按第 8 节完成 B1–B7，尤其是两仓 full tests、CLI、历史
Workspace/Resume、性能和 Circle Packing 三 seed `worker=2` 实机门禁。最终报告不得用阶段结果替代。
