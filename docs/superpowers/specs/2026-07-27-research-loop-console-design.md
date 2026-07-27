# Research Loop 本地问题控制台设计

日期：2026-07-27  
状态：已批准，待实施计划

## 背景

Research Loop 的目标是实现 [quantum.harness issue #133](https://github.com/QuantumBFS/quantum.harness/issues/133) 所描述的 problem factory：自主生成可发表的量子多体研究问题，为每个问题预注册可执行 gate，求解问题，并最终通过同行评审。

当前网页虽然展示了 Discover、Verify、Solve、Publish 四个阶段，但本质上是一个以介绍为主的单页演示：数据硬编码在组件中，状态只保存在浏览器 `localStorage`，唯一主操作只是循环推进演示阶段。它不能管理真实问题，也不能启动问题生成流程。

本次改版将首页变成可使用的本地问题控制台，并建立从网页启动 Codex 对话、由 Codex 生成问题文件、再由网页读取问题的第一个完整闭环。

## 目标

- 让“问题”成为控制台的核心对象。
- 在主页查看全部问题及其从草稿到发表的生命周期状态。
- 用紧凑、可筛选的问题表代替宣传式首页。
- 通过“增加问题”按钮打开带有严格上下文的 Codex 对话。
- 由 Codex 在用户确认后把合格问题直接写入仓库。
- 保留自动和人工拒绝记录，以满足 issue #133 的审计要求。
- 让仓库中的问题文件成为唯一可信数据源，并由 Git 保留版本历史。
- 为未来的问题详情页、gate 执行、solver 运行和报告查看提供稳定数据边界。

## 非目标

- 本轮不设计或实现问题详情页中的 gate、solver、报告和发表操作。
- 本轮不实现多人账户、权限、数据库同步或并发编辑。
- 本轮不让主页直接推进问题状态、启动运行或删除问题。
- 本轮不实现完整 problem factory 后端；尚未接通的后续阶段只通过数据契约预留。
- 本轮不把派生索引作为第二份业务数据源。

## 用户与运行方式

第一版服务单个研究者，在本机仓库中运行。用户通过本地网页管理问题，通过 Codex 桌面应用完成问题生成对话。网页与 Codex 共享同一个仓库路径。

研究问题及其生成记录属于仓库内容，可以被 Git 检查、比较、提交和发布。浏览器本地存储不承载业务数据。

## 总体架构

```text
主页“增加问题”
       │ codex:// deep link（预填 prompt 与仓库 path）
       ▼
Codex 严格引导式对话
       │ 用户确认接受，或 rubric 判定拒绝
       ▼
problems/<problem-id>/
       │ schema 校验与确定性索引生成
       ▼
ProblemRepository
       │
       ▼
主页指标、筛选器与问题表
```

系统分为四个边界清晰的单元：

1. `Problem files`：保存结构化 manifest、完整研究说明和生成审计材料，是唯一可信数据源。
2. `Problem indexer`：扫描问题目录、校验 schema、隔离错误并生成确定性只读索引。
3. `ProblemRepository`：为 UI 提供稳定查询接口，使未来切换到文件加数据库的混合后端时无需重写页面。
4. `Codex launch`：构造新对话 deep link 和 fallback 提示词，不负责在浏览器内实现聊天。

## 生命周期

问题使用以下状态：

```text
draft
  → qualifying
  → accepted
  → solving
  → solved
  → publishing
  → published

draft 或 qualifying → rejected
任意非终态 → archived
```

界面对应显示为：草稿、资格验证中、已接受、求解中、已解决、投稿中、已发表、已拒绝、已归档。

第一版首页只读取和展示状态，不负责执行状态迁移。`rejected` 必须附带拒绝类型和原因；被拒绝对象不删除，默认筛选可以隐藏。`archived` 用于保留不再活跃但不应删除的记录。

## 问题文件契约

每个问题使用独立目录：

```text
problems/QMB-001/
├── problem.json
├── problem.md
└── generation/
    ├── initial-prompt.md
    ├── transcript.md
    └── decision.md
```

### `problem.json`

manifest 只保存程序需要的稳定字段，不复制长篇研究正文。第一版 schema 的完整公共字段为：

```json
{
  "schemaVersion": 1,
  "id": "QMB-001",
  "title": "问题标题",
  "summary": "一行研究目标摘要",
  "status": "draft",
  "gate": {
    "type": "interval-arithmetic",
    "readiness": "specified"
  },
  "provenance": {
    "sourceCount": 3
  },
  "lastActivity": {
    "summary": "问题草稿由 Codex 创建",
    "at": "2026-07-27T10:00:00Z"
  },
  "createdAt": "2026-07-27T10:00:00Z",
  "updatedAt": "2026-07-27T10:00:00Z"
}
```

除仅供 `rejected` 使用的 `rejection` 外，不接受未声明的顶层字段，以便尽早发现拼写错误和 schema 漂移。`gate.readiness` 的第一版允许值为 `missing`、`specified`、`executable` 和 `passed`。状态为 `accepted` 或更晚阶段的问题，gate 至少必须达到 `executable`；只有带有 runnable gate 的问题才能计入 issue #133 的 Tier 1。

当 `status` 为 `rejected` 时，manifest 还必须包含：

```json
{
  "rejection": {
    "kind": "automatic",
    "reason": "无法把成功标准表达为不可博弈的可执行 gate"
  }
}
```

`rejection.kind` 为 `automatic` 或 `human`。

### `problem.md`

人类可读的完整研究问题必须包含：

- 背景与文献缺口；
- 明确的研究目标；
- 为什么通过门槛值得形成论文；
- executable gate 的输入、判定规则和防博弈说明；
- novelty 依据与既有目录比较；
- provenance 来源；
- fresh evaluation 计划。

### `generation/`

- `initial-prompt.md` 保存启动此次生成流程的规范化提示词。
- `transcript.md` 保存与本问题生成直接相关的用户与 Codex 对话记录。
- `decision.md` 保存 rubric 检查结果、最终接受或拒绝结论、参与的人工 gatekeeping 行为及理由。

接受一个问题需要用户明确确认。自动或人工否决的候选仍应写入一个状态为 `rejected` 的问题目录，以确保拒绝可审计。

## 问题 ID 与索引

第一版使用仓库内递增的 `QMB-NNN` ID。创建前扫描所有 manifest，以最大现有序号加一生成候选 ID；写入前再次验证 ID 与目录均不存在。单用户本机模式不处理多进程同时创建问题。

索引器从 `problems/*/problem.json` 生成派生索引。排序必须确定：默认先按 `updatedAt` 降序，再按 `id` 升序。派生索引可以放入构建输出或被忽略的生成目录，但不能被人工编辑，也不能成为业务真相来源。

`ProblemRepository` 至少提供：

- `listProblems(filters)`；
- `getSummary()`；
- `getIndexDiagnostics()`。

首页只依赖这些接口，不直接理解文件扫描细节。

## “增加问题”Codex 流程

主页按钮使用 Codex 官方 deep link：`codex://threads/new`，并传入 URL 编码后的 `prompt` 与绝对仓库 `path`。Deep link 只预填输入框，不自动发送；用户仍需在 Codex 中确认发送。

预填提示词必须：

- 说明 issue #133 的总体目标和 5 个问题的成功标准；
- 要求 Codex 一次只询问一个问题；
- 依次检查文献依据、研究价值、novelty、可执行 gate 和 fresh evaluation；
- 对不能表达为代码 gate 的候选自动拒绝；
- 在写入前展示最终摘要、rubric 结果与文件清单；
- 要求通过候选只能在用户明确确认后写入；
- 要求拒绝候选写入完整拒绝原因和生成记录；
- 遵守本规格的问题目录与 schema；
- 写入后运行 manifest 校验并报告结果。

“增加问题”旁始终提供“无法打开 Codex？”入口，其中包含同一份可复制提示词、仓库路径以及手动打开 Codex 的简短说明。网页不依赖浏览器准确检测自定义协议是否启动成功，按钮不得成为唯一入口。

## 主页信息架构

主页去掉大面积宣传式 hero，保留现有米白、深绿和荧光绿的品牌识别，但采用更紧凑的工具型布局。

### 顶部栏

- Research Loop 品牌；
- 当前仓库或本地模式标识；
- 索引健康状态与最近更新时间。

### 目标概览

一条紧凑指标栏对应 issue #133 的三个成功层级：

- 全部问题；
- 已接受 `x / 5`；
- 已解决 `x / 5`；
- 已发表 `x / 5`；
- 已拒绝数量。

“已接受”计数包括 `accepted` 及其后续状态；“已解决”包括 `solved`、`publishing` 和 `published`；“已发表”只包括 `published`。

### 工具栏

- 页面标题“问题”；
- 按 ID、标题和摘要搜索；
- 多选状态筛选；
- 默认隐藏 `rejected` 和 `archived`；
- 主操作“+ 增加问题”。

### 问题表

每行代表一个问题，整行可以进入问题详情路由。列为：

1. 问题：ID、标题和一行摘要；
2. 状态；
3. Executable gate：类型和 readiness；
4. Provenance：来源数量；
5. 最近活动；
6. 更新时间；
7. 进入箭头。

本轮提供稳定的 `/problems/<id>` 路由，只展示问题 ID、标题以及“详情功能将在后续设计”的说明。主页不包含运行、验证、删除或状态推进操作。

### 页面状态

- 加载中：显示与表格结构一致的骨架；
- 空问题库：解释创建闭环并提供“增加第一个问题”；
- 筛选无结果：保留筛选器并提供清除操作；
- 索引错误：显示诊断摘要，不伪装为空问题库；
- 部分 manifest 损坏：合法问题继续显示，错误文件集中展示在“数据问题”区域。

## 数据流

### 读取

1. 本地开发进程或构建步骤运行索引器。
2. 索引器校验所有 manifest 并产生问题列表、汇总指标和诊断结果。
3. `ProblemRepository` 返回只读视图模型。
4. 首页进行搜索和筛选，不修改源文件。

### 创建

1. 用户点击“增加问题”。
2. 浏览器打开预填上下文的新 Codex 对话。
3. Codex 与用户完成严格 rubric 对话。
4. Codex 先准备完整目录内容，再根据接受或拒绝结论写入问题目录。
5. Codex 运行 schema 校验；失败则修复，不留下可被索引的半成品 manifest。
6. 文件监听触发索引重建；主页重新加载后显示新问题。

## 错误处理与完整性

- 每个 manifest 独立校验，单个错误不能阻断整个主页。
- 诊断必须包含相对文件路径、字段位置和可操作的错误消息。
- 重复 ID、目录名与 manifest ID 不一致、未知 schema version、非法状态和缺失条件字段均视为索引错误。
- `accepted` 及以后状态必须具备 readiness 为 `executable` 或 `passed` 的 gate、provenance 和完整 `problem.md`。
- `rejected` 必须具备拒绝类型与非空原因。
- Codex 创建时先生成完整内容并校验，再让最终 manifest 对索引器可见，以避免半成品进入主页。
- 网页不吞掉 deep-link 失败；fallback 必须让用户能继续工作。

## 可访问性与响应式设计

- 所有交互可通过键盘完成，并提供清晰焦点样式。
- 状态同时使用文字、图形或色调，不能只依赖颜色。
- 桌面使用语义化表格；窄屏转换为保持相同字段顺序的紧凑问题列表。
- 搜索和筛选具有可读标签及结果数量反馈。
- 动画遵守 `prefers-reduced-motion`。
- 色彩对比满足 WCAG AA。

## 测试策略

### 自动测试

- Schema：合法 manifest、全部状态、条件必填字段、非法 schema version。
- 索引器：多问题聚合、确定性排序、重复 ID、目录不一致、损坏 manifest 隔离和空目录。
- 汇总指标：Tier 1、Tier 2、Tier 3 与拒绝数量的准确计算。
- Deep link：prompt 与绝对路径的 URL 编码、fallback 内容一致性。
- 首页：搜索、状态筛选、默认隐藏拒绝与归档、空状态、无结果状态、部分错误和整行导航。
- 响应式与可访问性：语义、键盘焦点、非颜色状态表达和窄屏布局。
- 端到端冒烟：从 fixture 问题目录生成索引，启动站点，确认页面内容；加入问题 fixture 后确认索引更新。

现有 `tests/rendered-html.test.mjs` 仍在验证已经不存在的 starter loading skeleton，应替换为控制台的构建和渲染测试。

### 手工验收

1. 本地启动网页。
2. 点击“增加问题”。
3. 确认 Codex 打开在当前仓库，输入框已预填但未自动发送。
4. 完成一次通过 rubric 的最短生成对话并确认创建。
5. 确认目录符合 schema，刷新主页后问题、指标和筛选结果正确。
6. 完成一次拒绝路径，确认拒绝原因被保存且默认隐藏，可通过筛选查看。

## 实施边界与迁移

实现时保留现有 Next.js/vinext/Cloudflare 项目结构和品牌配色，但替换 `app/page.tsx` 中的演示状态机及其 `localStorage` 数据。针对本次功能增加聚焦的 schema、索引、repository、Codex link 和主页组件；不进行无关框架迁移。

如果未来加入实时 solver 运行、日志流或多人协作，可以在 `ProblemRepository` 后增加本地数据库索引和运行存储。问题研究材料仍保留在仓库中，主页组件不依赖具体存储实现。

## 完成标准

- 首页不再包含项目宣传 hero 或模拟推进按钮。
- 首页从真实 `problems/` 目录显示全生命周期问题表和正确 Tier 指标。
- 搜索、状态筛选、错误隔离、空状态和响应式布局可用。
- “增加问题”能打开正确仓库中的预填 Codex 对话，并有可靠 fallback。
- Codex 创建契约能够产出通过 schema 校验的问题或拒绝记录。
- `localStorage` 不再保存问题或流程状态。
- lint、构建、自动测试全部通过。
- 真实 deep-link 接受与拒绝路径各完成一次手工验收。
