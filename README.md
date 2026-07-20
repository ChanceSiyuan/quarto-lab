# quarto-lab 研究工作流

这个仓库是一个 Quarto 数字花园(量子计算研究笔记),同时装载了一套 agent
技能(`skills/` + `Ion.toml`)。本 README 记录这套技能如何嵌入日常研究
工作流,供自己参考。

习惯基线:**看论文 → 在 AI chat 里边读边问 → 边写 Quarto note**。
这个循环本身不需要任何技能;技能只在**阶段转换处**触发——筛选、入库、
补洞、构建、开题。

---

## 核心循环

```
┌─ ① 筛选 ──── screen-paper ──── "这篇值得读吗?"
│
├─ ② 入库 ──── download-ref ──── 全文落地,之后的问答有据可查
│
├─ ③ 读+问+写 ── (普通 chat) ──── 推导没验证就写 (t.b.c.),不中断阅读
│
├─ ④ 补洞 ──── complete-gaps ─── 用聊天记录把 (t.b.c.) 补成严格证明
│
├─ ⑤ 构建 ──── render-site ───── DGX 渲染,导航自动生成
│
└─ ⑥ 开题 ──── generate-issues ── note → 3–5 个 research issue → 回到 ①
```

### ① 筛选:`screen-paper`

> "帮我筛一下 arXiv:2507.12345,值不值得深读?"

按组内框架(中性原子/Rydberg 平台、错误缓解与哈密顿演化方向、避开
红海和 QA)出三档结论:**Pass / Skim / Deep Dive**。Deep Dive 附
1–2 句"值得复现什么"。

### ② 入库:`download-ref`

> "把 2002.08953 pull 进 shadow-tomography 参考库"

写 `.knowledge/literature/ref.bib`(`keywords = {shadow-tomography}`
钉住主题)→ 下 PDF → 渲染成 markdown → 重建 `INDEX.md`。主题槽位
对应 `theory/` 各节(见技能内的槽位表)。

关键收益:之后在 chat 里问"第三节的 variance bound 为什么是
$3^w$",agent 直接读本地渲染的全文回答,而不是凭训练记忆猜。

### ③ 读 + 问 + 写:普通 chat,零技能

照常提问、照常在 `theory/<Section>/xxx.qmd` 里记笔记。唯一的习惯
约定:**跳过的代数、没验证的推导,直接写 `(t.b.c.)` 或 `(todo:...)`
占位**,别中断阅读去补细节。占位符是给 ④ 留的钩子。

### ④ 补洞:`complete-gaps`

> "用今天这段聊天记录,把 draft.qmd 里的三处 (t.b.c.) 补完"

Mode A 的输入就是 chat 记录:批判性筛选其中的推导(取对的、丢冗余、
升级严谨度),先给补全大纲、确认后才动笔。外科手术式:不动结构,只
填证明、补隐含定理块(`::: {#thm-* .callout-important}`)、更新
`refs.bib`。完成后 `grep "t.b.c." <file>` 应为空。

如果起点是零散 bullet 而非带洞草稿,用 `expand-notes`(整篇扩写,
支持 tex 拆分成多篇)。

### ⑤ 构建:`render-site`

> "渲染一下,确认新 note 没问题"

本机是 SSH 挂载拷贝,渲染慢到不可用;技能会自动走 DGX:

```sh
ssh chance@100.106.69.117 'bash -lc "export PATH=$HOME/.local/bin:$PATH \
  && cd ~/quarto-lab && quarto render theory/<Section>/<note>.qmd"'
```

导航、侧栏、小节索引由 pre-render 钩子(`scripts/update_theory_nav.py`)
自动生成——`AUTO` 标记块永远不要手改。

### ⑥ 开题:`generate-issues`

> "读一下这篇 note,开几个 research issue"

强制联网搜文献(含跨领域:纯数学/CS 连接)后,按仓库的 issue 模板
提 3–5 个方向:推广 / 补严格证明 / 文献撞车对比 / 模拟任务。产出的
issue 又成为下一轮"读什么"的输入。

