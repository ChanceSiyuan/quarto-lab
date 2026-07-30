---
name: conference-survey
description: Use when surveying a conference archive's oral presentations for a topic, prioritizing talks to read, or auditing a conference program from an archive link.
---

# Conference Survey

Scout a conference frontier from an archive URL and a topic. Produce
prioritized Chinese triage, not an exhaustive prose summary.

## Outputs

Write durable, untrusted files under one directory per conference:
`drafts/conference/<conference>/`. The parent `drafts/conference/` tree remains
outside trusted knowledge, and multiple topic audits for the same conference
share that conference directory.

- `<slug>.qmd` — recommendation article;
- `<slug>_review.tsv` — page-by-page audit;
- `<slug>_review_summary.txt` — counts and limitations;
- `<slug>_presentations.json` — scrape cache when enumeration is expensive.

Keep `drafts/conference/index.qmd` and the conference's own `index.qmd` linked
to the new article. Every QMD frontmatter contains exactly `title`,
`description`, and one `categories` value chosen from `theory`, `experiment`,
or `codes`. Do not add a page-local bibliography or Quarto project file: every
QMD inherits execution-disabled preview settings and `literature/ref.bib` from
`drafts/_quarto.yml`.

Never write a conference survey directly into `knowledge/`.

## Workflow

1. Enumerate every session and every presentation from the archive root.
   Determine oral status from each page's own label and record the total before
   topic filtering.
2. Read every oral's title, session, abstract, authors, and page references.
   Assign exactly one decision:
   `included_in_topic_abstract`, `related_excluded`, or `unrelated_excluded`.
3. Match scientific intent rather than literal keywords. Include live
   questions, capabilities, protocols, and bottlenecks; exclude incidental
   hits, duplicates, and overly broad talks. Prefer `related_excluded` when
   uncertain.
4. For each included talk, explain in Chinese what was done, what was measured
   or engineered, why it matters, and why it should be read early. Follow each
   block with `参考链接：` containing the oral page and supporting references.
5. Make the TSV IDs stable and human-readable. Ensure its counts agree with
   the summary and every included ID appears in the QMD.
6. Remove placeholders and preview the article:

```bash
make draft-preview FILE=drafts/conference/<conference>/<slug>.qmd
```

Report output paths, decision counts, inaccessible pages, and other audit
limitations. Promotion is a later `review-draft` workflow.
