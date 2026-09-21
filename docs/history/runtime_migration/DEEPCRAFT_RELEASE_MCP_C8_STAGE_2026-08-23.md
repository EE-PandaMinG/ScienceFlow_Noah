# C8 DeepCraft 独立 Wheel / MCP 收口记录

日期：2026-08-23

## 已完成

- `deepcraft[mcp]` 现在只依赖 `mcp[cli]`，不再依赖历史 `deepcraft-agent` 或
  `deepcraft-core[mcp]`。
- 新 `deepcraft.mcp.MCPClient` 将 stdio/SSE server tool 直接映射为正式
  `deepcraft.tools.BaseTool/ToolCollection/ToolResult`，使用 Runtime cancellation 和 ToolContext。
- DeepCraft 自己持有的 BaseAgent compatibility 改用自己持有的 Memory、BaseTool 和
  ToolCollection，不再从历史 agent distribution 获取对象。
- 两份 CI 中已经失效的 `deepcraft/core`、`deepcraft/agent` 路径修正为当前布局；增加独立 wheel
  build、wheel 内容检查、隔离安装和 cold CLI job。
- DeepCraft 暴露 distribution `__version__`。
- C7 三 seed/worker=2 严格效果门禁通过后，已物理删除零运行消费者的
  `legacy_packages/agent`（957 行 Python），同时移除 root/DeepCraft path source、pytest
  pythonpath 和 ScienceFlow 的 agent 路径注入。DeepCraft 自有 compatibility BaseAgent 与
  ScienceFlow legacy backend 回滚能力继续保留。
- ScienceFlow 包初始化中的最后一段 repo-local `sys.path` 注入也已删除；DeepCraft 与暂存的
  historical core 均由声明式 dependency/editable source 解析。删除后实际 import 路径仍指向本仓
  对应包，定向测试 `10 passed`，runtime parity quick 四类差异继续为 0。

## 实际发布候选检查

已构建 `deepcraft-0.1.0-py3-none-any.whl`，在新的 uv virtualenv 中从 `/tmp` 安装并验证：

- `import deepcraft` 不导入 ScienceFlow；
- `deepcraft.__version__ == "0.1.0"`；
- `deepcraft tools list` 返回 `read_text/write_text/shell`；
- wheel 共 95 项，不包含 `scienceflow` 或 `legacy_packages` 路径；
- MCP contract/adapter 与依赖边界 `10 passed`。

删除历史 agent distribution 后重新构建相同版本 wheel，仍为 95 项；新建隔离 uv 环境只安装
`click + deepcraft` 后，`import deepcraft`、版本 `0.1.0` 和 `deepcraft tools list`
（`read_text/write_text/shell`）再次通过，wheel 内没有 `deepcraft_agent`、`legacy_packages` 或
ScienceFlow 条目。DeepCraft 完整测试为 `116 passed`，删除边界定向测试为 `12 passed`。
删除后的 ScienceFlow 根完整矩阵为 `1675 passed, 3 skipped`；另有一次在重型 ratio solver
并行占用 CPU 时出现 interaction log 并发顺序抖动，独立复现 5 次及无负载全量复跑均通过，未修改
比较器或放宽断言。

## 历史 core 删除与正式 LLM 收口

完成 C1 replay 驱动的最后一段归属迁移后，已删除：

- `deepcraft/legacy_packages/core` 整个历史 distribution；
- `deepcraft_core` path source、lock package 和 pytest path；
- 中间过渡层 `deepcraft.llm.legacy_compat`；
- CI 中所有已失效的 historical core 安装与测试路径。

冻结实现现由 `deepcraft.llm` 自身持有。原 1566 行 `online.py` 被按 request policy、text stream、
tool stream、logprobs、write argument decoder 和 accounting 拆分；公开入口
`deepcraft.llm.online.OnlineLLM`、原有方法签名、retry/timeout、request omission、stream interrupt、
ToolCall 聚合和稳定 seed ID 合同保持。所有正式源码文件不超过 350 行，函数不超过 120 行。

