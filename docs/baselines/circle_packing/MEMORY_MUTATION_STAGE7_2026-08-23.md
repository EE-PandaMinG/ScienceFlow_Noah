# DeepCraft Legacy Memory Mutation 迁移 Stage 7 记录

## 范围

本切片下沉三个领域无关机制：

- 将一个 runtime Workspace 绝对前缀稳定改写为 `.` / `./`。
- 对 legacy Memory 全量消息应用上层 transform，只有对象 identity 变化时才重建 storage。
- 保留 leading system/user task prefix，并裁剪到最近 N 个 assistant/tool rounds，避免 suffix 从 orphan tool 开始。

ScienceFlow 继续拥有 `wsp/<32hex>` 匹配规则、legacy ToolCall/Function 的具体复制方式、调用时机和 `recent_rounds` 配置。原函数签名保持为 facade。

## 快速门禁

- legacy record、clone inherit、resume、tool-memory 与 mutation 提供方：`117 passed`。
- ScienceFlow content/tool arguments 路径改写与 recent-round facade：`46 passed`（组合子集）。
- 完整相关 DeepCraft/ScienceFlow 快速组合、Ruff、compileall、dependency boundary、minimal import 与 diff-check 通过。
- 普通路径、空字符串、根目录、无变化消息、prefix、orphan tool 和奇偶裁剪边界均有契约测试。

本切片不修改持久化 JSON/JSONL 格式、Memory Record schema、Prompt、Workspace 布局或 LLM 调用，因此复用已保存的三 seed baseline，不启动长任务。

## 判定

Legacy Memory 的通用 mutation/prune 机制已归属 DeepCraft；ScienceFlow Workspace 路径与继承策略保持在上层。主 RunLoop 与完整 MemoryContext policy 仍未迁移，默认 Runtime 不切换。
