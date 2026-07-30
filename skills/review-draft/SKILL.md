---
name: review-draft
description: Use when the user names one note under `drafts/` and wants it reviewed, corrected, placed, or promoted into the trusted knowledge tree — "review this draft", "where does this note belong", "get this into the knowledge base", "is this ready to promote".
---

# review-draft

## Overview

`drafts/` is untrusted: imported cards, pasted notes, whatever an agent wrote.
A review moves one note toward `knowledge/` by telling the user what is wrong
with it and where it would belong — and by changing nothing until they say so.

## Input

Accept exactly one file under `drafts/`, named by the user. Refuse a directory,
a glob, or more than one file, and refuse any path outside `drafts/`; ask the
user to name one note. To read it rendered:

```bash
make draft-preview FILE=drafts/<path>.qmd
```

## The report

Report exactly four sections, in this order, and nothing else — no summary, no
provenance audit, no rewritten copy:

1. **Language and grammar** — spelling, grammar, and unclear or ambiguous sentences, as locations with suggested wording.
2. **Factual errors or uncertainty** — claims that are wrong, unsupported, missing a condition, or in conflict with another note, each with how certain the objection is.
3. **Quarto and Markdown format** — broken syntax, math that will not render, links that will not resolve, raw HTML.
4. **Placement recommendation** — exactly three labelled lines:
   - *Destination*: exactly one destination — either an existing `knowledge/<topic>/<filename>.qmd`, or one new topic directory `knowledge/<topic>/` carrying its own `index.qmd`, plus the filename for this note.
   - *Category*: exactly one category for a content page — `theory`, `experiment`, or `codes`. A topic `index.qmd` has none.
   - *Reason*: one sentence.

Do not edit, move, split, rewrite, or promote the note before the user confirms
the destination and the category. The recommendation is text in the
conversation; the repository stays untouched until they answer.

## After the user confirms

1. Create or switch to a non-`main` branch.
2. Convert the note to `.qmd` at the confirmed destination, adding only the allowed frontmatter: `title`, `description`, `categories`, `aliases`.
3. Add the page to the parent index's `## Reading map` — a page nothing links to is an orphan and fails validation. A new topic directory needs its own `index.qmd` with a `## Reading map` of its own, listed in its parent's.
4. Apply the corrections the user approved, and only those.
5. Validate the tree:

   ```bash
   make knowledge-check
   ```

6. Present the change as a Git diff or pull request, and stop. Only the user's merge makes the note trusted knowledge.

Leave the original in `drafts/`. The migration manifest checksums the imported
cards, and removing one is a separate decision for the user.

## Red flags — stop and ask

- Recommending two destinations "so the user can choose": choose one and give the reason.
- Editing the note while reviewing it, or promoting it in the same turn as the review.
- Promoting onto `main`, or merging the branch after opening it.
- Adding frontmatter beyond the four allowed keys to make something render.
