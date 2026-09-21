# Plans

规划文档与稳定架构定义分开维护：

- [`current/`](current/)：当前仍在执行或用于发布收口的规划。
  - [`agent_runtime_v5_plan.md`](current/agent_runtime_v5_plan.md)
  - [`plan_v5.2.md`](current/plan_v5.2.md)
  - [`product_tui/plan_v2.md`](current/product_tui/plan_v2.md)：复用现有 TUI/manifest/runtime 的最小侵入式 `/long-research` 规划。
  - [`lnr_storage_telemetry.md`](current/lnr_storage_telemetry.md)：LNR 复用阶段快照统计、排除输入数据并向 TUI 提供轻量存储投影。
- [`archive/`](archive/)：已经完成或被后续版本替代的历史规划，仅保留追溯用途。

新增规划先进入 `current/`；完成、取消或被替代后通过 Git rename 移入 `archive/`。
架构事实应沉淀到 [`../architecture/`](../architecture/)，运行证据应进入
[`../evidence/`](../evidence/)，不要把实现记录继续追加到 plan 文件中。
