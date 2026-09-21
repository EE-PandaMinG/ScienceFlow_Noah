# ScienceFlow 统一 TUI 与长程研究最小侵入规划 V2

状态：轻量 TUI 代码与验收已完成；待按依赖顺序发布 PyPI；LNR 基线观察项见 16.3
日期：2026-09-03
实施分支：`product`
规划基线：`3488071`
InquiryCraft 实施基线：`e3bb8ba`
需求基线：[`plan_v1.md`](plan_v1.md)
关联架构收口：[`../plan_v5.2.md`](../plan_v5.2.md)
长程机制验收：[`../../../benchmark/bench_sf_v1.md`](../../../benchmark/bench_sf_v1.md)

## 1. 刷新结论

V2 经代码复查后改为最小侵入方案。现有代码已经拥有 Task、Config、Parallel manifest、
CPU/GPU 分配、Evaluator、Gate、Monitor 和 Resume，不再为 TUI 新建平行合同或运行系统。

产品行为保持：

```text
scienceflow tui
    |
    +-- 普通文本 ----------> 现有 InquiryCraft Agent Loop
    |
    +-- /long-research ----> 问询必要配置
                               -> 生成现有 Parallel manifest
                               -> 调用现有 evaluator/gate 做 preflight
                               -> 用户确认
                               -> 现有 ParallelRunner / LNR
```

不存在 `/goal` 或 `/quick`。TUI 启动后默认就是 Agent Loop；只有 `/long-research` 能进入长程
研究。现有 `scienceflow run`、`parallel`、`monitor` 和 Resume 入口继续保留。

## 2. 复用审计

| 需求 | 现有 owner | V2 决策 |
| --- | --- | --- |
| 普通 Agent TUI | InquiryCraft `InquiryCraftTui` | 原样复用 |
| stream/tool/conversation | InquiryCraft AgentRuntime | 原样复用 |
| 通用 slash commands | InquiryCraft `parse_submission` | 原样复用 |
| task description | Parallel manifest inline `task` | 不新增 Task contract |
| dataset path/layout | `input_data_dir` + `scan_data_dir` | 复用 |
| evaluator/gate config | `Config.evaluator`、`Config.gate` | 复用 |
| evaluator/gate runtime | `EvaluatorManager`、`GateManager`、assessment pipeline | 复用 |
| 注册任务 | `TaskPackageSpec` | 优先复用 |
| 未注册任务 | inline task + `artifact_command` | 复用 |
| 执行配置 | Parallel `TaskSpec` | 不新增 RunPlan |
| worker 数 | `lnr.num_workers` | 问询后写入 manifest |
| GPU | `gpu_list: cpu/auto/0,1` | 复用解析和分配 |
| CPU | `cpu_list` + worker slicing | 只问总 CPU pool |
| 时限 | `time_limit` + `wall_clock_budget_sec` | 复用 |
| Monitor | `interfaces/ui/monitor` projection | 复用 |
| Resume | Parallel/LNR state | 复用 |

现有行为已经覆盖：

- `gpu_list: auto` 根据 LNR worker 数选择对应 GPU 数；
- `gpu_list: "0,1"` 固定候选 GPU；
- `gpu_list: cpu` 显式禁用 GPU；
- 一个任务级 `cpu_list` 会被切成互不重叠的 worker CPU sets；
- manifest 已合并 `lnr`、`agent`、`evaluator` 和 `gate`；
- Parallel 已处理 workspace、timeout、GPU assignment、结果状态和 Resume。

## 3. 最小新增面

### 3.1 InquiryCraft

不拆 `InquiryCraftTui`，只增加一个公开宿主输入拦截口：

```text
InquiryCraft/src/inquirycraft/tui/
  contracts.py       # 新增 TuiHostPort / TuiSubmissionInterceptor
  app.py             # submit_text 前调用 interceptor
  __init__.py        # 公共 export

InquiryCraft/src/inquirycraft/cli/
  app.py             # TUI command factory 接收 interceptor
```

建议合同：

```python
class TuiHostPort(Protocol):
    @property
    def busy(self) -> bool: ...

    async def notice(self, text: str) -> None: ...
    async def cancel_agent(self) -> None: ...
    def conversation_snapshot(self) -> ConversationSnapshot: ...
    def set_host_status(self, text: str) -> None: ...


class TuiSubmissionInterceptor(Protocol):
    async def try_handle(self, text: str, host: TuiHostPort) -> bool: ...
```

