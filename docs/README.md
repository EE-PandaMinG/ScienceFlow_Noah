# ScienceFlow documentation

`docs/` 是仓库唯一的文档根目录。运行时代码、测试和任务包不应在这里保存实现副本；
规划、历史记录与正式证据也必须放入各自的分类目录，避免混放。

## 目录

- [`public/`](public/)：面向使用者的中英文说明、静态 HTML 文档和图片资源。
- [`architecture/`](architecture/)：当前有效的架构边界、组件职责和设计定义。
- [`plans/current/`](plans/current/)：正在执行的版本规划、owner matrix 与结构基线。
- [`plans/archive/`](plans/archive/)：已经完成或被替代的历史规划。
- [`benchmark/`](benchmark/)：Bench SF 定义与资源 workspace 审计。
- [`evidence/`](evidence/)：正式验收与失败样本的不可变证据。
- [`baselines/`](baselines/)：历史效果门禁、运行基线与机器可读报告。
- [`history/runtime_migration/`](history/runtime_migration/)：DeepCraft/InquiryCraft 迁移阶段、审计与验证记录。

## 维护规则

1. 新的执行规划统一放在 `plans/current/`，不再放入 `architecture/`。
2. 规划完成或被替代后移入 `plans/archive/`，保留 Git 历史。
3. `architecture/` 只描述当前稳定结构，不保存排期、阶段进度或临时 checklist。
4. 正式运行证据进入 `evidence/`；可复用长程 Resume checkpoint 由独立的
   `bench_sf` 本地仓库维护。
5. 文档链接统一相对于仓库路径书写；禁止重新创建顶层 `doc/`。
