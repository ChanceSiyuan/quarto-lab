---
name: conference-survey
description: Use when surveying a conference archive's oral presentations for a topic — "survey the DAMOP orals on X", "which talks should I read", given a conference archive link plus a topic/keyword list.
---

# conference-survey

Conference-frontier scouting: from a conference archive link and a topic,
identify which oral presentations are worth reading first and explain why in
concise Chinese. The goal is prioritized triage, not exhaustive collection.

<example name="activate good">
User: "Survey https://meetings.aps.org/.../DAMOP25 orals for Rydberg error mitigation → theory/Virtual_Distillation/." → conference-survey fires.
</example>

<example name="activate not-applicable">
User: "Survey the literature on virtual distillation." → use the sci-brain `survey` skill (paper KB survey, not a conference archive).
</example>

## Inputs

```text
conference_link: [URL of the conference archive]
topic: [keywords, research direction, or selection criterion]
output_dir: [where outputs go]
optional_output_slug: [filename stem; infer from topic if omitted]
optional_template_qmd: [existing .qmd whose structure should be copied]
```

Given the first three, proceed without follow-up questions unless the archive
is inaccessible or the output dir ambiguous.

## Outputs (all durable, in `output_dir` — never only /tmp)

```text
{slug}.qmd                    # Chinese recommendation article
{slug}_review.tsv             # page-by-page audit table
{slug}_review_summary.txt     # audit summary
{slug}_presentations.json     # scrape cache (if scraping is expensive)
```

## Core directives

1. **Full universe.** Enumerate every session and every presentation page
   from the archive root; decide which pages are actually orals from the
   page's own type/label when available; record the total oral count before
   filtering.
2. **Read and classify every oral** — title, session, abstract, authors, and
   the references already listed on the page (not just keyword hits) — into
   exactly one of `included_in_topic_abstract` / `related_excluded` /
   `unrelated_excluded`. Preserve the distinction between "topic-adjacent
   but not recommended" and "truly unrelated"; when in doubt,
   `related_excluded`.
3. **Topic matching is intent-based**, not keyword-literal: include talks
   that reveal live scientific questions, capabilities, protocols, or
   bottlenecks for the topic; exclude incidental keyword hits, talks too
   broad to guide reading, duplicates covered by a stronger block, and tool
   talks without clear topic relevance.
4. **Search for understanding, not decoration.** Prefer references already on
   the oral page; then arXiv/journal/review articles. No padding.
5. **Chinese blocks, fast triage.** Each recommended block answers: what is
   done, what is measured/simulated/engineered, why it matters for the topic,
   why read it early — followed by a `参考链接：` list (oral page + refs).

## Article skeleton (when no template qmd given)

```markdown
---
categories:
- reviews
date: 'YYYY-MM-DD'
description: '[conference + topic description]'
lang: zh
title: '[conference]: [topic] oral 推荐'
---

# Summary and questions
[Scope, total oral count, inclusion standard, field-level trends, 2-3 priority reads per category.]

# 核心摘要
## SESSION/PAGE: 中文短标题
[Chinese block]
参考链接：
- [oral SESSION/PAGE](...)
- [paper/reference](...)
```

## Audit files

TSV columns (at least):
`id  decision  reason_cn  tags  session  title  url  publication  abstract_short`
— `id` stable and human-readable (e.g. `B03/4`); `reason_cn` explains the
decision in Chinese.

Summary txt: source archive + cache location, total orals, count per
decision, and the `related_excluded` list with one-line reasons.

## Validation (before reporting)

<checklist name="verify-survey">
- No placeholder text (`TODO`, `待补`, `PLACEHOLDER`) in the .qmd
- Every block has a `参考链接：` section
- Every `included_in_topic_abstract` ID in the TSV appears in the .qmd
- The .qmd renders (see `render-site`); never edit `_site/` directly
- Counts in the summary txt match the TSV
</checklist>

Report output paths, counts per decision, and any verification limitations.