InquiryCraft 的唯一执行变化：

```python
async def submit_text(self, text: str) -> None:
    if self.interceptor is not None:
        if await self.interceptor.try_handle(text, self.host_port):
            return

    # 现有 parse_submission / dispatch 完全保持
```

返回 `False` 时，普通输入和现有 `/cancel`、`/status`、`/help` 行为不变；返回 `True` 时，宿主已
处理 `/long-research` 或正在进行的问询回答。

禁止 ScienceFlow 继承并覆盖 InquiryCraft 私有 `_dispatch_submission()`，也不复制 TUI。

### 3.2 ScienceFlow

首版只新增：

```text
scienceflow/interfaces/cli/commands/run/tui.py
scienceflow/interfaces/ui/long_research.py
scienceflow/research/onboarding/
  __init__.py
  session.py
  manifest.py
  preflight.py
  support/
    answers.py
    gate_probe.py
    task_defaults.py
scienceflow/runtime/parallel/service.py
```

`support/` 只是内部职责拆分，使状态机和 preflight 文件保持有界；它不增加公共合同或第二套
运行抽象。

不新增：

- `interfaces/ui/tui/screens/*`；
- 新的 AgentSurface/AgentSessionController；
- ResearchTaskContract/RunPlan；
- `runtime/launch/` 包；
- `quality/preflight/` 子系统；
- 新的 ResourceInventory 架构；
- 与现有 manifest 并行的 task/run 配置格式。

## 4. `/long-research` 交互 owner

`scienceflow/interfaces/ui/long_research.py` 是 InquiryCraft TUI interceptor 的 ScienceFlow
实现，只拥有输入路由和 transcript 展示：

```python
class LongResearchInteraction:
    def __init__(self, onboarding_factory):
        self.session: LongResearchSession | None = None

    async def try_handle(self, text: str, host: TuiHostPort) -> bool:
        if is_long_research_command(text):
            if host.busy:
                await host.notice("Agent is running; finish or cancel before long research.")
                return True
            self.session = self.onboarding_factory.start(
                conversation=host.conversation_snapshot(),
                constraints=long_research_argument(text),
            )
            await host.notice(self.session.next_prompt())
            return True

        if self.session is not None:
            update = self.session.answer(text)
            await host.notice(update.message)
            return True

        return False
```

边界：

- 普通输入直接进入 Agent Loop；
- `/long-research` 不作为消息发送给模型；
- 模型输出中的 `/long-research` 不能触发 host action；
- Agent 正在生成时不读取半完成 conversation；
- onboarding 可取消并回到同一个 Agent session；
- UI 文件不解释 evaluator、Gate、GPU 或 worker policy。

第一版问询直接使用现有 transcript 和输入框，不先开发按钮、表单或多屏页面。确有体验需求后再
增加通用 choice widget。

## 5. LongResearchSession

`research/onboarding/session.py` 只保存生成 manifest 所缺的字段和问询状态：

```python
@dataclass(slots=True)
class LongResearchDraft:
    task_text: str = ""
    exp_id: str = ""
    run_id: str = ""
    workspace_base: str = ""
    input_data_dir: str = ""
    metric_name: str = ""
    lower_is_better: bool | None = None
    artifact_path: str = ""
    evaluator: dict[str, object] = field(default_factory=dict)
    gate: dict[str, object] = field(default_factory=dict)
    workers: int | None = None
    cpu_list: str = ""
    gpu_list: str = ""
    wall_clock_sec: int | None = None
```

该 draft 是短生命周期 onboarding state，不是新的运行公共合同。最终只输出标准 Parallel
manifest；加载后继续使用现有 `runtime.parallel.config.models.TaskSpec`。

状态机保持简单：

```text
DRAFTING -> ASKING -> PREFLIGHT -> CONFIRM -> RUNNING / CANCELLED
```

`next_question()` 只询问仍为空或存在冲突的关键字段，不重复询问已经由用户明确给出的值。

## 6. 配置问询

首版问题顺序：

