---
name: expand-notes
description: Use when expanding rough academic notes into polished Quarto knowledge drafts, including LaTeX, lecture material, and research conversations.
---

# Expand notes into knowledge drafts

Turn source material into concise, self-contained `.qmd` notes at advanced-graduate rigor. Preserve the source's claims and mathematical detail; add missing explanation only when it can be grounded in a named source.

Write every new or rewritten QMD title, description, heading, paragraph,
formal-block label, and caption in English. Translate non-English rough notes
when rewriting them, but do not silently translate untouched human-authored
text. Chat responses may follow the user's language.

## Trust and scope

- Write new or substantially revised material under `drafts/` first, before any promotion into the trusted tree.
- Choose either one coherent article or a deliberate multi-page split. Do not fragment a topic only to shorten files.
- Never copy a paper's full text into `knowledge/`; papers and extracted source material remain external evidence under `literature/`.
- Do not edit a trusted page or its reading map until the user confirms the proposed destination.
- When the host supplies a native Zotero Note key, call `zotero_read_note` first. Treat its inert `qmdBody` as rough source material, then write the result under `drafts/`; never copy active Note HTML or create a parallel prompt workflow. If the result contains a non-null `qmdAuthorityMarker`, preserve that marker verbatim immediately after the Draft frontmatter. After writing the Draft, call `zotero_propose_note_from_qmd` with its safe relative path so one review can bind it to the existing source Note without duplicating or overwriting that Note.

## Knowledge page shape

Trusted frontmatter may contain only `title`, `description`, `categories`, and optional `aliases`. A content page declares exactly one category: `theory`, `experiment`, or `codes`. An `index.qmd` omits `categories` and contains exactly one `## Reading map` listing each direct child in the intended reading order.

Use `description` for a one-sentence account of what the page lets a reader understand or do. Keep the body synthetic: explain assumptions, derivations, limits, and cross-links rather than reproducing a source.

Use semantic formal blocks to organize mathematical narration whenever the
content warrants them:

- Introduce a reusable object, convention, or quantity in a definition block:
  `::: {#def-* .callout-note icon="false"}`.
- State an intermediate result that supports a later argument in a lemma
  block: `::: {#lem-* .callout-important icon="false"}`.
- State a central result in a theorem block:
  `::: {#thm-* .callout-important icon="false"}`.
- Put a substantial proof in
  `::: {#proof-* .callout-note collapse="true"}` immediately after the
  statement it proves.

Begin a formal block with `## (<descriptive name>)`; the anchor already carries the type, so do not repeat “Definition”, “Lemma”, or “Theorem” in the visible heading. Keep anchors unique.
Do not wrap ordinary exposition in a formal block merely for decoration.

## Draft-body boundary

Make every body paragraph teach the note's research topic. Do not write agent,
repository, review, or trust-state commentary into the QMD, including phrases
such as “this content comes from external literature,” “has not been promoted to
trusted knowledge,” “AI working copy,” or “the user asked.” Keep workflow status
in the agent response and review UI, outside the note.

Express provenance with a real Pandoc citation and, when useful, a verified
page locator. Do not add a placeholder source or trust disclaimer when a
citekey is unavailable; report the unresolved citation outside the QMD for
review. Author attribution, evidentiary limits, and source comparisons may
remain when they are themselves relevant academic content.

## Citations and review

Every citation must resolve in the single committed bibliography, `literature/ref.bib`. Use Pandoc citations such as `[@citekey]`; do not add page-local bibliographies. Verify formulas against source TeX or PDF rather than lossy extracted Markdown.

Before writing, present the proposed destination, page split, category, missing arguments, and sources. After writing, preview the draft when useful. After the user approves promotion, update the parent reading map and run:

```bash
make knowledge-check
```

Present the resulting diff. Only the user's merge makes the note trusted.

When the user requests a native Zotero Note mirror of an existing QMD Draft, keep the QMD as authority and call `zotero_propose_note_from_qmd`. The reviewed proposal, not this skill, owns the Zotero write.
