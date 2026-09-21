# InquiryCraft 品牌与独立 File Tool 阶段记录（2026-08-23）

## 结论

本阶段完成两项相关工程调整：

1. 文件 Tool 不再归属于 `workspace` 源码层级。InquiryCraft 现在以独立
   `FileTool`/`ReadTool`/`WriteTool`/`EditTool`/`GrepTool`/`GlobTool`/`LsTool`
   提供能力，路径范围由可注入的 `PathPolicy` 单独控制。
2. Agent Runtime 品牌、canonical Python namespace、distribution、CLI 和新环境变量从
   DeepCraft 切换为 InquiryCraft；ScienceFlow 生产导入全部切换到 `inquirycraft.*`。

该阶段是纯工程迁移，没有修改 ScienceFlow 的模型 Prompt、Tool 名称或参数 Schema、
Memory 插入顺序、interaction log、Stage/LNR 回调、资源机制和任务 workspace 布局。

## 最终结构

```text
InquiryCraft/src/inquirycraft/tools/
├── file_tools.py       # FileTool + Read/Write/Edit
├── search_tools.py     # Grep/Glob/Ls
├── path_policy.py      # root containment / extra roots / denied prefixes
├── filesystem/         # 领域无关文件操作原语
├── execution/          # 通用 Tool execution engine
└── artifacts/          # 通用 raw output store/reducer
```

`tools/workspace/`、`workspace_tools.py` 和 `workspace_search_tools.py` 已从 canonical
源码移除。`workspace` 现在只是宿主可选择的路径策略，而不是 Tool 的代码所有者。
ScienceFlow 继续以原来的 `workspace_dir`、`sandbox` 和 extra roots 参数组装 Tool；
InquiryCraft 在内部把这些兼容参数收敛为严格 `PathPolicy`，因此现有路径行为不变。

## 品牌与兼容边界

- canonical distribution：`inquirycraft-runtime==0.4.0`；
- canonical namespace：`inquirycraft`；
- canonical CLI：`inquirycraft`；
- canonical standalone env：`INQUIRYCRAFT_*`；
- 私有 Git tag：`v0.4.0`，commit `dd18ff9907af61678d7b11fc7717c52eb65aee7a`；
- 不发布 PyPI；继续从私有 Git tag 安装；
- 新 `EE-PandaMinG/InquiryCraft` 仓在执行时尚不存在，因此远端 URL 暂时保留历史
  `EE-PandaMinG/DeepCraft.git`，品牌与代码 namespace 已完成迁移。

为避免旧消费者瞬时失效，发行包暂时保留薄 `deepcraft` 顶层兼容入口、旧 CLI alias 和
`DEEPCRAFT_*` 环境变量回退；所有实现只有一份，位于 `inquirycraft/`。

以下名称属于已经冻结的 ScienceFlow 配置或 workspace 数据合同，刻意不改名：

- `runtime_backend="deepcraft"` 内部兼容 token；
- `SCIENCEFLOW_DEEPCRAFT_EVENTS`；
- `deepcraft_events.jsonl`；
- 历史 benchmark/fixture/config 文件名。

这些保留项不会作为新品牌 API 继续扩展；若未来迁移，必须另做数据格式版本化和 Resume 门禁。

## 验证结果

- InquiryCraft full suite：`152 passed`；
- InquiryCraft Ruff：`src/inquirycraft`、薄兼容层和 tests 全绿，`152 files` format clean；
- wheel/sdist：`inquirycraft_runtime-0.4.0` 构建成功，同时包含 canonical namespace 与薄兼容入口；
- ScienceFlow 品牌/Tool/Runtime 定向：Git 安装态 `48 passed`；
- ScienceFlow full suite：`1681 passed, 3 skipped, 2` 个既有 deprecation warnings；
- Tool Runtime 冻结 benchmark：schema/context/mechanism/error text/workspace 五类 diff 全为 `0`；
- quick runtime parity（4 jobs）：failed/context/mechanism/workspace diff 全为 `0`；
- `scienceflow agent tools list` 从 Git 安装的 InquiryCraft `v0.4.0` 正常输出；
- `uv.lock` 已从 `deepcraft-runtime v0.3.0@880fc90` 更新到
  `inquirycraft-runtime v0.4.0@dd18ff9`。

本阶段未重复运行耗时的真实 vLLM 三 seed 任务：冻结 Tool benchmark、runtime parity、完整
ScienceFlow 离线矩阵和 Git 安装态验证均已覆盖本次纯目录/品牌迁移；真实科学任务效果继续由
前一阶段已通过的 Circle Packing exact Resume/三 seed 门禁作为基线，下一次机制变化检查点再运行。

## 后续观察

1. GitHub 仓库显示名仍为 `DeepCraft`。创建或重命名远端为 `InquiryCraft` 后，只需更新两仓 URL、
   CI checkout 和 lock，不需要修改 runtime 行为。
2. 薄 `deepcraft` 兼容入口可在所有外部消费者迁移后删除；删除前需要单独的 import contract 审计。
3. ScienceFlow 全量 Ruff 仍有历史规范债务；本阶段未用大范围自动格式化混入品牌迁移，避免制造
   与运行机制无关的超大 diff。InquiryCraft 自身保持全量 Ruff/format 通过。