1. 数据目录在哪里；
2. 目标 metric 和方向是否明确；
3. 是否用 GPU，自动还是指定 `0`、`1`、`0,1`；
4. worker 数量；
5. 可使用的总 CPU pool；
6. 运行时长；
7. evaluator/gate 摘要确认。

示例：

```text
> /long-research

ScienceFlow:
检测到 GPU 0（72 GB free）和 GPU 1（68 GB free）。
请选择：auto / 0 / 1 / 0,1 / cpu

> 0,1

ScienceFlow:
建议 2 workers。CPU 可用 0-31，将由现有 worker runtime 自动分成 0-15 和 16-31。
Worker 数量：2（推荐）/ 1 / 自定义
```

问询结果直接映射：

| 用户答案 | 现有 manifest 字段 |
| --- | --- |
| CPU only | `gpu_list: cpu` |
| 自动 GPU | `gpu_list: auto` |
| GPU 0、1 | `gpu_list: "0,1"` |
| 两个 worker | `lnr.num_workers: 2` |
| CPU 0-31 | `cpu_list: "0-31"` |
| 一小时 | `lnr.wall_clock_budget_sec: 3600` |
| runner buffer | `time_limit: 4200` |

资源展示复用 `runtime/core/support/system_resources.py`。只需将现有 GPU probe 小幅扩展为
`index,uuid,memory.total,memory.free`；不建立新 ResourceInventoryService。最终资源 acquisition、
queue、sharing 和 release 仍由 ResourceManagementService/ResourceRuntime 决定。

## 7. Manifest 是唯一运行配置

`research/onboarding/manifest.py` 生成现有格式：

```yaml
max_concurrent: 1
time_limit: 4200
resume: false

lnr:
  resource_control_mode: resource_smart_policy

defaults:
  config: scienceflow/foundation/config/default.yaml
  phase: run
  type: lnr
  workspace_base: ./workspaces/generated
  evaluator:
    enabled: true
    backend: artifact_command
  gate:
    params:
      minimum_metric_validity: high

tasks:
  - exp_id: generated-task
    run_id: generated-run
    task: |
      从当前会话提炼的任务描述
    input_data_dir: /data/example
    time_limit: 4200
    cpu_list: "0-31"
    gpu_list: "0,1"
    lnr:
      wall_clock_budget_sec: 3600
      num_workers: 2
      omp_threads_cap: 8
```

文件保存为：

```text
<workspace>/.scienceflow/run_manifest.yaml
<workspace>/.scienceflow/onboarding.json
<workspace>/.scienceflow/preflight_report.json
```

不再生成额外 `task.yaml`、`run.yaml` 和双 hash 体系。Resume 继续以原 manifest、resolved config
和现有 state 为准。`onboarding.json` 只记录用户答案与生成来源，便于解释，不参与运行解析。

已登记任务使用 `TaskPackageSpec + task_package` evaluator；未登记任务使用 inline `task` 与现有
`artifact_command` 配置。只有确实缺少 evaluator 时，才在 `.scienceflow/evaluator/` 生成最小
validator。

## 8. Preflight 只编排现有能力

`research/onboarding/preflight.py` 不创建新的评价框架，只依次调用：

```text
scan_data_dir
    -> Parallel manifest load/validation
    -> EvaluatorManager / configured backend
    -> GateManager / CandidateAssessmentPipeline
    -> PreflightReport
```

最低检查：

- dataset 存在且可读；
- manifest 能解析成现有 TaskSpec；
- evaluator backend 已登记；
- artifact path、metric 名称和方向完整；
- baseline/smoke evaluator 可以执行；
- 缺失、损坏或非有限 metric 被拒绝；
- Gate 对 evaluator failure 保持 fail-closed；
- CPU/GPU/worker 配置可解析。

Preflight 只新增执行顺序和报告，不复制 ArtifactCommandBackend、TaskPackageBackend 或 GatePolicy。

无法建立权威 evaluator 时允许用户继续 exploratory run，但必须明确提示，不能标为 verified。

## 9. 公共 Parallel 运行入口

不创建 `runtime/launch/` 包，只在 `scienceflow/runtime/parallel/service.py` 增加公共函数：

