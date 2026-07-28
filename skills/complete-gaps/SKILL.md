---
name: complete-gaps
description: Use when a draft QMD contains todo placeholders, skipped derivation steps, incomplete proofs, or rough passages that need rigorous local completion.
---

# Complete Gaps

Complete a Quarto draft surgically without restructuring its argument. Work in
`drafts/` or a user-named project workspace. If the source is trusted
`knowledge/`, copy the relevant material into `drafts/` and leave the trusted
`knowledge/` page unchanged.

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
