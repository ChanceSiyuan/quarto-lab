# Quarto Lab：人和 Agent 共读的研究知识库

这个仓库现在把 Quarto 数字花园明确分成三个物理边界：

```text
theory/                    已由用户认可的可信知识
drafts/                    未完成或尚未审阅的草稿
conference/                会议筛选与临时笔记（同样不可信）
.knowledge/literature/     外部证据，不等于已经学会的知识
```

当前阶段只实现“可信知识的读取、验证、解析和发布”。自动研究、自动
结题、自动 promotion，以及新的文献抓取系统都留在后续阶段。

## 快速开始

需要 Python 3.11、Quarto 1.9.38，以及仓库 `.venv` 中由 `uv.lock`
固定的 Python 依赖。

```bash
make help
make knowledge-check
make knowledge-resolve QUERY="triangular TFIM"
make knowledge-build
make knowledge-preview
make test
```

兼容入口 `./scripts/render_site.sh` 等价于 `make knowledge-build`。
不要直接运行 `quarto render`：安全入口会在临时目录中构建固定配置，
同时通过配置和 `--no-execute` 两次禁用代码执行。

## 一棵图，两种读者

`theory/` 既是人类浏览的 Quarto 内容树，也是 agent 唯一能当作已学
知识读取的来源。每个 topic 的 `index.qmd` 包含一个
`## Reading map`，按顺序列出全部直接内容页与子 topic：

```markdown
## Reading map

- [Preliminaries](preliminaries.qmd)
- [Nested topic](nested/index.qmd)
```

这个顺序同时生成 Quarto sidebar 和 agent 的 Reading Bundle，不再
存在 `_sidebar.yml`、`_metadata.yml`、AUTO 区块或另一份 agent 索引。

Agent 查询示例：

```bash
make knowledge-resolve QUERY="triangular TFIM"
```

返回值有三种状态：

- `match`：agent 必须依次读取 `bundle.orderedFiles`；
- `ambiguous`：把候选 topic 交给用户，不可静默任选；
- `no-match`：明确说明本地已学知识没有覆盖，再另行发起外部研究。

Resolver 不会搜索 `drafts/`、`conference/` 或 literature。
Agent 侧的同名流程封装在 `skills/read-knowledge/`，其职责只有解析并
按顺序读取，不会写入或自动 promotion。

## 验证规则

`make knowledge-check` 会确定性检查：

- 每个含 QMD 后代的目录都有 `index.qmd`；
- 每个 topic 恰有一个 Reading map，且直接子项不缺、不重、不越级；
- Related topics 只指向可信 index；
- frontmatter 使用严格白名单，页面不能覆盖 execution、format、
  filters、includes 或 resources；YAML 解码后的 metadata 也不能包含
  HTML；
- 本地链接、图片、bibliography 不缺失、不越出可信边界、不经过
  symlink；非 QMD 依赖必须是 allowlisted 普通文件，SVG 内容会在
  `knowledge-check` 阶段审计；
- raw HTML anchor、image、media/resource URL 也参与同一 scheme、路径与
  缺失资源验证，只认可 HTTP(S)/mailto 外链；
- 禁止 script、事件处理器、iframe/object/embed、form、meta refresh
  以及会加载网络资源的 CSS 等 active HTML；
- 整个正文（包括 inline/fenced code）、raw HTML、YAML 解码后的
  frontmatter 和基础配置中都禁止 Quarto shortcode，避免
  include/embed/env 绕过临时投影或读取构建环境；
- diagnostics 按文件、行、列和代码稳定排序。

2026-07-28 的迁移快照包含 136 篇可信 QMD、37 个 topic、48 篇 draft
和 10 篇 conference note。具体判定与逐文件迁移记录见
[`docs/migrations/2026-07-27-incomplete-theory-drafts.md`](docs/migrations/2026-07-27-incomplete-theory-drafts.md)。

## 安全构建

`make knowledge-build` 执行：

1. 加载并完整验证 KnowledgeGraph；
2. 把根 `index.qmd` 作为非知识的站点外壳单独严格验证；
3. 在 `work/` 下建立同文件系统的临时 Quarto project；
4. 严格重建 `_quarto.yml`，不透传 Pandoc/Lua filter、hook、extension
   或任意 include；
5. 只复制可信 QMD、实际引用的资源、bibliography 与经审计的固定站点
   资源；
6. 从 Reading maps 生成 sidebar；
7. 使用参数数组运行 `quarto render . --no-execute`；
8. 检查输出根和子项都不是 symlink，且没有 QMD、BibTeX、draft、
   conference、notebook、cache、Lua filter 或源码脚本；
9. 仅在全部成功后原子替换 `_site/`，失败时保留上一版站点。

根 `index.qmd` 只帮助人类进入站点，不属于 `theory/`，不会进入
KnowledgeGraph 或任何 agent Reading Bundle。

`_site/` 和 `work/` 都是生成物，不要手工编辑或提交。

## Agent skills

`skills/` 是本仓库 skill 的唯一源码。`Ion.toml` 与 `Ion.lock` 对第三方
skill 使用精确 revision；`./scripts/install_skills.sh` 会先在隔离目录
安装并复核 lock/产物，再以可回滚事务同步到 `.agents/skills/` 和
`.claude/skills/`。两个 consumer 目录都是可再生副本，不是源码。

## Draft promotion

草稿可以由人或 agent 阅读、评论和完善，但它在 `drafts/` 或
`conference/` 中始终不可信。只有用户明确确认后，才可：

1. 在非 `main` 分支把内容整理为 `.qmd`；
2. 放入一个现有或新建的 `theory/<topic>/`；
3. 更新父 topic 的 Reading map；
4. 运行 `make knowledge-check` 与 `make knowledge-build`；
5. 提交 diff 供用户合并。

目录移动、agent 声称完成或单纯渲染成功都不构成 promotion。

## 代码结构

```text
lib/knowledge/
  parser.py       QMD/frontmatter/Markdown 解析
  graph.py        可信树与 Reading-map 图
  targets.py      URL/本地路径的统一词法分类
  validate.py     完整、稳定的边界诊断
  resolve.py      确定性查询与 Reading Bundle
  quarto.py       临时安全 Quarto 投影
  site.py         no-execute render、审计、原子发布
scripts/knowledge.py
Makefile
```

设计术语与决定见 [`CONTEXT.md`](CONTEXT.md) 和
[`docs/adr/`](docs/adr/)。部署不在当前工作流内；执行任何部署前先询问
用户。