相对本阶段开始的 Git 检查点，DeepCraft Python 总量从 12,269 行降到 9,946 行，净减少 2,323 行；
这包含删除 4,565 行 historical core 后保留必要功能的正式模块，不以功能裁剪换取行数。

## 本阶段最终验证

- DeepCraft：`140 passed in 2.59s`；Ruff、compileall、dependency boundary 和 source-size 通过。
- 受影响 provider/consumer：`23 passed, 3 skipped`；随后完整根矩阵
  `1675 passed, 3 skipped, 2 warnings in 161.85s`。
- `runtime_parity quick --jobs 4`：context、mechanism、workspace 未登记差异均为 0；performance
  suite 同样通过且登记差异为 0。
- 本机 Qwen3.6-27B vLLM：纯文本、强制 ToolCall、tool argument streaming、seeded stable ID 和
  client close 全部通过。
- DeepCraft CLI：严格返回 `C8_DEEPCRAFT_CLI_OK`；session JSONL 角色为
  `system,user,assistant`，event sequence `1..8` 且以 `session.completed` 闭合。
- 新构建 wheel 共 105 项，不含 ScienceFlow、`legacy_packages`、`deepcraft_core` 或
  `deepcraft_agent`；只安装 `click + deepcraft` 的隔离环境可 import、显示版本并列出
  `read_text/write_text/shell`，且 cold import 不加载 OpenAI/Pydantic。

没有更新 baseline、修改 Prompt/Tool schema、放宽 comparator 或重复运行 Circle Packing；C7 已完成
三 seed/worker=2 效果门禁，本切片是纯工程归属迁移。

## 尚余发布动作

源码、独立 wheel 和 CI 边界已经就绪；DeepCraft 独立 Git 仓库、`main` 和 `v0.1.2` 已推送。
用户明确不需要 PyPI；发布合同改为私有 Git tag 加 GitHub Release 制品。ScienceFlow 已依赖该 tag，
lock 固定解析 commit，仓内 editable source 与源码副本均已删除。

## 纯 facade 最终清理

在 core 删除检查点之后继续按实际消费者清单删除了 9 个零消费者 re-export 文件：整个
`deepcraft.compat` 包，以及 flat `deepcraft.hooks/cancellation/resume/replay`。第一次候选还尝试
删除 `deepcraft.memory.legacy_records`，快速门禁立即发现它仍被 Memory 顶层 API 装配使用，因此
恢复并保留；没有通过修改测试掩盖这个真实依赖。

最终结果：

- DeepCraft `139 passed`，ScienceFlow/跨层定向 `8 passed`；
- runtime parity quick 的 context、mechanism、workspace 差异仍全部为 0；
- wheel 从 core 收口后的 105 项进一步降为 96 项，不含 `deepcraft/compat`、flat shim、ScienceFlow
  或任何 historical distribution；隔离 minimal import 与 CLI tools list 通过；
- 相对 C8 开始检查点，DeepCraft Python 从 12,269 行降至 9,861 行，净减少 2,408 行。

## 独立仓发布准备

为保证 `deepcraft/` 目录可直接成为独立 Git 仓，而不只是 monorepo 中“看起来独立”，本阶段又完成：

- 增加 DeepCraft 自有 `.github/workflows/ci.yml` 和 tag 驱动的 `release.yml`；后者构建 sdist/wheel、
  校验 tag/version、运行独立测试并创建带制品的 GitHub Release；不使用 PyPI；
- 增加独立 `LICENSE`、`CHANGELOG.md`、`.gitignore`、项目 URL 和 SPDX metadata；
- 生成 DeepCraft 自有 `uv.lock`（59 packages），不再依赖 ScienceFlow 根 lock 才能复现开发环境；
- 将 DeepCraft 测试中唯一直接 import ScienceFlow 的断言移回已有 ScienceFlow 跨层 contract；
- 将 legacy Resume fixture 复制为 DeepCraft 自有测试资产，移除测试对父仓目录的读取；
- 删除无人使用的 `deepcraft[scienceflow]` extra 别名，ScienceFlow 明确使用
  `deepcraft[openai,legacy]`。

