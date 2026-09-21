# DeepCraft PooledLLM Failover 迁移 Stage 5 记录

## 范围

本切片把 provider 通用的 reasoning replay 错误识别，以及 legacy `OnlineLLM` 的 round-robin、sticky routing、同 key 软重试、跨 key failover、cooldown、`Retry-After`、统计代理和 interrupt 状态机迁移到 DeepCraft。

ScienceFlow 的 `scienceflow.core.key_pool.PooledLLM` 保留为同名子类 facade，并继续保留：

- `scienceflow.core.key_pool` 导入路径和类 `__module__`。
- 原构造签名与默认 cooldown 值。
- `SCIENCEFLOW_POOL_RL_MAX_WAIT_SEC` 环境变量。
- `scienceflow` logger 与原日志文本。
- 可动态替换的模块级 `OnlineLLM`。
- 可动态调整的 `_SOFT_RETRY_DELAY_SEC`。
- `_stable_index`、`_retry_after_seconds` 和 `_pooled_last_idx` 私有兼容入口。

本切片不修改 StageConfig、模型参数、重试次数、异常类型、Prompt、Tool、Workspace 或默认 Runtime。

## 快速门禁

- ScienceFlow sticky/failover、构造、worker 配置、deterministic gate 与 RunLoop 消费方：`95 passed`。
- DeepCraft 提供方与 ScienceFlow facade 组合：`22 passed`。
- DeepCraft 依赖边界：`4 passed`。
- Ruff、compileall、minimal import 通过；最小 `import deepcraft` 不加载 OpenAI、httpx 或 Click。
- 同一段 scripted `ReadTimeout` 轨迹在旧提交 `d9b650b` 与 candidate 输出 JSON byte-for-byte 一致，包括调用顺序、调用次数、failover 次数、pool index、usage、TTFT、TPOT、finish reason 与 repr。

成功热路径交替长采样（每组 15 次、每次 50k 调用，两组/侧）的合并中位数：

- baseline: `0.176134s`
- candidate: `0.175871s`
- 变化：`-0.149%`

因此没有可见性能回归。根据分层验证规则，本纯工程切片复用已通过的阶段级完整矩阵和三 seed baseline，不启动新的长任务。

## 判定

PooledLLM failover 本体和 provider reasoning-error 识别已归属 DeepCraft，ScienceFlow 外部兼容面保持。ScienceFlow 主 RunLoop、Memory Policy 与默认 provider 调用链仍需后续切片迁移；本结果不授权切换默认 Runtime。
