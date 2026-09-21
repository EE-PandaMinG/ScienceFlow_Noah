# DeepCraft 结构整理与真实任务验证（2026-08-23）

## 整理结果

本阶段只做工程结构迁移，不改变 ScienceFlow 的 Prompt、Tool Schema、调用时机、
Stage/Gate/Evaluator、worker 合并逻辑或既有 workspace 文件格式。

- 正式底座统一为 `runtime/`、`llm/`、`tools/`、`memory/`、`events/`、`cli/`。
- LLM loop、Hooks、Cancellation、Resume 收口到 `runtime/`；录制/回放收口到
  `events/replay.py`。
- ScienceFlow 仍依赖的旧版 factory、failover pool、memory mutation/record 和 adapter
  收口到 `legacy/`。
- 历史 `deepcraft_core`、`deepcraft_agent`、`deepcraft_tool_ext` 三个独立 distribution
  收口到 `legacy_packages/`，包名和实现未变。
- `compat/` 与旧平铺导入路径只保留 re-export shim；合同测试验证旧对象与规范对象
  identity 相同。
- 安装 extra 规范名改为 `deepcraft[legacy]`；`deepcraft[scienceflow]` 保留为弃用别名。
  MCP 仍为显式 extra，未进入默认 ScienceFlow 环境。
- DeepCraft 测试拆分为 `unit/`、`integration/`、`legacy/`、`contract/`，明确独立演进
  和兼容门禁的责任边界。

详细边界见 `deepcraft/ARCHITECTURE.md`。

## 工程门禁

| 门禁 | 结果 | 耗时 |
|---|---:|---:|
| DeepCraft 全套 | 64 passed | 1.37 s |
| ScienceFlow 迁移相关定向门禁 | 149 passed | 5.91 s |
| ScienceFlow 完整离线矩阵 | 1672 passed, 3 skipped | 167.36 s |

完整矩阵只有既有的两条配置弃用 warning，无新增 warning。`uv lock --check` 和
`git diff --check` 通过。

## ScienceFlow 真实任务

任务为 Circle Packing、seed 5555、worker=1、本地 vLLM `Qwen3.6-27B`。为减少验证
耗时，采用短预算首次运行并沿同一 workspace 续跑，而不是重新执行 900 秒性能门禁。

- 首次运行：221 s，4 次主 LLM 调用，9 次工具调用，正常退出；完整生成
  `resolved_config.yaml`、LHR、interaction、merge、resource 和
  `.agent_memory/ScienceAgent/{short_term.json,long_term.jsonl}`。
- 续跑复用同一 Memory，执行已生成的 `solution.py` 并提交 S01 stage。
- 最终 artifact 包含 26 个圆；官方 evaluator 结果：

```json
{"benchmark_ratio":0.8058949400996297,"container":"unit_square","metric":{"name":"radii_sum","value":2.123533167162524},"num_circles":26,"radii_sum":2.123533167162524,"valid":true}
```

首次运行和续跑 manifest：

- `scripts/deepcraft_organization_sf_smoke_20260823.yaml`
- `scripts/deepcraft_organization_sf_smoke_resume_20260823.yaml`

本地 workspace（Git ignore）：

`workspaces/deepcraft_organization_sf_smoke_20260823/deepcraft-organization-seed5555/circle-packing`

续跑外层状态为 `budget_done`，因为 manifest 的 300 秒总任务预算包含首次已消费的
221 秒；artifact、S01 snapshot 和 evaluator 输入在剩余 79 秒内已完成。该状态属于
预期预算截止，不是运行错误。

## DeepCraft CLI 真实交互

独立运行 `deepcraft repl`，不经过 ScienceFlow：

1. 第一轮由模型调用 `write_text`，写入无尾换行的
   `deepcraft-cli-confirmed-20260823`。
2. 第二轮由模型调用 `read_text`，回复完全相同的内容。
3. `events.jsonl` 共 34 条事件，其中 `tool.completed` 顺序严格为
   `write_text -> read_text`；`session.jsonl` 共 9 条 append-only conversation 记录。

本地 workspace（Git ignore）：`workspaces/deepcraft_cli_interactive_20260823`。

## 后续门禁策略

日常纯工程迁移只跑 DeepCraft 快速套件和受影响的 ScienceFlow 定向套件；每个结构
阶段完成时跑一次完整离线矩阵。真实 LLM 任务只在行为边界或 release checkpoint
运行，避免每次机械移动都重复消耗数分钟。
