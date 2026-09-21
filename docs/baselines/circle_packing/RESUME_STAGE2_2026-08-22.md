# DeepCraft Resume 迁移切片与 Circle Packing 对比记录

日期：2026-08-22

## 结论

本阶段完成了通用 Resume 判定与执行能力从 ScienceFlow 向 DeepCraft 的迁移切片，但没有切换 ScienceFlow 的完整默认 Runtime，也没有删除兼容层。

- 严格 replay、旧 Workspace 读取、功能测试和性能门禁通过。
- Circle Packing 新任务与旧 Workspace 续跑均完成了三 seed、Worker=2 的并行对比。
- 真实续跑中 DeepCraft Resume 侧有效 final 为 3/3，Legacy Resume 侧为 2/3，候选侧两个可配对 seed 的续跑耗时均下降。
- 预注册的严格三 seed 效果门禁仍为失败：Legacy seed 4444 没有有效 final，且 seed 3333 候选分数回退约 1.4%。

因此，本切片可以作为已验证的兼容实现保留，但不满足“切换默认 Runtime/删除旧实现”的条件。

## 代码范围

基线提交为 `de31705`，候选实现由以下提交组成：

- `0476141`：新增 `deepcraft.resume`，为 `AgentRuntime` 增加 `resume()`，扩展严格 Replay，并将 ScienceFlow 的 `memory_state` 改为兼容 facade。
- `1abcf1a`：优化 legacy dict/attribute 消息检查热路径，保持历史检查成本。

DeepCraft 新增的通用能力包括：

- 对空会话、完整 assistant/user/tool 尾部、单个未完成 Tool Call 和不安全的多个未完成 Tool Call 进行领域无关分类。
- 从 `JsonlConversationStore` 恢复会话，避免重复写入 task/system message。
- 中断发生在单个 Tool Call 后时，恢复后只执行一次未完成 Tool，再进入下一次 LLM 请求。
- 多个未完成 Tool Call 不做隐式猜测，明确拒绝不安全恢复。
- `ReplayLLMClient` 支持从指定 sequence 开始，且请求不匹配时不消耗记录。

ScienceFlow 仍保留原有公开 import 路径、事件格式和 Workspace 文件格式；本阶段没有迁移 Stage、Gate、Evaluator、ESTRA、Merge 或主 RunLoop。

## 自动化门禁

### 功能与兼容性

- Resume/Replay 聚焦测试：`21 passed`。
- 相关门禁组合：`46 passed`。
- 最终相关测试矩阵：`1678 passed, 2 skipped, 2 warnings`，耗时 `159.92s`。
- `tests/test_sci_modeling_bench.py` 因当前环境未安装 `scientific-design` optional extra 而不在本次矩阵中；不能将其记为已验证。

新增的严格验证覆盖：

- 中断后恢复与不中断运行产生相同的 Conversation、Tool Result 和 Workspace 文件。
- 旧版 `short_term.json`、`long_term.jsonl` fixture 可以直接加载，加载过程不改写任何字节。
- 从持久化 store 恢复时不重复 user task。
- ScienceFlow 原公开 Resume 符号和 import 路径保持可用。

### Resume 检查微基准

同一 legacy 消息输入执行 100,000 次、重复 9 轮：

| 实现 | 中位耗时 |
| --- | ---: |
| Legacy | 0.312155 s |
| DeepCraft | 0.302972 s |

DeepCraft 中位耗时下降约 2.94%，约减少 0.092 微秒/调用。本切片没有引入 Resume 检查性能回退。

## Circle Packing 实验设计

- 模型服务：同一 vLLM 进程，`Qwen3.6-27B`，OpenAI-compatible endpoint `http://127.0.0.1:8001/v1`。
- seed：`2222`、`3333`、`4444`。
- 每个任务 `num_workers: 2`，每侧同时运行三个 seed；两侧并行执行。
- 新任务预算：LNR 900 秒，task 1200 秒。
- 续跑预算：每个已有 Workspace 新增 300 秒 LNR segment，task 600 秒。
- 基线使用 detached worktree 的 `de31705`；候选使用当前 DeepCraft Resume 实现。
- 基线 CPU 为 `0-47`，候选 CPU 为 `56-103`，避免 CPU 集合重叠。
- 六个新任务的首条 user message 在配对 seed/worker 间逐字节一致；长度分别为 5281、5282 bytes。
- 归一化 task workspace、input path 和 config source path 后，三组 `resolved_config.yaml` 均逐字节一致。

