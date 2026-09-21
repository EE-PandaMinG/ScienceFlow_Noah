# DeepCraft Runtime 通用机制迁移 Stage 4 记录

## 范围

本阶段只迁移通用工程机制，不修改 ScienceFlow 的 Prompt、Tool Schema、算法、调度、超时、Workspace 写入或默认 Runtime：

- 同轮 tool stream 重试次数、指数退避和错误分类下沉到 `deepcraft.llm`。
- OpenAI dict 与 SDK object 两种 tool-call 读取下沉到 `deepcraft.tools`。
- 多 Key endpoint 的 round-robin、cooldown、sticky index、`Retry-After` 和 key/url 展开下沉到 `deepcraft.llm`。
- ScienceFlow 保留其 stream 清理、reasoning replay、日志、failover、环境变量和 Memory 策略，通过兼容 facade 使用新机制。

## 快速分层门禁

根据纯工程迁移的风险，本阶段不重复运行 baseline/candidate 两侧长任务：

- 相关 retry、tool-call、key-pool、REPL 和配置消费方测试均通过。
- DeepCraft 独立测试：`44 passed in 0.75s`。
- DeepCraft Runtime/Resume/Memory/Workspace 组合门禁：`65 passed in 3.09s`。
- ScienceFlow 完整矩阵：`1667 passed, 3 skipped, 2 warnings in 222.93s`。
- `scientific-design`：`29 passed, 1 skipped in 24.78s`。
- DeepCraft 与 ScienceFlow CLI 均能冷启动；`deepcraft tools list` 保持 `read_text`、`write_text`、`shell`。
- 变更 Python 文件 Ruff、compileall、diff-check、DeepCraft 单向依赖和 minimal-import 门禁通过。

旧/新实现的 endpoint pool 秒级热路径微基准（7 次取最小值）没有可见回归：

| 操作 | baseline `d9b650b` | candidate | 变化 |
| --- | ---: | ---: | ---: |
| `KeyPool.pick` × 200k | 0.074336s | 0.074053s | -0.38% |
| `parse_key_env` × 100k | 0.195888s | 0.187386s | -4.34% |
| stable index × 100k | 0.066047s | 0.066689s | +0.97% |

## 可复用三 seed baseline

旧代码 `d9b650b` 已在完全相同的物理 Workspace 路径上完成 seed `2222/3333/4444`，均为 `worker=2`，三个 evaluator 结果均 valid/eligible。分数与前一轮记录逐 seed 完全一致：

- `2222`: `2.16602261940063`
- `3333`: `2.3801381750708424`
- `4444`: `2.4916996199873798`

baseline Workspace 已归档，且在移动前分别抓取了 496、508、475 项完整 Workspace Contract Manifest。机器可读记录见 `memory_stage4_baseline_report_20260823.json`。

candidate 侧延后到默认 Runtime 切换前的最终门禁。届时重建同一物理路径，只补 candidate 并与本 baseline 比较，不重新消耗 baseline 时间。

## 判定

本阶段通用机制迁移通过快速工程门禁，但不代表主 ScienceFlow RunLoop 或 PooledLLM failover 已全部迁移，也不授权切换默认 Runtime。完整三 seed candidate、非 Circle Packing 代表任务和最终 Workspace 等效门禁仍属于发布收口条件。