```python
@dataclass(frozen=True, slots=True)
class ParallelRunSummary:
    results: tuple[TaskResult, ...]
    text: str


async def run_manifest(
    manifest_path: str | Path,
    *,
    max_concurrent: int | None = None,
    log_dir: str | Path | None = None,
) -> ParallelRunSummary:
    runner = ParallelRunner(
        manifest_path,
        max_concurrent=max_concurrent,
        log_dir=log_dir,
    )
    results = await runner.run_all()
    return ParallelRunSummary(tuple(results), runner.format_summary(results))
```

调用关系：

```text
LongResearchInteraction --+
                           +--> run_manifest() --> ParallelRunner --> LNR
scienceflow parallel ------+
```

这样 CLI 不再读取 `_tasks`、`_max_concurrent` 私有字段，TUI 也不直接构造 runner。现有脚本参数
与 manifest 保持兼容。

## 10. Monitor、退出与 Resume

第一版不把现有 Rich Monitor 重写成 Textual screen：

- TUI 通过现有 state projection 显示一行/一块摘要；
- 完整监控继续使用 `scienceflow monitor --manifest ...`；
- `/status` 可显示生成 manifest、run id、worker 和剩余时限；
- TUI 退出时询问 cancel 或保留可 Resume 状态；
- 进程终止与资源释放走现有安全路径；
- 后续确需统一全屏 Monitor 时，只复用 projection，不复制 JSONL 解析。

首版不承诺 daemon 式 detach/attach；先保持当前 runner 生命周期语义，避免同时引入新的进程
supervisor。已有异常中断 Resume 能力不受影响。

## 11. 实施切片

### S0：InquiryCraft TUI interceptor（已完成）

- 新增 TuiHostPort/TuiSubmissionInterceptor；
- 在现有 `submit_text()` 前调用；
- 暴露可配置 TUI command factory；
- 现有 TUI/CLI 行为 parity 测试。

完成条件：无 interceptor 时行为逐项不变；宿主可以消费未知命令和后续回答。

### S1：ScienceFlow TUI 与 `/long-research`（已完成）

- Light 依赖启用 `inquirycraft[tui]`；
- 添加根级 `scienceflow tui`；
- 注册 LongResearchInteraction；
- 默认普通文本直接 Agent Loop；
- command、busy、cancel 和模型文本不可伪造测试。

完成条件：无任何任务配置也能聊天；只有 `/long-research` 进入问询。

### S2：问询与 manifest（已完成）

- conversation -> LongResearchDraft；
- 复用 dataset scan；
- GPU、worker、CPU、时限问询；
- 生成标准 manifest；
- 用现有 ParallelRunner loader 验证。

完成条件：陌生 fixture task 不手写 YAML 即可得到现有 runner 可加载的 manifest。

### S3：Evaluator/Gate preflight（已完成）

- 优先匹配 TaskPackage；
- 未登记任务生成 artifact_command 配置；
- 调用现有 evaluator/gate pipeline；
- 输出 preflight report 和确认摘要。

完成条件：无效 artifact、metric 方向缺失、evaluator failure 和 gate rejection 被正确展示。

### S4：公共运行入口（已完成）

- 增加 `run_manifest()`；
- CLI parallel 改用公共入口；
- TUI 确认后调用同一入口；
- 复用现有 Monitor/Resume。

完成条件：TUI 与 CLI 使用同一 manifest 得到相同 resolved TaskSpec 和运行结果状态。

### S5：发布收口（已完成）

- Light wheel clean-install；
- `scienceflow tui --help` 与启动 smoke；
- 短 fixture 端到端；
- 发布候选选择 `bench_sf` 关键 Resume point；
- Circle/Nomad/TFBind8 `w2-2h` 仍只用于正式发布验收。

## 12. 验收矩阵

| 场景 | 期望 |
| --- | --- |
| `scienceflow tui` | 直接进入现有 Agent Loop |
| 普通文本 | interceptor 返回 false，行为与 IQ TUI 一致 |
| `/long-research` | 开始问询，不发送给模型 |
| Agent busy | 不截取半完成 conversation，提示完成或 cancel |
| 已提供 GPU/worker | 不重复询问 |
| 选择 GPU `0,1` | manifest 写入 `gpu_list: "0,1"` |
| 两个 worker + CPU 0-31 | 现有 runtime 分出互不重叠 CPU sets |
| 自动 GPU | 现有 runner 按 worker 数解析与分配 |
| 已登记任务 | 复用 TaskPackage evaluator/gate |
| 未登记任务 | inline task + artifact_command |
| preflight 失败 | 不启动或由用户明确选择 exploratory |
| TUI 启动 | 调用公共 `run_manifest()` |
| CLI 启动 | 调用同一 `run_manifest()` |
| 中断/Resume | 沿用现有 state 和 Resume 语义 |

