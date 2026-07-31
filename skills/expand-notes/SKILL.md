---
name: expand-notes
description: Use when expanding rough academic notes into polished Quarto knowledge drafts, including LaTeX, lecture material, and research conversations.
---

# Expand notes into knowledge drafts

Turn source material into concise, self-contained `.qmd` notes at advanced-graduate rigor. Preserve the source's claims and mathematical detail; add missing explanation only when it can be grounded in a named source.

## Trust and scope

- Write new or substantially revised material under `drafts/` first, before any promotion into the trusted tree.
- Choose either one coherent article or a deliberate multi-page split. Do not fragment a topic only to shorten files.
- Never copy a paper's full text into `knowledge/`; papers and extracted source material remain external evidence under `literature/`.
- Do not edit a trusted page or its reading map until the user confirms the proposed destination.
- When the host supplies a native Zotero Note key, call `zotero_read_note` first. Treat its inert `qmdBody` as rough source material, then write the result under `drafts/`; never copy active Note HTML or create a parallel prompt workflow. If the result contains a non-null `qmdAuthorityMarker`, preserve that marker verbatim immediately after the Draft frontmatter. After writing the Draft, call `zotero_propose_note_from_qmd` with its safe relative path so one review can bind it to the existing source Note without duplicating or overwriting that Note.

## Knowledge page shape

Trusted frontmatter may contain only `title`, `description`, `categories`, and optional `aliases`. A content page declares exactly one category: `theory`, `experiment`, or `codes`. An `index.qmd` omits `categories` and contains exactly one `## Reading map` listing each direct child in the intended reading order.

Use `description` for a one-sentence account of what the page lets a reader understand or do. Keep the body synthetic: explain assumptions, derivations, limits, and cross-links rather than reproducing a source.

For formal statements, retain the quarto-lab conventions:

- definition: `::: {#def-* .callout-note icon="false"}`
- lemma or theorem: `::: {#lem-* .callout-important icon="false"}` or `#thm-*`
- long proof: `::: {.callout-note collapse="true"}`

Begin a formal block with `## (<descriptive name>)`; the anchor already carries the type, so do not repeat “Definition”, “Lemma”, or “Theorem” in the visible heading. Keep anchors unique.

## Citations and review

Every citation must resolve in the single committed bibliography, `literature/ref.bib`. Use Pandoc citations such as `[@citekey]`; do not add page-local bibliographies. Verify formulas against source TeX or PDF rather than lossy extracted Markdown.

Before writing, present the proposed destination, page split, category, missing arguments, and sources. After writing, preview the draft when useful. After the user approves promotion, update the parent reading map and run:

```bash
make knowledge-check
```

Present the resulting diff. Only the user's merge makes the note trusted.

When the user requests a native Zotero Note mirror of an existing QMD Draft, keep the QMD as authority and call `zotero_propose_note_from_qmd`. The reviewed proposal, not this skill, owns the Zotero write.
