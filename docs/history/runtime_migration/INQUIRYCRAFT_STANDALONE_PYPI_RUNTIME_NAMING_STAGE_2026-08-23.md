# InquiryCraft 独立品牌、PyPI 与通用 Runtime 命名阶段记录（2026-08-23）

## 1. 目标与边界

本阶段完成三项纯工程迁移：

1. 将原运行时仓库的完整 Git 历史同步到 `EE-PandaMinG/InquiryCraft`；
2. 将 InquiryCraft 的 distribution、Python namespace 和 CLI 统一为 `inquirycraft`，并将公开描述改为独立 Agent Runtime；
3. 将 ScienceFlow 内部的品牌化事件和 backend 名称改为通用 runtime 名称。

迁移不得改变 ScienceFlow 的 provider-visible context、消息顺序、工具 schema、工具调用机制、错误文本和 workspace 业务文件。旧品牌配置入口按最新决策直接删除，不再提供 alias。

## 2. Git 历史同步

- 新仓初始化提交与原仓历史通过 unrelated-history merge 合并，双方提交均保留；
- 原仓全部历史标签已经同步到新仓；
- 新仓 `origin` 为 `git@github.com:EE-PandaMinG/InquiryCraft.git`；
- 旧仓 URL 仅作为本地 `deepcraft-origin` 远端留存，不再作为发布源；
- 当前 InquiryCraft `main` 为 `88de227c0cb1630570b0b7782e61dd2032053805`，提交图共 56 个提交；
- `v0.6.0` 尚未创建，避免在 PyPI Trusted Publisher 配置完成前触发失败发布。

## 3. InquiryCraft 独立化

### 3.1 统一名称

- distribution：`inquirycraft`；
- import：`inquirycraft`；
- CLI：`inquirycraft`；
- 版本候选：`0.6.0`；
- minimal dependency：仅 `click`；
- `openai`、`tokens`、`mcp`、`dev` 保持 optional extras。

旧 `deepcraft` package、CLI、环境变量和 distribution 入口均不再提供。

### 3.2 独立描述

InquiryCraft 的 README、Architecture、PyPI summary、源码 docstring、测试说明和 CI 不再以 ScienceFlow 解释项目职责。公开描述只覆盖通用 agent loop、LLM protocol、Tool、Memory、Event、Replay、Resume、Executor、MCP 和 CLI。

构建产物 `inquirycraft-0.6.0-py3-none-any.whl` 共 102 个条目，不包含 ScienceFlow 或旧品牌 package path。`twine check` 对 wheel 和 sdist 均通过。

### 3.3 PyPI 发布准备

release workflow 已拆为：

1. build/test/tag-version gate；
2. GitHub Release；
3. 使用 `pypa/gh-action-pypi-publish` 和 OIDC 的 PyPI publish job。

PyPI job 使用受保护的 `pypi` environment 和 job-level `id-token: write`。后续仍在私有 Git 仓迭代，只把明确的 release tag 构建产物发布到公开 PyPI。

发布前仍需在 PyPI 创建 pending Trusted Publisher：

- Owner：`EE-PandaMinG`；
- Repository：`InquiryCraft`；
- Workflow：`release.yml`；
- Environment：`pypi`；
- Project：`inquirycraft`。

完成该外部配置后再创建并推送 `v0.6.0`。

## 4. 版权信息清理

经用户确认授权，InquiryCraft 当前工作树的 MIT 版权主体已统一为
`InquiryCraft Contributors`，相关源码和测试文件统一使用
`SPDX-License-Identifier: MIT`。源码、测试、元数据、wheel 和 sdist 对旧企业归属文本的扫描均为 0 命中。

为满足此前“历史提交不可丢失”的要求，本次只清理当前版本和发布制品，不改写既有 Git commit 历史。

## 5. ScienceFlow 通用 Runtime 命名

- 默认 backend token：`runtime`；
- 允许的 backend：`runtime`、`legacy`；
- 运行事件模块：`scienceflow.core.runtime_events`；
- 启用变量：`SCIENCEFLOW_RUNTIME_EVENTS`；
- 显式路径变量：`SCIENCEFLOW_RUNTIME_EVENT_LOG`；
- 默认事件文件：`agent_runtime_events.jsonl`。

旧 `deepcraft` / `inquirycraft` backend alias、`SCIENCEFLOW_DEEPCRAFT_*` 变量和 `deepcraft_events.jsonl` 默认写入逻辑已删除。已有实验 YAML 的 `runtime_backend` 值统一改为 `runtime`。

ScienceFlow 暂时固定 InquiryCraft 新仓的 `v0.5.0` Git tag；待 `inquirycraft==0.6.0` 首次发布到 PyPI 后，再以独立提交切换为 PyPI 精确版本，避免引用未发布 tag 或漂移的 `main`。

## 6. 验证结果

### InquiryCraft

- unit/integration/contract：`149 passed`；
- Ruff lint：通过；
- Ruff format check：通过；
- `uv lock --check`：通过；
- wheel/sdist：构建通过；
- `twine check`：两个制品均通过；
- wheel metadata：`Name: inquirycraft`、`Version: 0.6.0`。

### ScienceFlow

- 受影响契约测试：`23 passed`；
- Tool Runtime frozen contract：schema/context/mechanism/error/workspace 全部 0 diff；
- Full Runtime Parity：4 jobs 并行，context/mechanism/workspace 全部 0 diff；
- 全量离线测试：`1682 passed, 3 skipped, 2 known warnings`。

因此，当前通用命名迁移没有改变已冻结的科学运行上下文、执行机制或 workspace 效果。

## 7. 后续动作

1. 用户在 PyPI 配置 `inquirycraft` pending Trusted Publisher；
2. 创建并推送 InquiryCraft `v0.6.0`，观察 PyPI 与 GitHub Release job；
3. 验证 `pip install 'inquirycraft[openai]==0.6.0'` 的隔离环境；
4. ScienceFlow 改用 `inquirycraft[openai]==0.6.0`，刷新 `uv.lock`；
5. 再运行受影响测试与并行 frozen benchmark 后提交 ScienceFlow 切换。
