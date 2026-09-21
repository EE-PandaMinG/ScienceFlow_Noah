# C5 ScienceAgent 双 Runtime Backend 阶段记录

日期：2026-08-23

## 本切片结果

- `ScienceAgent` 新增 `legacy` / `deepcraft` backend 选择；C5 接入时保持 `legacy`，全部门禁通过后
  已在 C7 切换默认值为 `deepcraft`。
- backend 选择位于 `repl.runtime_backend`，只参与进程内编排，不进入 Prompt、Memory、provider
  request 或 Workspace。
- DeepCraft 新增 `HostedAgentRuntime`，接管单次策略循环的 admission、取消、`ScienceAgent.state`
  生命周期、失败收口和 event sink flush；每轮策略入口执行 DeepCraft cancellation check。
- ScienceFlow 现有策略循环移动为 `_run_scienceflow_policy_loop`，没有修改循环体及其上下文构建、
  Tool 调度、Stage/Resource、Resume 和 Workspace 写入逻辑。

现有轮次循环保留 ScienceFlow 策略编排，但实际依赖的通用 retry、stream guard、Tool bundle
分类/并发、LLM adapter、生命周期、取消和事件均来自 DeepCraft。双 backend 门禁完成后，默认值在
C7 切为 `deepcraft`；`legacy` 仍保留为回滚路径。

## 一致性证据

同一录制 LLM 脚本分别运行两个 backend，严格比较：

- 两轮 provider 前参数；
- 完整 Memory `model_dump(mode="json")`；
- ToolCall ID、名称、参数和结果；
- 返回文本；
- Workspace 路径集合和文件字节。

结果完全一致。backend replay 还覆盖 readonly 并行 bundle、同轮 LLM retry 和调用前取消。
定向门禁 `22 passed`；DeepCraft runtime/依赖边界与初始 backend replay `13 passed`；扩展后的
hosted/backend replay `8 passed`；Runtime Parity quick（jobs=4）四类差异均为 `0`。

## 风险与下一步

现有 `RunLoopMixin.run` 将运行时机械流程和科学策略写在同一大函数中。后续按“轮次准备 -> LLM
调用 -> 响应分类 -> Tool bundle 调度 -> 轮次收口”五个稳定接缝提取，每提取一个接缝立即运行双
backend replay。不得复制一份新循环，也不得通过放宽 normalization 接受差异。

## 短真实 vLLM 门禁

本机 `Qwen3.6-27B` 以 `runtime_backend=deepcraft` 完成一次 `write -> read -> final`：最终回答
精确为 `C5_DEEPCRAFT_OK`，`c5.txt` 精确为 `C5_DEEPCRAFT_OK\n`，Memory role 顺序为
`user, assistant, tool, assistant, tool, assistant`，结束状态回到 `IDLE`。临时 Workspace 为
`/tmp/scienceflow_c5_deepcraft_mn5tjb7s`。

## Circle Packing 与 exact-workspace Resume

seed `5555`、worker=1、`runtime_backend=deepcraft`。首段因 240 秒 LNR 中预留 180 秒全局 merge，
worker 在 Stage 提交前 `budget_expired`；进程虽为 exit 0，但本记录明确不将它判为效果通过。

随后使用同一 run ID、Workspace、`.agent_memory/ScienceAgent/{short_term.json,long_term.jsonl}` 和
`solution.py` 进行 Resume。恢复后成功执行 solver 并提交 `W00:L01:S01`：

- evaluator backend：`task_package`，status `ok`；
- `validation_ok=true`、`selection_eligible=true`、Gate action `accept`；
- metric validity `high`；
- `radii_sum=2.4641818359`，高于任务初始合法基线 `1.82`；
- snapshot `W00-L01-S01-76181da190`，Memory、Stage logs 和 Workspace 均保留。

恢复段在 247 秒后由外层累计预算正常标记为 `budget_done/time_budget_expired`；该状态发生在有效
S01 已落盘之后，不伪装为 `completed`。恢复后的 short/long Memory 均为 19 条、29289 bytes。

首次与恢复 manifest 分别为
`scripts/deepcraft_runtime_c5_circle_seed5555_20260823.yaml` 和
`scripts/deepcraft_runtime_c5_circle_seed5555_resume_20260823.yaml`。
