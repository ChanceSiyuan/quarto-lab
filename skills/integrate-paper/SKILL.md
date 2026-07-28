---
name: integrate-paper
description: Use when integrating results from repository QMD notes into an existing LaTeX manuscript, filling manuscript sections, or restructuring an appendix from research notes.
---

# Integrate Paper

Fill or restructure a LaTeX manuscript from repository notes while preserving
the manuscript's notation, style, and bibliography conventions. Treat
`drafts/` and `literature/` as untrusted inputs; user corrections override
notes. Never edit `knowledge/` during manuscript integration.

## Establish first

- target manuscript and build command;
- source note paths;
- section map from results to main text or appendix;
- page or word budget;
- known corrections to the notes.

For a trusted source topic, resolve and read its complete bundle:

```bash
make knowledge-resolve QUERY="<source topic or result>"
```

Propose the section map and obtain explicit approval before writing.

## Workflow

1. Inventory the source theorems, proofs, examples, figures, citations, and
   anchors. Mark conflicts and superseded claims.
2. Decide which results belong in the main body, appendix, or nowhere. Do not
   silently compress away assumptions or negative results.
3. Fill the main body in the manuscript's style. Defer detailed proofs when the
   venue requires it and respect the page budget.
4. Merge appendix content instead of replacing it wholesale. Preserve existing
   derivations that remain valid.
5. Translate notation into the manuscript's macro layer; never paste QMD math
   mechanically.
6. Carry every needed citation into the manuscript bibliography and check all
   new `\cite` and `\ref` keys.
7. Run the manuscript's documented build command. Report unresolved references,
   compile failures, and page-budget drift.

Present the final diff and verification result. Manuscript approval does not
authorize changes to trusted knowledge.
