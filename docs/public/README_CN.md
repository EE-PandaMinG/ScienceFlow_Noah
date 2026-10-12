<h1 align="center">ScienceFlow</h1>

<p align="center"><b>端到端自动研究 Agent 框架</b></p>

<p align="center">
  <a href="https://www.noahlab.com.hk/news/212"><b>项目报道</b></a>
  ·
  <a href="https://arxiv.org/abs/2608.14354"><b>arXiv 论文</b></a>
  ·
  <a href="../../README.md"><b>English</b></a>
</p>

> [!IMPORTANT]
> **测试预览版。** 当前代码线用于生成公开的 `preview` 分支，面向功能体验、集成测试和演示，
> 已包含 TUI 对话、多任务长程研究、续跑与恢复、资源协调和结构化遥测。稳定版发布前，接口、
> 配置结构、界面细节和工作区元数据仍可能调整。请使用仓库锁文件和独立工作区进行测试，
> 暂不建议用于无人值守的生产任务。

ScienceFlow 是一个端到端自动研究 Agent 框架，面向持续数小时或数天的高效、稳定且目标一致的研究过程。它以可恢复的可执行工作空间为核心，将持久状态、自适应探索与证据感知执行控制统一起来，使 Agent 能够在保留已验证进展的同时继续、调整或恢复研究路线。

ScienceFlow 文档使用 **iqcraft** 作为 InquiryCraft 的简称；Python 包、import 与 CLI 示例仍统一使用
正式名称 `inquirycraft`。

ScienceFlow 在机器学习、科学建模和数学优化任务上持续开展长程研究，并在完整 75 题 MLE-bench 上于 24 小时预算内达到 **70.22 ± 1.18% Any-Medal**，超过已报告最强基线 **4.92 个百分点**。

<p align="center">
  <img src="scienceflow/assets/mlebench_top10_any_medal.png" alt="完整 MLE-bench Any-Medal 排行榜" width="100%">
</p>
<p align="center"><sub><b>图 1a：完整 MLE-bench Any-Medal 排行榜。</b> ScienceFlow 结果为三次独立运行的均值 ± SEM。</sub></p>

## 快速开始

**前置要求：** Python 3.11+ 和可用的模型 API。当前 PyPI 包是测试预览版，下面固定
具体版本，避免测试环境随后续 Preview 改变。

### 安装

