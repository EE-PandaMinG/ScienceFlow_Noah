# DeepCraft Legacy LLM Factory 迁移 Stage 6 记录

## 范围

本切片把以下配置无关的构造机制迁移到 `deepcraft.compat.llm_factory`：

- single `OnlineLLM` 与多 endpoint `PooledLLM` 分支。
- 共享的 model、token、frequency penalty、system-message coalesce、stream 和 tracker 参数。
- key/url 展开、endpoint model broadcast/cycle。
- sticky routing 与 cooldown 参数。
- 只在动态挂载时传递的 deterministic `request_seed`。
- 上层注入的 headers 与 HTTP async client kwargs。

ScienceFlow `_build_llm(StageConfig)` 仍保留原导入入口，只把 StageConfig 映射为 `LegacyLLMFactoryConfig`，并注入现有 `OnlineLLM`、ScienceFlow `PooledLLM` facade 与 `scienceflow` logger。

本切片不修改 StageConfig schema、环境变量、HTTP client 构建、模型参数、Prompt、Tool、Workspace 或 Runtime 选择。

## 快速门禁

- DeepCraft factory 提供方与 ScienceFlow StageConfig 消费方：`19 passed`。
- single/pool、request seed 存在/缺失、异构模型 cycle、routing 与 cooldown 均有独立契约断言。
- 旧提交 `d9b650b` 与 candidate 使用同一组 single/pool StageConfig 和 mock client 工厂，输出的完整构造 kwargs JSON byte-for-byte 一致。
- Ruff、compileall、DeepCraft dependency boundary、minimal import 与相关 Runtime/Workspace 快速门禁通过。

factory 每个 Agent/feedback client 只在构造时执行一次，不位于 token、stream 或 tool-call 热路径。依据分层验证规则，本切片不启动真实长任务。

## 判定

通用 legacy LLM 构造机制已归属 DeepCraft，ScienceFlow 配置与输出契约保持。默认 client 仍是兼容期 legacy `OnlineLLM`；切换到新的 `LLMClient`/OpenAI adapter 需要在主 RunLoop backend 门禁完成后单独进行。
