---
name: read-knowledge
description: Use when answering a research question about this repository — before stating a research fact, definition, parameter value, benchmark number, or interpretation that the learned knowledge might already cover, and before summarising what is known about a model, method, or code.
---

# read-knowledge

## Overview

`knowledge/**/*.qmd` is the only trusted answer source here, and the resolver is
the only supported way to find the pages that answer a question. Grepping the
tree, recalling a previous session, and remembering the physics from training
data all answer from something that is not the learned knowledge.

**The rule: resolve, read the whole bundle, then answer.**

## Resolve

```bash
make knowledge-resolve QUERY="<the user's research question>"
```

Pass the user's question, not a keyword distilled from it. The command prints
one JSON document and exits 0 for every outcome: `status` is an answer, not a
failure.

## Act on `status`

| `status` | Required action |
|---|---|
| `match` | Read every path in `bundle.orderedFiles`, in the given order, before answering. |
| `ambiguous` | Present every entry of `alternatives` — page, topic, title — and ask which one the user means. |
| `no-match` | Say that the learned knowledge has no match for this question. |

Every path includes the ancestor `index.qmd` files. An index carries the scope
and the caveats under which its content pages hold, so a content page read
alone can be quoted out of the conditions it is true in. Answer only from what
those files say, and name the pages the answer came from.

Never pick between the entries of `alternatives` silently: candidates in two
topics are two different research objects, and choosing is the user's call.

## What is never an answer source

- **Never read `drafts/`** to fill a gap. It is imported, unreviewed material; nothing in it has passed validation or user review, and "it came from our own harness" does not make it a repository claim.
- **Never read `literature/`** as learned knowledge. It is external evidence; quoting it as a conclusion of this repository launders a paper into a finding.
- Neither tree is a trusted fallback, in whole or in part. `no-match` is not permission to reach for them.

After `no-match`, say so plainly and stop there. Only if the user then asks for
more, enter a separately named workflow and label its output as external
evidence rather than learned knowledge:

- `download-ref`, to add a paper to `literature/`;
- an announced external-research or source-audit pass — web search, reading a
  paper, background knowledge — stated as such in the same breath as the claim.

## Red flags — stop and resolve

- About to state a benchmark number, a critical point, or "we concluded …" with no resolver run in this session.
- About to `grep`, `ls`, or `find` under `knowledge/`, `drafts/`, or `literature/` to locate an answer.
- About to write "the repository does not cover this, but the literature says …" as one answer.
- Read some of `bundle.orderedFiles` because the rest "looked like navigation".

## Rationalisations

| Excuse | Reality |
|---|---|
| "The tree is small, the answer is visible." | Then the resolver costs one command. The observable call is the point, not the search. |
| "The draft says it, and we wrote the draft." | Imported is not reviewed. Only a merged page under `knowledge/` is a repository claim. |
| "The paper in `literature/` is authoritative." | It is authoritative about itself. This repository has concluded nothing from it. |
| "I resolved this topic earlier." | Resolve again. The trusted tree changes between sessions and a bundle is cheap. |
| "This is standard physics, not a repository claim." | Then report the `no-match` and label the claim as external knowledge. |
| "The index pages are only navigation." | Indexes carry the scope their content pages are true in. Read every file in the bundle. |
