# Circle Packing 重构后验证 Run 1

## 运行边界

- Git：`9e876a7`（运行启动时；默认 ScienceFlow runtime 仍为 legacy facade 下的原类对象）
- worker=1 / worker=2 同时运行，共享本地 vLLM
- 与重构前 baseline 相同：模型配置、任务、seed 2222、900 秒 LNR 预算、CPU 划分和 Gate/Evaluator 配置
- 仅 run id 与 workspace 路径不同

## 结果

| 指标 | worker=1 | worker=2 |
|---|---:|---:|
| 状态 / exit code | completed / 0 | completed / 0 |
| 实际耗时 | 851.8 s | 851.8 s |
| 最终 Stage | W00:S01 | W01:S01（W00 无 Stage） |
| 最终 `radii_sum` | 1.9282828851999998 | 2.1891311245910927 |
| benchmark ratio | 0.7317961613662239 | 0.8307898006038303 |
| 独立 evaluator valid | true | true |
| Main LLM calls | 11 | 18（W00=6，W01=12） |
| Main input tokens | 105,341 | 175,154 |
| Main cached tokens | 83,888 | 136,416 |
| Main output tokens | 10,882 | 16,037 |
| Stage LLM calls / input | 1 / 835 | 1 / 837 |
| Stop reason | budget_expired | W00/W01 均为 budget_expired |

最终 artifact SHA256：

- worker=1：`6e95eb7907c0b4032713ecb2376a64da7f49e97bc0e48d503b9b3d455e7a3357`
- worker=2：`8c1ac20045b15016ca949b78140823b9f927dfcf6c052c0966d71740dade88cc`

## 契约验证

- 展开的 config 与 baseline 逐字段比较，worker=1/2 均仅有 4 个差异：
  `workspace_dir`、`task_workspace_root_dir`、`log_dir`、`submission_dir`；它们都指向本次隔离 workspace。其余字段及 provider 指纹完全一致。
- 首条 Agent user context 在归一化 workspace 绝对路径后与各自 baseline byte-for-byte 一致（长度分别为 5008、5269）。
- `deepcraft.legacy` facade 的 Message/Memory/OnlineLLM/BaseAgent/Tool 类仍与原包保持对象身份一致。
- Workspace compatible gate：worker=1 检查 193 个固定路径契约，worker=2 检查 205 个；均无 missing path、kind/mode、symlink 或结构化 shape 回归。worker=1 只新增 global merge interaction/traj 日志路径。
- worker 数、Stage/Gate、resource stop、merge final、Memory、interaction log、JSON/JSONL 和 submission symlink 契约均存在。

对应文件：

- `validation_run1_worker{1,2}_workspace_contract_manifest.json`
- `validation_run1_worker{1,2}_workspace_contract_report.json`
- `validation_run1_worker{1,2}_resolved_config_contract.json`

## 测试与判定

- DeepCraft/关键跨层测试：118 passed（依赖分层提交后）；确定性 replay/DeepCraft 契约：39 passed。
- ScienceFlow 轻量环境可运行集合：1608 passed、4 skipped。
- 另有 4 个环境型失败：3 个 Ratio Minimization 测试因 `.venv` 未安装 SciPy，1 个资源队列测试中的脚本因未安装 Torch；不是断言到本次代码差异。

本轮功能、文件和配置契约通过，但单次真实任务指标低于重构前样本，因此**效果门禁暂不判定通过**。默认路径没有算法替换，调用次数和 token 也未增加；首条 prompt 归一化后一致，差异目前归因为模型采样/并发轨迹的候选假设。需要用隔离复跑或多次样本验证，不能用架构同一性替代任务效果门禁。