## 13. 日常测试

普通提交只运行：

1. InquiryCraft interceptor parity；
2. `/long-research` command/busy/cancel；
3. LongResearchSession 问询顺序；
4. manifest fixture 与现有 loader parity；
5. GPU auto/explicit/cpu 和 worker CPU slicing；
6. evaluator/gate preflight 正反例；
7. TUI/CLI `run_manifest()` parity；
8. Light wheel TUI smoke。

不在每次 TUI 修改后运行全量长程任务。关键机制继承由 `bench_sf` Resume checkpoint 验证，正式
发布才执行完整 `w2-2h` 验收。

### 13.1 三层验证与结论隔离

| 层级 | 入口 | 回答的问题 | 失败分类 |
| --- | --- | --- | --- |
| 快速合同 | `pytest` | 接口、配置和确定性逻辑是否正确 | code/config regression |
| Resume 技术点 | `bench_sf release` 或按变更选择 point | 关键长程状态能否被当前代码继承并继续 | `failed` / `unreached` / `environment_error` |
| 从零长程 | Circle、Nomad、TFBind8 `w2-2h` | 并发压力下完整链路能否运行、评估和收口 | framework / model / scientific effect 分栏记录 |

`bench_sf` 的 point/chain/release 是 checkpoint Resume 实测，不是 pytest，也不要求跑满两小时。
它验证 exactly-once、Stage、ESTRA、peer context、资源恢复和 finalization 等技术边界。只有从空
Workspace 启动的三项任务才属于 2h 长程验证。

长程报告必须拆分以下三种结论，不以 launcher exit code 或最终分数互相替代：

1. `framework_result`：事件顺序、CPU 隔离、Evaluator/Gate、Stage、Resume/ESTRA、Merge/Finalization、
   timeout 和 cleanup 是否满足合同；
2. `model_result`：模型是否触发工具、是否形成候选、是否出现 text-only stop、超长 streaming 或格式错误；
3. `scientific_effect_result`：artifact 合法性、最终数量、权威指标和相对基线效果。

当前本机 Qwen3.5-9B vLLM 只用于框架逻辑验证。它的候选质量、技术点未触发或科学分数下降不得直接
记为框架回归；同样，模型给出高分也不能掩盖 hard invariant、Gate、资源隔离或 cleanup 失败。

### 13.2 推荐执行顺序

1. 运行受影响单元/合同测试；
2. `bench_sf audit`，再运行 diff 选中的 point；发布候选运行 CPU `bench_sf release`；
3. 只有 GPU 无外部 compute process 时才显式运行两个 physical GPU point；不得抢占或清理外部任务；
4. 固定代码、模型 endpoint、数据 revision、manifest SHA 和起始时间；
5. 并行启动 Circle `0-15`、Nomad `16-31`、TFBind8 `32-47`，每项 Worker=2；
6. 每 5–10 分钟检查 launcher、worker、provider、Stage 和资源事件，不用频繁全量解析 Workspace；
7. 任务完成后生成独立证据摘要，确认所有 benchmark-owned process 和 lease 清零。

本轮 2h profile 使用 `wall_clock_budget_sec: 7200`，外层 `time_limit: 7800` 为评估、收口和清理
预留 600 秒。三项均设置 `gpu_list: cpu` 和空 `resource_gpu_pool`；这里的 CPU 指任务侧计算，六个
worker 仍共享远端/本机 vLLM provider。provider 并发不足导致的排队必须记录为环境噪声。

### 13.3 启动前硬检查

- 三个 dataset 路径存在；TFBind8 public view 必须由锁定 revision 的 prepare 命令生成；
- manifest 能被当前 ParallelRunner 解析，run id 和 Workspace 路径没有复用；
- `CODE_MODEL`、`CODE_BASE_URL`、`CODE_API_KEY` 以及 feedback 对应变量显式设置；
- 对只允许单个首位 system message 的 vLLM chat template，显式设置
  `CODE_COALESCE_SYSTEM_MESSAGES=true` 和 `FEEDBACK_COALESCE_SYSTEM_MESSAGES=true`；
