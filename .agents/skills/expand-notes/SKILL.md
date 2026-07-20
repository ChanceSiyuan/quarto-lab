---
name: expand-notes
description: Use when the user provides rough academic notes, a LaTeX document, or lecture material to be expanded into polished Quarto reading notes — "expand these notes", "turn this into a post", "split this tex into qmd notes", "generate an article from my notes".
---

# expand-notes

Expand incomplete academic notes into professional Quarto (`.qmd`) reading
notes plus a unified BibTeX file, at advanced-graduate rigor. The reader is a
quantum computing PhD student: skip basic overviews, keep the tone strictly
academic, and favor mathematical depth.

<example name="activate good">
User: "Expand theory/Magic/rough_notes.tex into reading notes." → expand-notes fires (Scope A).
</example>

<example name="activate not-applicable">
User: "Fill in the (t.b.c.) gaps in this draft." → use `complete-gaps` instead (surgical completion, not expansion).
</example>

## Scope: choose ONE

- **Scope A — multi-file split.** Split a `.tex` document into distinct
  `.qmd` files per chapter/section, each with YAML frontmatter.
- **Scope B — single article.** Produce one `.qmd` survey article from the
  notes; no splitting.

Output lives in the matching section dir `theory/<Section>/` (create one if
the topic is new). Navigation and section indexes are generated — see
`render-site`; do not hand-edit generated nav blocks.

## House frontmatter

```yaml
---
categories:
- Readings
date: 'YYYY-MM-DD'
lang: en
title: <Title>
bibliography: refs.bib
---
```

`refs.bib` is the section-local bibliography, next to the note.

## Core directives

1. **Content expansion & gap-filling.** Expand existing concepts line-by-line
   into complete, self-consistent narratives. Actively search the literature
   for the missing frameworks and arguments; synthesize, don't paraphrase.
2. **Formal blocks.** Compact critical statements into Quarto Divs:
   - Definitions: `::: {#def-* .callout-note icon="false"}`
   - Lemmas: `::: {#lem-* .callout-important icon="false"}`
   - Theorems: `::: {#thm-* .callout-important icon="false"}`
   - Proofs: `::: {.callout-note collapse="true"}` — if lengthy but standard,
     cite precisely instead of proving.
3. **Reference management.** One unified section `refs.bib` covering all
   output documents; extract existing references and add every newly cited
   paper (Google Scholar–standard BibTeX). Cite inline with `@key`.
4. **Strict grounding.** Every concept, theorem, or expansion must trace back
   to the source notes or to a specific cited paper. No decorative content.

## Workflow

1. Read the source; identify incomplete sections.
2. Present a brief structural outline FIRST: proposed filenames/sections,
   gaps and expansion plan, preliminary list of papers to search and cite.
3. **Wait for confirmation on the outline before writing the full files.**
4. Write the `.qmd` file(s) and `refs.bib`.
5. Verify: render the new file(s) (`render-site`), confirm citations resolve
   and formal-block anchors (`#def-*`, `#thm-*`) are unique.