实验入口保存在：

- `scripts/circle_packing_3seed_resume_stage2_baseline_20260822.yaml`
- `scripts/circle_packing_3seed_resume_stage2_candidate_20260822.yaml`
- `scripts/circle_packing_3seed_resume_stage2_continuation_baseline_20260822.yaml`
- `scripts/circle_packing_3seed_resume_stage2_continuation_candidate_20260822.yaml`

## 新任务对比

六个任务进程均正常退出，但两侧 seed 2222、4444 都因 `budget_expired` 没有产生可参与门禁的 Stage/final。只有 seed 3333 可配对：

| seed | Legacy 分数 | Candidate 分数 | 分数变化 | Legacy 耗时 | Candidate 耗时 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 3333 | 2.413939 | 2.380138 | -0.033801 (-1.4%) | 973.3 s | 986.7 s |

此结果不能构成有效的三 seed 对比。报告 `resume_stage2_effect_gate_report_20260822.json` 正确记录为 `passed: false`。新任务路径没有加载既有 Memory，因此没有调用本阶段新增的 Resume 路径；两侧相同的 2/3 no-final 率不能归因于 Resume 迁移。

## 旧 Workspace 续跑对比

续跑复用上述六个 Workspace。配置中的 `resume: false` 仅用于关闭 ParallelRunner 对“已完成任务”的跳过；LNR 检测 `.agent_memory` 后仍进入各自的 Resume 实现。

12 个 worker 均写入 `lhr_resume_events.jsonl`，事件均为：

- `action=continue_llm`
- `reason=last_assistant_message_complete`
- `executed_tool=false`

六个续跑任务均正常退出。有效 final 与本段耗时如下：

| seed | Legacy final | Candidate final | Legacy 本段耗时 | Candidate 本段耗时 | 结果 |
| ---: | ---: | ---: | ---: | ---: | --- |
| 2222 | 1.820000 | 2.166023 | 518.8 s | 424.1 s | 分数 +0.346023，耗时 -18.3% |
| 3333 | 2.413939 | 2.380138 | 478.0 s | 251.4 s | 分数 -1.4%，耗时 -47.4% |
| 4444 | 无有效 final | 2.491700 | 214.5 s | 486.1 s | 无法配对 |

候选侧 final 成功率为 3/3，Legacy 为 2/3。所有生成的 final artifact 又通过任务自带 evaluator 独立复评，7 个 artifact 均验证成功且分数一致。

报告 `resume_stage2_continuation_effect_gate_report_20260822.json` 仍正确记录为 `passed: false`，原因是：

1. Legacy seed 4444 缺少可配对有效结果。
2. seed 3333 要求逐 seed 不回退，而候选分数下降约 1.4%。

## Workspace 契约检查

- 没有发现候选侧缺失历史要求的路径。
- seed 2222 兼容检查通过：检查 194 项，missing 0，mismatch 0，候选新增 7 项。
- seed 3333：检查 204 项，missing 0，mismatch 1，新增 9 项；差异仅来自两侧 worker 的 `lhr_resume_events.jsonl` 内容变体。
- seed 4444：检查 115 项，missing 0，mismatch 2，新增 81 项；差异来自 Legacy 无 final 而候选产生了 `global_candidates.jsonl` 和 evidence 内容。

这些差异是不同 Agent 轨迹和结果成功率造成的内容差异，不是 Workspace 路径或 Memory schema 被删除。比较器没有为了得到“通过”而放宽规则。旧 fixture 的字节保持测试是旧 Memory 文件兼容性的确定性证据。

## 阶段判定与下一步

本阶段判定：Resume 迁移切片的确定性功能、旧数据兼容和本地性能门禁通过；真实任务的严格效果门禁未通过。

在再次满足三 seed 严格门禁前：

- 不切换完整 ScienceFlow 默认 Runtime。
- 不删除 Legacy Resume facade 或旧 RunLoop。
- 不声称 ScienceFlow 全部迁移已经完成。

下一轮应使用相同配置重跑独立三 seed Resume 对比，优先降低并发调度/服务竞争带来的轨迹噪声，并补充至少一个代表性非 Circle Packing 任务和 `scientific-design` extra 的完整测试矩阵。
