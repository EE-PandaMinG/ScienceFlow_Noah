# Circle Packing 重构后验证 Run 2

## 运行边界

- Git：`502c353` 前后的文档/测试变更不进入已启动的 runtime 进程；ScienceFlow 默认执行路径未切换。
- worker=1 / worker=2 使用第二组全新 workspace 并行运行。
- 模型、任务、seed 2222、CPU、900 秒 LNR 预算、Gate 和 Evaluator 配置与 baseline 一致。
- 展开配置逐字段对比仍只差 4 个隔离 workspace 路径字段。
- 首条 Agent user context 归一化 workspace 路径后，与各自 baseline byte-for-byte 一致（worker=1 为 5008 字符，worker=2/W00 为 5268 字符）。

## 结果

| 指标 | worker=1 | worker=2 |
|---|---:|---:|
| 状态 / exit code | completed / 0 | completed / 0 |
| 实际耗时 | 875.7 s | 851.8 s |
| 最终 Stage | W00:S01 | W00:S01（W01 无 Stage） |
| 最终 `radii_sum` | 2.1666666666666665 | 1.858758122292416 |
| benchmark ratio | 0.8222643896268185 | 0.7054110521033837 |
| 独立 evaluator valid | true | true |
| Main LLM calls | 14 | 21（W00=12，W01=9） |
| Main input tokens | 146,951 | 221,317 |
| Main cached tokens | 121,520 | 181,888 |
| Main output tokens | 12,901 | 16,778 |
| Stage LLM calls / input | 1 / 828 | 1 / 833 |
| Stop reason | budget_expired | W00/W01 均为 budget_expired |

最终 artifact SHA256：

- worker=1：`19041c47f4a073a37de42cdf76923e6c58f57dfbc57951818a5642e7145c6604`
- worker=2：`fee94d9d688a3d1e22f2955085dbb6820d7c959b0eb1fb58e6a0736bf565c09c`

Workspace compatible gate 再次通过：worker=1 检查 193 个固定路径契约，worker=2 检查 202 个；均无 missing path、kind/mode、symlink 或结构化 shape 回归。worker=2 额外产生了 `stage_memory/index.json`，因为本轮轨迹使用了该已有能力。Run 2 的完整 workspace 保留在本地 ignored 目录；为避免重复提交约 3,480 项（主要来自 Agent 在 `tmp/deps` 安装并被 snapshot 捕获的 SciPy 文件）的巨大 Manifest，本轮只提交统计结论，临时比较报告保存在 `/tmp`。

## 两次样本与门禁判定

| 样本 | worker=1 metric | worker=2 metric |
|---|---:|---:|
| 重构前 baseline | 2.1937999999999622 | 2.441894866277423 |
| 重构后 Run 1 | 1.9282828851999998 | 2.1891311245910927 |
| 重构后 Run 2 | 2.1666666666666665 | 1.858758122292416 |

两个重构后样本均成功、有效且完整保留 workspace/配置/调用契约，但具体任务指标没有达到预先登记的单样本下限。因此严格的真实任务效果门禁仍为 **FAILED / 未允许切换默认 runtime**。

这不构成新 DeepCraft runtime 的性能结论：当前 ScienceFlow 仍调用与重构前完全相同的 legacy 类对象；没有替换 LLM、Tool、RunLoop、Memory、Stage 或 resource policy。调用次数、生成 token、Agent 生成的求解器和资源超时轨迹在三次随机运行间明显不同。后续必须使用本轮新增的 deterministic LLM recording/replay fixture，或增加足够的同条件统计样本，再判断 runtime 切换；不能删除旧路径或把可用性成功当成效果通过。
