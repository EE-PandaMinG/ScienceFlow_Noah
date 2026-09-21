# DeepCraft 私有 Git 发布与物理分仓记录（2026-08-23）

## 结论

DeepCraft 与 ScienceFlow 已从“同仓不同目录”切换为两个独立演进边界。DeepCraft 通过私有 Git
tag 发布，不使用 PyPI；ScienceFlow 只消费固定 tag，并由 `uv.lock` 固定 commit。

## 发布边界

- 仓库：`git@github.com:EE-PandaMinG/DeepCraft.git`；
- 正式版本：`v0.1.2`；
- tag commit：`5f2493374ccd3d318997926714eb0c8c2cbb0f78`；
- distribution：`deepcraft-runtime==0.1.2`；
- Python namespace 与 CLI：继续为 `deepcraft`；
- release workflow：构建、独立测试、tag/version 校验、上传 Actions artifact、创建带 wheel/sdist 的
  GitHub Release；没有 PyPI 发布步骤。

## ScienceFlow 消费边界

- `pyproject.toml` 直接依赖私有 Git `v0.1.2`；
- `uv.lock` 将 tag 解析固定到 `5f249337...`；
- pytest 不再注入 `deepcraft/src`；
- 根仓不再运行 DeepCraft provider test；只保留 ScienceFlow consumer 与跨层 contract；
- private cross-repo CI checkout 固定 `v0.1.2`，凭据名为 `DEEPCRAFT_READ_TOKEN`。
- nightly compatibility 每日验证 DeepCraft `main`，也支持手动指定 branch/tag/commit；功能 parity
  仍以 4 进程运行。

## 物理删除

从 ScienceFlow 删除仓内 `deepcraft/` 跟踪树及重复根 CI，共 136 个文件、14,475 行。全部内容已由
DeepCraft `main`/`v0.1.2` 和 ScienceFlow Git 历史双重保护。ignored 构建缓存没有直接删除，已移动到
`/tmp/scienceflow-embedded-deepcraft-remnants-Lq5HqJ/deepcraft`。

## 无损验证

- DeepCraft 独立：`136 passed, 1 skipped`，Ruff 通过；
- Git 安装：`deepcraft-runtime==0.1.2`，模块来自 `.venv/site-packages`；
- ScienceFlow full runtime parity：4 进程，Context/Mechanism/Workspace/failed 均为 0；
- 跨层定向：17 passed；
- ScienceFlow 最终完整矩阵：`1677 passed, 3 skipped, 2 warnings in 166.61s`；
- 生产 Prompt、Tool schema、运行策略以及 Workspace log/memory/JSON/JSONL 均未修改。

全量 `ruff check scienceflow` 另发现 32 项既有规范债务，已登记为 `OBS-014`。本阶段没有用 noqa
掩盖，也没有把 import side-effect 风险混入纯分仓提交；本次修改文件的 Ruff 与 compileall 通过。
