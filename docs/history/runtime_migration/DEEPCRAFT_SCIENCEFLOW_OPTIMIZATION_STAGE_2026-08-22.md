# DeepCraft / ScienceFlow 优化阶段记录（2026-08-22）

## 阶段结论

本阶段已经建立可独立使用的轻量 DeepCraft Agent Runtime 基础，并在不切换 ScienceFlow 默认 legacy 等价执行路径的前提下完成兼容性建设。Circle Packing 三 seed、`worker=2` 的真实任务配对门禁已经通过；现有 ScienceFlow 的任务效果、配置语义和 Workspace 外部文件契约在该门禁范围内未发生退化。

本阶段是可回退的迁移检查点，不代表两个项目已经完成物理拆仓，也不授权删除 legacy Runtime。后续迁移仍按“小切片、先门禁、后切换”的原则推进。

## Git 与对比边界

- 重构前基线：`46e3c61`。
- 对齐调查前检查点：`d24542b`，标签 `pre-circle-packing-alignment-investigation-20260822`。
- 三 seed 门禁实现与对齐：`f76f1f5`、`7872bcb`。
- 三 seed 验证证据：`4d89c07`。
- Baseline 验证 worktree 在 `46e3c61` 上只回移相同门禁基础设施；验证 HEAD 为 `a826385`，没有回移 Runtime 优化。

本文件所在提交和对应阶段标签用于开始下一规划任务前的恢复点。

## 本阶段完成内容

### 1. DeepCraft 最小底座

- 建立领域无关的 Agent Runtime、LLM、Tool、Memory、Event 和基础 CLI 公共接口。
- CLI 可由 DeepCraft 独立使用，也提供 ScienceFlow 可复用的扩展入口。
- DeepCraft 新公共层不依赖 ScienceFlow；ScienceFlow 专属 Stage、Gate、Evaluator、ESTRA、资源控制和多 Worker 策略仍留在 ScienceFlow。
- 默认依赖完成轻量化；MCP 作为 optional extra 保留。Browser、向量检索和 LiteLLM 不进入新 Runtime 的受支持默认能力。

### 2. 兼容迁移基础

- ScienceFlow 通过公开 facade 保持 legacy 等价路径，尚未强制切换默认 Runtime。
- 建立通用 JSONL Event、恢复和确定性 record/replay 基础能力；现有 ScienceFlow 日志仍是权威外部输出。
- 保留现有 Prompt、Tool schema、模型调用参数、Workspace 布局、日志、Memory、JSON/JSONL、配置和 Resume 数据格式。
- DeepCraft 单元/契约测试、ScienceFlow 测试和跨层兼容门禁已在单仓库内分开。

### 3. Circle Packing 门禁对齐

- 增加显式 opt-in 的 deterministic gate，不改变普通运行默认配置或 schema。
- 对齐 provider seed、Tool Call ID、Prompt/Git 时间、Runtime budget 和向 Agent 展示的逻辑 CPU 上下文。
- 修复项目 `.venv` 中损坏的 `jiter` 二进制缓存后，OpenAI-compatible vLLM smoke test 通过。
- 保存三 seed 实际执行清单：
  - `scripts/circle_packing_3seed_parallel_baseline_20260822.yaml`
  - `scripts/circle_packing_3seed_parallel_optimized_20260822.yaml`

## 验证证据

### 自动化测试

- 相关完整测试：340 passed。
- Workspace / 配置契约：20 passed。
- DeepCraft 独立测试：17 passed。
- CPU 上下文规范化后，当前分支与 Baseline 验证分支的聚焦门禁测试均为 7 passed。

### 三 seed 真实任务

六个任务使用同一个本地 OpenAI-compatible `Qwen3.6-27B` vLLM 并行执行；seed 为 `2222`、`3333`、`4444`，每任务 `worker=2`。Baseline 与优化后的同 seed/worker 首条 user message 均 byte-for-byte 一致。

| Seed | Baseline `radii_sum` | 优化后 `radii_sum` | Baseline 耗时 | 优化后耗时 |
| ---: | ---: | ---: | ---: | ---: |
| 2222 | 2.1106639153 | 2.4784410491 | 987.6 s | 1004.0 s |
| 3333 | 1.8200000000 | 1.8200000000 | 834.3 s | 878.0 s |
| 4444 | 2.0154003333 | 2.0438852729 | 953.5 s | 869.8 s |

- 效果为 2 胜 1 平，无 seed 回退；中位分数提升 1.413%，平均分数提升 6.664%。
- 中位耗时降低 7.918%，平均耗时降低 0.850%；每个 seed 的耗时回归均低于 10% 门限。
- 六个任务均正常完成且 evaluator valid；独立复验分数与 merge 结果一致。
- 自动报告为 `passed: true`、`failures: []`。

详细证据见：

- `docs/baselines/circle_packing/THREE_SEED_GATE_2026-08-22.md`
- `docs/baselines/circle_packing/three_seed_effect_gate_report_20260822.json`

### Workspace 与配置契约

- 三组 `resolved_config.yaml` 在规范化 workspace/input/config-source 绝对路径后完全一致。
- 三个 seed 分别检查 193 个 Baseline 固定路径，missing 和 mismatch 均为 0。
- 优化后允许新增有效产物，但未缺失或改变 Baseline 的路径、文件类型、mode、symlink 或结构化 shape 契约。

## 尚未完成与禁止提前清理的内容

- ScienceFlow 默认调用链尚未切换到新 DeepCraft Runtime。
- 严格 deterministic replay、旧 Workspace Resume、其他代表任务和完整测试/性能矩阵尚未全部通过。
- DeepCraft 与 ScienceFlow 尚未形成独立仓库、独立版本和独立发布流水线。
- legacy Runtime、兼容 facade 和现有 ScienceFlow 权威日志实现暂时不得删除。
- 不得仅依据 Circle Packing 单任务门禁宣称整个迁移完成。

## 下一规划任务的建议入口

下一阶段优先规划并验证以下顺序：

1. 建立严格 replay 与旧 Workspace Resume 双向兼容门禁。
2. 选择至少一个不同类型的代表任务，补齐效果、调用序列、Workspace 和性能门禁。
3. 只迁移一个边界清晰的 Runtime 切片，并保留运行时回退开关。
4. 上述门禁通过后，再规划 ScienceFlow 默认路径切换；物理拆仓和版本发布放在默认路径稳定之后。

每个切片继续执行同一硬条件：ScienceFlow 的具体任务效果、调用行为、性能以及 Workspace 中 log、memory、JSON/JSONL 和配置格式不得缺失或改变。