- `/v1/models` 可达且实际 served model 与记录一致；
- 三个 CPU 集互不重叠，并核查主机外部负载；
- vLLM/GPU 有外部任务时，标记共享服务环境，禁止执行 `bench_sf --include-gpu`；
- 旧 Workspace 不以 `resume: false` 重新覆盖；
- 连续 streaming 由外层进程 watchdog 兜底，并单独核查是否侵占 600 秒 finalization reserve。

## 14. 禁止扩张

- 不复制或继承覆盖 InquiryCraft TUI 私有实现；
- 不拆 AgentSurface，除非 interceptor 事实证明无法满足交互；
- 不创建第二套 TaskSpec/RunPlan；
- 不创建新的 LaunchService package；
- 不创建新的 Evaluator/Gate/Resource Runtime；
- 不让 Textual widget 决定 GPU、worker 或 Gate；
- 不生成每任务一个 Python Gate 类；
- 不创建五个空壳 screen 只为目录对称；
- 不删除现有 CLI、Monitor 或 Resume；
- 不把 `/long-research` 加入 InquiryCraft 领域；
- 不在首版引入 daemon、远程 worker transport 或新的进程 supervisor。

## 15. 实施记录

本轮已闭环到公共 `run_manifest()`，未引入计划禁止的平行框架：

1. InquiryCraft `0.8.1` 增加最小 interceptor/host port，普通 TUI 行为保持不变；
2. Light 默认依赖包含 `inquirycraft[openai,tui]`，根级 `scienceflow tui` 已可启动；
3. `/long-research` 从 detached conversation 提炼任务，只问缺失信息；
4. 注册任务复用 TaskPackage，陌生任务显式保持 exploratory；
5. GPU probe、资源字段解析、Parallel loader、Evaluator smoke 和 Gate fail-closed 均进入 preflight；
6. TUI 与 CLI 共同调用 `runtime/parallel/service.py::run_manifest()`；
7. onboarding 按状态机、答案解析、manifest、preflight、Gate probe 和 TaskPackage defaults 分层，
   每个业务目录仍满足最多五个直接模块的结构门禁。

当前确定性验证：InquiryCraft `237 passed, 1 skipped`；ScienceFlow `1914 passed, 3 skipped`；
本地构建两个 wheel 后，在全新 Python 3.12 venv 中成功安装 Light，确认 InquiryCraft `0.8.1`、
Textual、`scienceflow --help`、`scienceflow tui --help` 和陌生 fixture onboarding/preflight。Light wheel
同时直接携带现有 `tasks/` 单一来源，避免 PyPI 安装后丢失已登记 TaskPackage；不复制任务实现。

代码提交 `f8230d6` 上的 `bench_sf audit` 为 16/16；CPU `bench_sf release` 为 14/14
`passed / 100`。打包提交 `74b919d` 另以 clean wheel 安装验证了 91 个 TaskPackage 和
Circle/Nomad/TFBind8 登记任务可发现性。两个物理
GPU point 因 vLLM 正占用 GPU 按默认策略跳过，沿用其既有双次稳定实测证据，不抢占外部进程。

发布顺序必须是先发布 InquiryCraft `0.8.1`，再刷新 ScienceFlow `uv.lock` 并发布 ScienceFlow；
在 `0.8.1` 尚未进入公开 PyPI 前，不把旧 `uv.lock` 的 `0.8.0` 记录伪装成已完成发布锁。

## 16. 发布候选验收记录

### 16.1 验证基线与环境

- 轻量 TUI/onboarding 代码：ScienceFlow `f8230d6`，InquiryCraft `e3bb8ba`；
- TaskPackage wheel 收口：ScienceFlow `74b919d`；
- 三个从零长程任务的固定运行基线：ScienceFlow `5c9b34b`；它验证现有 LNR/Parallel
  底层，新 TUI 薄适配层由同版合同测试、clean wheel 和 `bench_sf` 分别验证；