---

## 一天示例

```
早上刷 arXiv 看到一篇多拷贝 shadow tomography 的文章

→ "screen 一下这篇"                          [screen-paper → Deep Dive]
→ "pull 进 shadow-tomography 库"             [download-ref → 全文落地]

下午边读边问:
→ "他的 4-copy 电路和 nonlocal_multicopy.qmd
   里的构造等价吗?"                          [普通 chat;agent 同时读
                                              对方全文 + 我的旧 note]
→ 随手记 theory/Shadow_tomography/new_note.qmd,
   跳过的代数写 (t.b.c.)

晚上:
→ "用今天的聊天把 t.b.c. 补完"               [complete-gaps → 大纲 → 确认 → 成稿]
→ "渲染验证"                                 [render-site → DGX]
→ "开 issue"                                 [generate-issues → 下一轮输入]
```

---

## 低频流程

| 场景 | 技能 | 示例 |
|---|---|---|
| 会议季扫 oral | `conference-survey` | "扫一下 DAMOP 2026 archive 里 tweezer array 相关 oral,输出到 theory/Dynamics/" → 中文推荐 qmd + TSV 审计表 |
| 系统文献综述 | `survey`(sci-brain) | 建 BibTeX KB 于 `.knowledge/`;可接 `download-ref --from-bib` 批量抓 PDF |
| 综述后头脑风暴 | `ideas` → `idea-writer` | 基于 survey KB 的双 agent brainstorm → 写成结构化 proposal |
| note 成熟要写稿 | `integrate-paper` | "把 theory/compatibility 的结果装进 main.tex 的 sec3" — 会先问哪些 note 结论已被推翻,再做 qmd→revtex 迁移 |
| 查包 API | `context7-cli` | 需要 node,只在笔记本侧跑 |

---

## 技能速查

**本地技能**(源码在 `skills/`,已提交):

| 技能 | 触发场景 |
|---|---|
| `screen-paper` | 论文相关性快筛,出三档结论 |
| `download-ref` | arXiv/DOI/PDF 入文献库(含 `--from-bib` 批量模式) |
| `expand-notes` | 零散笔记/tex → 成篇 Quarto reading note |
| `complete-gaps` | 补 `(t.b.c.)`/`(todo:*)`,外科手术式 |
| `integrate-paper` | qmd 结果 → LaTeX 手稿 |
| `generate-issues` | note → research issues |
| `conference-survey` | 会议 oral 扫描triage |
| `render-site` | 渲染/预览/导航,自动走 DGX |

**第三方**(版本钉在 `Ion.lock`):`survey`、`ideas`、`idea-writer`、
`researchstyle`、`review-writer`、`paper-writer`(sci-brain 系);
`arxiv-search`、`context7-cli`(需 node)、`scientific-visualization`。

---

## 基础设施备忘

- **两份拷贝**:笔记本侧 `/home/chance/dgx/quarto-lab`(SSH 挂载,
  文件操作慢)与 DGX `~/quarto-lab`(工具链完整)。渲染在 DGX;
  技能安装在笔记本(DGX 无 `ion`/`node`)。
- **技能布局**:`skills/` 是本地技能源码;`scripts/install_skills.sh`
  生成两份**真实副本**(无符号链接,均 gitignore):`.claude/skills/`
  给 Claude Code,`.agents/skills/` 给 Codex(原生 Agent Skills 发现,
  已实测)。改完本地技能后重跑该脚本。两个 CLI 共享同一套工作流。
- **文献库**:`.knowledge/literature/<topic>/`,`ref.bib` 为库的
  source of truth;站点引用走各节 `refs.bib`(无者用根
  `references.bib`),cite key 双方一致(`lastname_year_firstword`)。
- **旧提示词**:`_instructions/` 保留作档案,内容已技能化。
- **README.md 与 `skills/` 已在 `_quarto.yml` 中排除渲染**,不会
  出现在网站上。
