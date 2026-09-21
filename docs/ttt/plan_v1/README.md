# ScienceFlow Test-Time Training Plan V1

本目录保存 ScienceFlow 引用 TTT-Discover、实现“异步训练 + Workspace Resume + Online
Agentic 自主迭代”的第一版设计基线。

状态：**设计完成，尚未实现**。

基线：

- ScienceFlow：`747d6329f12c0b914dd8ca97b21787acb788b374`
- TTT-Discover：`6c40e82dab9d5de7416ac873ad5cd3106084aaed`
- 设计日期：2026-08-31

文件：

- [`plan_v1.md`](plan_v1.md)：canonical 工程规划、合同和验收标准。
- [`ttt_scienceflow_plan_v1.tex`](ttt_scienceflow_plan_v1.tex)：论文式设计报告 LaTeX 源稿。
- [`ttt_scienceflow_plan_v1.pdf`](ttt_scienceflow_plan_v1.pdf)：编译后的 PDF 报告。

PDF 使用 Tectonic 构建：

```bash
tectonic --keep-logs --keep-intermediates ttt_scienceflow_plan_v1.tex
```

V1 不把 `test-time-training/discover` 整仓复制进 ScienceFlow，也不直接修改正在执行中的基模型。
首个实现目标是冻结 Qwen 基座、异步训练任务级 LoRA、在 Stage/lineage 边界执行可回滚晋升。