将 `deepcraft/` 完整复制到父仓之外的新目录并使用全新 venv 安装后，独立结果为
`136 passed, 1 skipped`，Ruff 通过，且运行过程没有 import ScienceFlow。最终 wheel 为 97 项，
metadata 包含 `Version: 0.1.0`、`License-Expression: MIT` 和独立仓 URL；不含 ScienceFlow、
historical distribution 或已删除 facade。

仓库创建后，SSH 写入已验证。远端为 private，未认证 GitHub API无法读取 Actions/Release 页面，
但 Git refs、tag 解引用、私有 Git 安装和 lock commit 均已独立验证。

### 可推送的独立 Git 历史

从最终 `deepcraft/` 前缀生成了本地独立历史并再次按真实 Git clone 验证：

- 本地 branch：`deepcraft-standalone`；远端 `main` tip
  `393ac7a5d89f8334dbe06a1a46be36631ae4f6a8`；
- annotated tag：`v0.1.0`，解引用后指向同一提交；
- clone 后使用仓内 `uv.lock` 做 locked sync，独立测试 `136 passed, 1 skipped`，Ruff 通过；
- 从 clone 根目录构建 wheel，内容仍为 97 项且隔离检查通过。

远端初始化提交 `dc604ac` 只包含一行 README；发布时未强推，而是以该提交和已验证独立历史为
双父节点生成内容不变的合并提交，再正常快进 `main` 并推送 `v0.1.0`。在 wheel 实际发布前，
不能把 ScienceFlow 的 local editable source 改成版本范围，否则当前安装和 CI 会立即失去可解析
依赖；最低/锁定/最新跨仓兼容矩阵同样应在首个制品可安装后启用。

## Git-only 发布决定与 0.1.2

推送 `v0.1.0` 后确认 PyPI 的 `deepcraft` distribution 已由无关第三方项目占用，其现有版本为
`0.0.1`。因此没有覆盖或冒用该名称，而是把发布 distribution 改为尚未占用的
`deepcraft-runtime`；Python import package 和 CLI 继续保持 `deepcraft`，ScienceFlow 运行时合同
不变。用户明确不需要 PyPI，发布边界改为私有 Git tag；为避免重写历史标签，最终版本为 `0.1.2`。

本地候选验证：DeepCraft `136 passed, 1 skipped`、Ruff 通过；隔离 wheel 名为
`deepcraft_runtime-0.1.2-py3-none-any.whl`，共 97 项，只安装 `click`，`import deepcraft` 返回
`0.1.2`，CLI tools list 正常，未加载 ScienceFlow；runtime parity full 4 进程严格比较为 0 diff。

`v0.1.2` 解引用到 `5f2493374ccd3d318997926714eb0c8c2cbb0f78`。release workflow 已删除
PyPI publisher，改用仓库 `GITHUB_TOKEN` 创建 GitHub Release 并附加 wheel/sdist。

## ScienceFlow 物理分仓

ScienceFlow 的依赖声明直接引用私有 `v0.1.2`，`uv.lock` 固定上述 commit。确认从
site-packages 加载 DeepCraft 且 full parity 为 0 diff 后，删除了仓内 `deepcraft/` 跟踪树和重复的
根 DeepCraft CI，共 136 个文件、14,475 行；ignored 构建缓存可恢复地移动到
`/tmp/scienceflow-embedded-deepcraft-remnants-Lq5HqJ/deepcraft`。DeepCraft provider 测试只在独立仓
运行，ScienceFlow 保留 consumer 和跨层 contract。

由于两个仓库均为 private，ScienceFlow GitHub Actions 读取 DeepCraft 需要仓库 secret
`DEEPCRAFT_READ_TOKEN`；workflow 已固定 checkout `v0.1.2`，不跟随 `main` 漂移。
另有 nightly workflow 每日验证 DeepCraft `main`，并提供手动 ref 输入用于升级前验证。

最终根矩阵在补装锁定的 `scientific-design` extra 后为
`1677 passed, 3 skipped, 2 warnings in 166.61s`；DeepCraft 独立矩阵为 `136 passed, 1 skipped`。
两边测试所有权已物理分开，不再在 ScienceFlow 重复执行 provider tests。
