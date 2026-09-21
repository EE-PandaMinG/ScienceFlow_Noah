# ScienceFlow / DeepCraft Tool Runtime v2 最终验收

最终候选为 ScienceFlow `bc43534` 与 DeepCraft `v0.3.0` (`880fc90`)；`uv.lock` SHA-256 为
`4375e6be3d2251f6e9ee752f833d6e887a206ceba01a8c7d81e98218fefe2975`。本报告只记录冻结
comparator 的结果，不重录 baseline、不修改容差。

## 结果

- B1：DeepCraft canonical/历史 fixture 与 full suite 通过，`145 passed`；
- B2：Schema、Context、Mechanism、error text、Workspace 五类 diff 全为 0，冻结 SHA-256 未变；
- B3：full 与 performance 的 failed case、context、mechanism、workspace 未登记差异全为 0；
- B4：迁移阶段 Worker=2 strict manifest 比较 435 entries，additional/mismatch/missing 全为 0；最终代码又
  从迁移前 exact Workspace 原位继续三 seed，并保留 Memory、Stage、artifact、日志和累计预算；
- B5：DeepCraft standalone CLI 在独立 full suite 中通过；ScienceFlow CLI/组合/Workspace/Resume 聚合
  `84 passed`；
- B6：fresh exploration 暴露模型随机性，且一次原位 continuation 仍未满足所有严格配对行；没有放宽门禁。
  从已验收的迁移前 exact Workspace 用最终代码继续后，三个 seed 全部 completed、validation/selection
  eligible，逐 seed、median、worst quality 和 runtime 全部通过；
- B6 non-Circle：ratio-minimization exact Resume 151.3 秒，累计预算 1203.1 -> 1354.4 秒，
  `inv_ratio_squared=0.0678325632379603`，validation/selection 均为 true；
- B7：ScienceFlow `1681 passed, 3 skipped`，DeepCraft `145 passed`，Ruff/format 与 performance 通过。

Circle Packing 最终三 seed：

| seed | candidate metric | reference metric | candidate time | reference time | result |
| --- | ---: | ---: | ---: | ---: | --- |
| 2222 | 2.4784410491 | 2.1106639153 | 330.2s | 987.6s | pass |
| 3333 | 2.5158387449 | 1.8200000000 | 337.2s | 834.3s | pass |
| 4444 | 2.0438852729 | 2.0154003333 | 247.9s | 953.5s | pass |

## 结构结果与保留观察

`scienceflow/core/agent/tool_exec`、`core/agent/tools`、`core/tools`、通用 `core/executor` 和
`deepcraft/legacy` 已删除。ScienceFlow production 相对 `4c81751` 净减少 1119 行。强耦合的
ScienceFlow context/resource/Stage/LNR policy 没有为追求行数下沉到 DeepCraft；其中大文件的后续
method extraction 已记录在 migration observations，必须继续使用 B2/B3/Resume 小切片验证。

机器可读总报告见 `docs/baselines/TOOL_RUNTIME_V2_FINAL_VALIDATION_2026-08-23.json`；B2、B3、性能、
Worker=2 strict 与 Circle effect gate 的原始 JSON 同目录保存。