推荐使用 [`pipx`](https://pipx.pypa.io/latest/how-to/install-pipx.html) 安装。ScienceFlow 的
Python 依赖会保持隔离，同时 `scienceflow` 命令可以在任意目录直接使用：

```bash
pipx install scienceflow==0.2.0b7
scienceflow --help
```

<details>
<summary><strong>其他安装方式</strong></summary>

**Conda**

```bash
conda create -n scienceflow python=3.12 -y
conda activate scienceflow
python -m pip install scienceflow==0.2.0b7
```

**uv**

```bash
uv tool install scienceflow==0.2.0b7
```

**Python 虚拟环境**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install scienceflow==0.2.0b7
```

</details>

### 配置并启动

首次使用时创建模型注册表，编辑生成的文件，然后启动 TUI：

```bash
scienceflow config init
scienceflow config path
scienceflow tui --workspace "$PWD/sf_workspace"
```

默认配置位于 `~/.config/scienceflow/models.json`，权限为 `600`；API Key 不会复制到
manifest、session 或报告中。详细字段见[模型配置说明](LLM_CONFIGURATION.md)，也可参考
[脱敏的多端点配置示例](../examples/models.example.json)。工作区和恢复选项可运行
`scienceflow tui --help` 查看。进入 TUI 后，使用 `/long-research` 准备并启动托管研究任务。

聊天和任务列表保留在启动工作区；单个任务可指定另一处**本机**执行根目录：

```bash
scienceflow run circle-packing --workspace "$PWD/sf_workspace" --execution-root /data/experiments
```

TUI 中输入 `/long-research circle-packing workspace=/data/experiments`，也可用自然语言
说明执行目录。显式参数不调用模型解析目录；自然语言先进行禁用工具的位置提取，再分配目录。
每次指定根目录都会创建独立任务子目录，不覆盖已有实验，不复制数据集。相对执行根目录、
相对数据路径均以管理工作区解释；不配置时保留现有默认目录布局。
`--execution-root` 不可与 `--manifest` 混用。准备后要换位置，请 `/cancel` 后重新发起任务；
恢复始终使用原目录。准备工具使用独立任务目录，shell 默认可用；普通聊天的目录和
session 不变。本阶段不支持 SSH；宿主接口由锁定的 InquiryCraft 0.9.2 提供。

## 最新动态

- **[2026-09]** 测试预览版已发布至 `preview` 分支，用于集成测试与反馈。
- **[2026-08]** ScienceFlow 正式开源——框架代码、任务包与文档均已发布在本仓库。
- **[2026-08]** ScienceFlow 论文已上线 [arXiv](https://arxiv.org/abs/2608.14354)。

## 核心概念

1. **可恢复的可执行状态。** 每个持续运行的 LNR worker 在隔离的可执行工作空间中推进研究；归档状态将工作空间与紧凑记忆、验证证据和资源记录绑定在一起。
2. **Stage Gate。** 任务特定的结果信号触发 `GateService`：配置的 Evaluator 生成标准化证据，Gate policy 决定是否准入。通过准入的结果被物化为不可变 Stage，并记录 ledger facts 和可恢复工作空间快照。
3. **ESTRA。** 在研究边界，Executable-State Transition through Re-Anchoring 做一次两轴决策：起点（当前工作区或已归档 Stage）与意图（`continue` 继续或 `redirect` 重定向）。选择归档起点时，系统会在下一研究分段开始前恢复对应的可执行状态。
4. **持久记忆。** Add 记录通过准入的 Stage 进展；Fold 保留 recent、best-validated 和 anchor-relevant 证据，并压缩旧记录；Unfold/restore 检索带索引的证据与状态，Assemble 为下一分段构造与锚点对应的上下文。
5. **证据感知执行控制。** 研究 worker 决定科学路线，控制器依据资源可用性、剩余预算、已验证进展和可恢复性，对物理任务进行准入、资源租约、在线监控、限时与停止；有效 worker 状态最终归档到 `merge/finals/final_*`。

## 系统架构

<p align="center">
  <img src="scienceflow/assets/scienceflow_system_architecture.png" alt="ScienceFlow 系统架构" width="100%">
</p>
<p align="center"><sub><b>图 2：ScienceFlow 系统架构。</b> Research worker 基于可恢复的可执行状态推进研究，通过边界触发的 ESTRA 调整长程轨迹；证据感知执行控制负责协调物理资源分配与任务执行。</sub></p>

## 源码开发

参与源码开发时，从审核过的锁文件创建环境：

```bash
cd ScienceFlow
uv sync --python 3.12 --group dev
uv run scienceflow config init
uv run scienceflow tui --workspace "$PWD/sf_workspace"
```

默认命令安装 Light 开发环境。只有需要 ML、GPU、MLE-bench 和 scientific-design 依赖时，
才使用 `uv sync --extra full --group dev`。发布包的 Full profile 应在虚拟环境内安装：

```bash
python -m pip install "scienceflow[full]"==0.2.0b7
```

ScienceFlow 在进程内使用 InquiryCraft `0.9.2` 作为通用 Agent Runtime，不需要另起服务。
源码环境与 PyPI 安装使用相同的 CLI 和用户私有模型注册表。

## 文档

[文档索引](../README.md) · [架构总览](scienceflow/index.html) · [可恢复状态与 LNR](scienceflow/module-lnr.html) · [证据感知执行控制](scienceflow/module-resource.html) · [新增优化任务](scienceflow/module-opt-solver-onboarding.html) · [当前规划](../plans/current/) · [SciModelingBench](../../tasks/sci_modeling_bench/README.md)

机器学习工程、科学建模和数学优化任务共享同一套 Stage Gate 与 Evaluator contract。
配置字段、仓库职责边界、任务 contract 和 Benchmark 细节统一放在上述文档中，不在 README
重复展开。

## 运行注意

- MLE-bench 任务需要数据根、任务 `exp_id`、`submission.csv` contract 对齐。
- 不同任务 profile 的旧 workspace 不应混用 resume，否则可能继承错误 prompt、dataset 或 artifact 维度。
- CLI 与 TUI 的启动、恢复统一执行 CPU/GPU 资源预留检查。使用 `--manifest` 时，worker、时间、CPU/GPU、数据和配置在 manifest 中设置，混用对应 CLI 参数会明确报错。
- TUI 通过轻量注册表变更感知其他终端的启动和恢复，不重新扫描已结束实验目录。
- `stopped_by_user` 表示人为停止的可恢复终态，不等价于失败；后续 resume 应从 `state.json` 的累计预算和 workspace stage 继续。
- TUI 底部资源栏显示本机资源概况；任务卡和 `/status N` 展示任务及 worker 的资源与用量。
- `scienceflow tui --resume` 恢复本工作区聊天会话及简短研究事件；TUI 内 `/resume N` 恢复编号为 N 的研究任务。`/status` 等查询只即时显示，不写入研究事件历史。
- 普通聊天只在当前模型请求中读取任务面板的简短状态摘要，不把这份摘要写入聊天记录或影响研究 worker。

## 验证

```bash
.venv/bin/pytest -q \
  tests/test_inquirycraft_dependency_boundary.py \
  tests/test_inquirycraft_cli_composition.py \
  tests/test_long_research_interaction.py
```

发布 workflow 仅接受与项目版本一致的 tag；它会构建并检查 wheel 与源码包，在干净环境中
安装 wheel，运行公共依赖契约，再通过 PyPI Trusted Publishing 上传。完整回归命令为
`uv run --locked pytest -q`。ML、GPU、MLE-bench 与 scientific-design 测试需要对应的可选依赖。

TUI 聊天和任务准备默认可执行 shell（当前用户权限，无操作系统沙箱），无默认超时。
Esc 取消当前聊天，退出 TUI 回收前台命令及子进程；长程 worker 的执行控制保持独立。

### 任务收尾与报告

研究结束、失败或停止后，托管任务会进入独立的报告阶段，默认预算 300 秒，
不占研究预算；提前完成即结束。manifest 顶层 `report_budget_sec` 可设置该预算。
报告先生成本地证据版，再在剩余预算内补充模型分析。任务目录包含
`report.md`、`report.html`、`report.json` 和 `report_assets/`，各次运行归档位于
`task_logs/reports/attempt-NNN/`。Web 打开 HTML 后可通过浏览器打印保存 PDF，
不安装服务端 PDF 引擎。

报告生成失败时，对已结束的研究执行原有 `resume` 只重试报告，不重新探索、
不占用研究 CPU/GPU 配额；仍有研究预算的暂停任务继续原有恢复流程。报告发布使用
原子版本切换，中断时保留上一个完整版本；历史版本暂不自动清理。
