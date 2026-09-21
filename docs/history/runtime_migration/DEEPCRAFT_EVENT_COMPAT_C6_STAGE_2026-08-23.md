# C6 DeepCraft Event / JSONL Compatibility 收口记录

日期：2026-08-23

## 结果

- LHR/Stage/ESTRA/Resource 控制事件先提升为 DeepCraft `RuntimeEvent`，再由 compatibility renderer
  生成历史 ScienceFlow event；旧 `lhr_events.jsonl` 字段、排序、文件名和写入顺序不变。
- `ScienceFlowEventBridge` 改用 DeepCraft `SyncJsonlEventSink`，不再维护第二套 JSONL writer。
- async/sync DeepCraft sink 都在重启时恢复已有最大 sequence；仅修复最后一个未闭合 partial line，
  对中间或已闭合坏行继续硬失败。
- `load_events()` 可读取 crash 后尚未修复的有效前缀；下一次 append 自动截断 partial tail 并从正确
  sequence 继续。
- completion/failure 事件继续强制 flush；ScienceFlow 的高频 LLM/Bash chunk 仍走原 interaction
  logger，不被逐 chunk 转写为 RuntimeEvent，因此不增加 provider 或 Bash stream 阻塞。
- 新 event 文件仍为显式 opt-in，并位于 `task_logs`，不会进入 Agent Workspace、Snapshot、Merge
  或 artifact 扫描。

## 一致性门禁

- 普通 LHR writer 与启用 DeepCraft dual-write 的历史 `lhr_events.jsonl`、`lhr_state.json` 字节一致。
- RuntimeEvent -> legacy event round-trip 字段完全一致。
- bridge 重启、partial tail、sequence continuation、坏完整行拒绝均有独立测试。
- DeepCraft event/runtime/replay 与 ScienceFlow LHR/ESTRA/Resource 定向矩阵：`30 passed`。
- Runtime Parity quick（jobs=4）：context、mechanism、workspace、failed cases 全为 `0`。

本阶段不改变任何 Prompt、provider payload、ToolCall、Memory 或既有 Workspace 文件合同。