- provider：`Qwen3.5-9B-sf-ttt` vLLM，context 65,536，首位 system message 合并已开启；
- Circle/Nomad/TFBind8 任务 CPU pool 分别为 `0-15` / `16-31` / `32-47`，均为
  `gpu_list: cpu`、`num_workers: 2`、`wall_clock_budget_sec: 7200`；与之同时的
  `bench_sf` CPU 验证固定在 `64-95`。

### 16.2 三任务结果

| 任务 | framework_result | model_result | scientific_effect_result |
| --- | --- | --- | --- |
| Circle | `success`，6021s；2 workers 产生 5 个合法 Stage，收集 5 个全局候选；merge agent 被 repetition guard 中止后，fallback 仍生成并重评 3 个 final，资源清零 | W00 正常收口；W01 在已提交 4 个合法 Stage 后触发 vLLM context 400 | 3 个 final 均通过 evaluator/Gate，`radii_sum` 为 `2.456714` / `2.444345` / `2.418557` |
| Nomad | `failed`，1789s；无合法 Stage 时 fail-closed，未伪造 final，资源清零 | W00 以 `text_only_stop_no_candidate` 结束；W01 的 prompt 32,769 + 请求输出 32,768 达 65,537，超过 vLLM 65,536 后返回 400 | 未形成可评 artifact；无候选属于本次模型表现，context 400 则是 provider 与请求预算未协调的集成缺口 |
| TFBind8 | launcher `failed`，3981s；worker 失败后仍发现 4 个合法 Stage，`partial_merge_available=true`、`finalization_ready=true`，best-stage finalization 成功；整体未误报成功，资源清零 | W01 首个无效候选被 Gate 拒绝；ESTRA 曾 compact 1 次，但两 worker 最终仍遇到同一 context 400 | 权威 final `best_k_mean=0.963221`、regret `0.0356925`、global NDCG `0.855295`，仅用 1/10 query |

结论：按本轮“只看逻辑，不要因本地小模型重跑全量”的验收口径，三任务已提供足够的
Stage、Gate、partial failure、global merge、best-stage finalization、CPU 隔离和 cleanup 实测证据。
Nomad/TFBind8 launcher 的非零退出不应被改写为成功。它们不是轻量 TUI 的回归，
但暴露了现有 LNR/provider 的 context 预算集成缺口，与小模型无候选的科学表现分开记录。

### 16.3 资源策略观察

Circle W01 的两个重 CPU command 均使用动态 timeout，且由任务代码自然退出，未越界使用其他
CPU pool。第二个 command 在距 deadline 约 898 秒时触发 finalization reserve guard，但当前
`kill_authority=review_only` 将 `OBSERVE_MORE` 归一为 `NO_ACTION`；command 约 36 秒后自然结束，
本次未造成超时且最终 merge 成功。因此：

- 本次运行结果上，CPU 隔离、命令生命周期和最终 cleanup 通过；
- finalization reserve 不判通过：review-only 模式下它是建议性而非强制截止，warmup/
  observe-more 可覆盖 reserve；后续 `bench_sf` 资源 point 应验证强制终止，或将 observe
  window 严格截断到 deadline；
- Circle W01 重试 S01 时，`assessment:S01:{detect,archive,assess}` 的 lifecycle `event_id`
  各重复一次且 `duplicate=false`。它不影响本次产物，但会污染事件幂等审计，需作为长程
  runtime 后续修复项；
- context 预算需要在发送前保证 `prompt_tokens + requested_output_tokens <= provider_limit`；
  ESTRA compact 只能作为恢复路径，不能代替请求边界预检。

### 16.4 证据入口

- 三任务 launcher：`.artifacts/product_2h_acceptance_20260903_r1/{circle,nomad,tfbind8}.launch.log`；
- 三任务 workspace：`workspaces/product_2h_acceptance_20260903_r1/`；
- Circle：`merge/worker_results.json`、`merge/stage_collection_report.md`、`merge/merge_report.md`、
  `merge/finals/*/eval_result.json`；
- TFBind8：`merge/worker_results.json`、`merge/best_stage_manifest.json`、
  `merge/finals/final_00/.run_results.md`；
- bench：`../bench_sf/reports/*-20260902T1702*.json`（实际仓库为 ScienceFlow 同级的 `bench_sf`）。
