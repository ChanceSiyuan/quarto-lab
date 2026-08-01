---
name: complete-gaps
description: "Use when a draft QMD contains `[todo: ...]` placeholders, skipped derivation steps, incomplete proofs, or rough passages that need rigorous local completion, including the Zotero Complete TODOs action."
---

# Complete Gaps

Complete a Quarto draft surgically without restructuring its argument. Work in
`drafts/` or a user-named project workspace. If the source is trusted
`knowledge/`, copy the relevant material into `drafts/` and leave the trusted
`knowledge/` page unchanged.

Write every new or rewritten QMD heading, paragraph, formal-block label, and
caption in English. Do not silently translate untouched human-authored text.
Chat responses may follow the user's language.

## Choose one evidence mode

- **Conversation mode:** extract the user's intended argument; independently
  check assistant-proposed derivations and discard unsupported steps.
- **Paper mode:** use the pinned LaTeX or PDF evidence beside a literature
  record. Verify formulas against source, not lossy transcription.

## Workflow

1. Inventory each explicit placeholder and each implicit logical gap.
2. Propose a per-gap completion plan: derivations, required external sources,
   formal blocks, and bibliography additions.
3. Obtain explicit approval for that plan before writing.
4. Replace every requested gap with a self-contained derivation. Preserve
   existing headings, notation, Quarto Div syntax, and narrative order.
5. Add a missing definition, lemma, or theorem only when the argument requires
   it. Use a stable `#def-*`, `#lem-*`, or `#thm-*` anchor and place a short
   proof in a collapsed callout.
6. Put new references in a draft-local bibliography. Never edit
   `literature/ref.bib` or a bibliography under `knowledge/` silently.
7. Confirm that no requested placeholder remains, citations resolve, and the
   exact draft previews safely:

```bash
make draft-preview FILE=drafts/<path>.qmd
```

Present the final diff. Promotion into `knowledge/` is a separate
`review-draft` action and requires later explicit approval.

## Zotero Complete TODOs mode

When the request declares `Action: complete-todos` and `Mode: todo-only`, treat
the toolbar click as approval for the placeholder replacements only:

1. Read the complete active private working copy before editing.
2. Find every literal `[todo: ...]` placeholder and process them in source
   order. Do not invent additional gaps or expand the task beyond them.
3. Replace only the exact byte span occupied by each placeholder. Preserve
   every byte outside those spans, including frontmatter, headings, blank
   lines, whitespace, citations, formulas, anchors, and Quarto Div fences.
4. Write each replacement in English. Use the surrounding notation and
   evidence already available in the dedicated conversation. Never add
   workflow commentary, trust-state notices, or review instructions to QMD.
   Format every formula using the Renderable math contract in
   `skills/expand-notes/SKILL.md`.
5. Do not edit `knowledge/`, `literature/`, the original Draft, or any file
   other than the supplied private working-copy path.
6. If a placeholder cannot be completed without guessing, leave that exact
   placeholder unchanged and report the blocker in chat. Do not compensate by
   changing nearby prose.
7. Keep the running action observable without exposing private reasoning:
   first report how many placeholders were found, then publish one short
   progress update per placeholder (`Completing TODO i/n: <brief topic>`).
   Report actions and outcomes only; never reveal hidden chain-of-thought.
8. Do not ask for a second approval. Save the working copy once, then report
   which placeholders were completed or left unresolved.

The Zotero host verifies byte-for-byte that non-placeholder content did not
change and rejects the working copy if any placeholder remains or any other
source span changes.
